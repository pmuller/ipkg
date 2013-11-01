import os
import sys
import tempfile
import shutil
import logging
import hashlib
import time
import tarfile
import json

from .environments import Environment
from .exceptions import IpkgException
from .packages import META_FILE
from .files import vopen
from .mixins import NameVersionRevisionComparable
from .utils import unarchive, mkdir
from .compat import basestring, StringIO
from . import platform


LOGGER = logging.getLogger(__name__)


class BuildError(IpkgException):
    """Raised when a formula fails to build."""


class IncompleteFormula(BuildError):
    """A mandatory attribute is missing.
    """
    def __init__(self, attr):
        self.attr = attr

    def __str__(self):
        return 'The "%s" attribute is mandatory' % self.attr


def find_files(base):
    result = []
    for parent, sub_dirs, files in os.walk(base):
        rel_dir = parent.split(base)[1][1:]
        for filename in files:
            result.append(os.path.join(rel_dir, filename))
    return result


class Formula(NameVersionRevisionComparable):
    """A recipe used to build a package.
    """
    name = None
    version = None
    revision = None
    sources = None
    patches = tuple()
    dependencies = tuple()
    homepage = None
    envvars = None
    build_envvars = None
    """Arguments passed to ``./configure``"""
    configure_args = ['--prefix=%(prefix)s']

    def __init__(self, environment=None, verbose=False, log=None):

        # Check for mandatory attributes
        for attr in ('name', 'version', 'revision', 'sources'):
            if getattr(self, attr) is None:
                raise IncompleteFormula(attr)

        self.environment = environment
        self.verbose = verbose
        self.log = log or logging.getLogger(__name__ )
        self.commands = {}
        self.__command_id = 0
        self.__cwd = os.getcwd()

    def run_command(self, command, data=None, cwd=None):
        cmd = command if isinstance(command, basestring) else ' '.join(command)
        LOGGER.info('Running: %s', cmd)

        if self.verbose:
            stdout = sys.stdout
            stderr = sys.stderr
        else:
            stdout = stderr = open(os.devnull, 'w')

        start = time.time()
        exit_code = self.environment.execute(command,
                                             stdout=stdout, stderr=stderr,
                                             cwd=cwd or self.__cwd, data=data),

        report = {
            'command': command,
            'start': start,
            'end': time.time(),
            'exit_code': exit_code,
            'cwd': cwd,
        }

        self.commands[self.__command_id] = report
        self.__command_id += 1
        return report

    def run_configure(self):
        command = ['./configure']
        directories = self.environment.directories
        command.extend(arg % directories for arg in self.configure_args)
        self.run_command(command)

    def __getattr__(self, attr):
        if attr.startswith('run_'):
            command = [attr.split('_', 1)[1]]
            def func(args=None, **kw):
                if args:
                    if isinstance(args, basestring):
                        args = args.split()
                    command.extend(args)
                self.run_command(command, **kw)
            return func
        else:
            raise AttributeError(attr)

    def build(self, package_dir, remove_build_dir=True, repository=None):
        """Build the formula."""
        LOGGER.debug('%r.build(package_dir=%s, remove_build_dir=%s)', self, package_dir, remove_build_dir)

        installed_dependencies = []
        build_dir = tempfile.mkdtemp(prefix='ipkg-build-')

        # Create a temporary env if no env has been previously defined
        if self.environment is None:
            LOGGER.info('Creating temporary build environment')
            prefix = os.path.join(build_dir, 'environment')
            self.environment = Environment(prefix)
            self.environment.directories.create()

        if self.build_envvars:
            self.environment.variables.add(self.build_envvars)

        env_prefix = self.environment.prefix

        # Install dependencies in build environment
        if self.dependencies:
            LOGGER.info('Build dependencies: %s',
                        ', '.join(self.dependencies))
            for dependency in self.dependencies:
                if dependency not in self.environment.packages:
                    self.environment.install(dependency, repository)
                    installed_dependencies.append(dependency)

        # Create the sources root directory
        self.src_root = src_root = os.path.join(build_dir, 'sources')
        mkdir(src_root, False)

        # Unarchive the sources file and store the sources directory as cwd 
        # for use when running commands from now
        self.__cwd = self.unarchive(self.sources)

        # Apply patches
        if self.patches:
            strip = 0
            for patch in self.patches:
                LOGGER.info('Applying patch: %s', patch)
                self.run_patch(['-p%d' % strip], data=patch.open().read())

        # Create a list of the files contained in the environment before
        # running "make install"
        files_before_install = set(find_files(env_prefix))

        # Compile and install the code
        self.install()

        # Compare the current environment file list with the previous one
        package_files = set(find_files(env_prefix)) - files_before_install
        # Use the list of new files to create a package
        ipkg_file = self.__create_package(package_files,
                                          env_prefix, package_dir)

        # Cleanup
        LOGGER.debug('Removing files installed in build environment')
        for package_file in package_files:
            package_file_path = os.path.join(env_prefix, package_file)
            os.unlink(package_file_path)

        if self.dependencies:
            LOGGER.debug('Uninstalling dependencies from build environment')
            for dependency in self.dependencies:
                self.environment.uninstall(dependency)

        if remove_build_dir:
            LOGGER.debug('Removing build directory: %s', build_dir)
            shutil.rmtree(build_dir)

        LOGGER.info('Build done')

        return ipkg_file

    def install(self):
        self.run_configure()
        self.run_make()
        self.run_make(['install'])

    def __create_package(self, files, build_dir, package_dir):
        #LOGGER.debug('%r.__create_package(%r, %r, %r)',
        #             self, files, build_dir, package_dir)

        meta = {
            'name': self.name,
            'version': self.version,
            'revision': str(self.revision),
            'os_name': platform.NAME,
            'os_release': platform.RELEASE,
            'arch': platform.ARCHITECTURE,
            'dependencies': self.dependencies,
            'homepage': self.homepage,
            'hostname': platform.HOSTNAME,
            'timestamp': time.time(),
            'files': tuple(files),
            'build_prefix': build_dir,
            'envvars': self.envvars,
        }

        filename = '%(name)s-%(version)s-%(revision)s-' \
                   '%(os_name)s-%(os_release)s-%(arch)s.ipkg' % meta
        filepath = os.path.join(package_dir, filename)

        meta_string = StringIO()
        json.dump(meta, meta_string, indent=4)
        meta_string_size = meta_string.tell()
        meta_string.seek(0)

        meta_tarinfo = tarfile.TarInfo(META_FILE)
        meta_tarinfo.type = tarfile.REGTYPE
        meta_tarinfo.mode = 0644
        meta_tarinfo.size = meta_string_size

        with tarfile.open(filepath, 'w:bz2') as pkg:
            pkg.addfile(meta_tarinfo, meta_string)
            for pkg_file in files:
                pkg.add(os.path.join(self.environment.prefix, pkg_file),
                        pkg_file, recursive=False)

        LOGGER.info('Package %s created', filepath)

        return filepath

    def unarchive(self, src_file):
        """Unarchive ``src_file``.
        """
        return unarchive(src_file.open(), self.src_root)

    @classmethod
    def from_file(cls, filepath):
        """Load a Formula from a file.
        """
        #LOGGER.debug('%s.from_file("%s")', cls.__name__, filepath)

        globals_ = {'Formula': cls, 'File': File, 'platform': platform}
        locals_ = {}

        with open(filepath) as bf:
            exec bf.read() in globals_, locals_

        formula_classes = []
        for obj in locals_.values():
            try:
                is_formula = issubclass(obj, Formula)
            except TypeError:
                pass
            else:
                if is_formula:
                    formula_classes.append(obj)

        if formula_classes:
            if len(formula_classes) > 1:
                raise IpkgException('Too many Formula classes')
            else:
                formula_class = formula_classes[0]
        else:
            raise IpkgException('No Formula class found')

        return formula_class

    def __repr__(self):
        return '%s(%r)' % (self.__class__.__name__, self.environment)


class File(object):

    def __init__(self, url, **kw):
        if 'sha512' in kw:
            hash_class = hashlib.sha512
            expected_hash = kw.pop('sha512')
        elif 'sha384' in kw:
            hash_class = hashlib.sha384
            expected_hash = kw.pop('sha384')
        elif 'sha256' in kw:
            hash_class = hashlib.sha256
            expected_hash = kw.pop('sha256')
        elif 'sha224' in kw:
            hash_class = hashlib.sha224
            expected_hash = kw.pop('sha224')
        elif 'sha1' in kw:
            hash_class = hashlib.sha1
            expected_hash = kw.pop('sha1')
        elif 'md5' in kw:
            hash_class = hashlib.md5
            expected_hash = kw.pop('md5')
        else:
            hash_class = None
            expected_hash = None

        self.url = url
        self.hash_class = hash_class
        self.expected_hash = expected_hash

    def open(self):
        f = vopen(self.url, expected_hash=self.expected_hash,
                  hash_class=self.hash_class)
        f.verify_checksum()
        return f

    def __repr__(self):
        return 'File("%s")' % self.url

    def __str__(self):
        return self.url
