import os
import sys
import tempfile
import shutil
import logging
import hashlib
import tarfile
import time
import socket
#import pwd
import tarfile
import json
from cStringIO import StringIO

import requests

from . import environment
from .exceptions import IpkgException
from .packages import META_FILE
from .vfiles import vopen


LOGGER = logging.getLogger(__name__)


class BuildError(IpkgException):
    """Raised when a formula fails to build."""


def find_files(base):
    result = []
    for parent, sub_dirs, files in os.walk(base):
        rel_dir = parent.split(base)[1][1:]
        for filename in files:
            result.append(os.path.join(rel_dir, filename))
    return result




class Formula(object):
    """A recipe used to build a package.
    """
    name = None
    version = None
    revision = None
    sources = None
    patches = tuple()
    dependencies = tuple()
    homepage = None
    """Arguments passed to ``./configure``"""
    configure_args = ('--prefix=%(env_dir)s',)

    def __init__(self, env=None, verbose=False, log=None):
        self.env = env
        self.verbose = verbose
        self.log = log or logging.getLogger(__name__ )
        self.commands = {}
        self.__command_id = 0
        self.__cwd = os.getcwd()

    def run_command(self, command, args, data=None, cwd=None):

        if self.verbose:
            stdout = sys.stdout
            stderr = sys.stderr
        else:
            stdout = stderr = open(os.devnull, 'w')

        start = time.time()
        exit_code = self.env.execute(command, args,
                                     stdout=stdout, stderr=stderr,
                                     cwd=cwd or self.__cwd, data=data),

        report = {
            'command': command,
            'args': args,
            'start': start,
            'end': time.time(),
            'exit_code': exit_code,
            'cwd': cwd,
        }

        self.commands[self.__command_id] = report
        self.__command_id += 1
        return report

    def run_configure(self):
        dirs = {k + '_dir': v for k, v in self.env.directories.items()}
        args = [p % dirs for p in self.configure_args]
        self.run_command('./configure', args)

    def __getattr__(self, attr):
        if attr.startswith('run_'):
            command = attr.split('_', 1)[1]
            def func(args=None, **kw):
                self.run_command(command, args, **kw)
            return func
        else:
            raise AttributeError(attr)

    def build(self, package_dir, remove_build_dir=True, repository=None):
        """Build the formula."""
        LOGGER.debug('%r.build(package_dir=%s, remove_build_dir=%s)', self, package_dir, remove_build_dir)

        installed_dependencies = []
        build_dir = tempfile.mkdtemp(prefix='ipkg-build-')

        # Create a temporary env if no env has been previously defined
        if self.env is None:
            LOGGER.info('Creating temporary build environment')
            prefix = os.path.join(build_dir, 'environment')
            self.env = environment.Environment(prefix, os.environ)
            self.env.create_directories()

        env_prefix = self.env.prefix

        # Install dependencies in build environment
        if self.dependencies:
            LOGGER.info('Build dependencies: %s',
                        ', '.join(self.dependencies))
            for dependency in self.dependencies:
                if dependency not in self.env.packages:
                    self.env.install(dependency, repository)
                    installed_dependencies.append(dependency)

        # Create the sources root directory
        self.src_root = src_root = os.path.join(build_dir, 'sources')
        environment.mkdir(src_root, False)

        # Unarchive the sources file and store the sources directory as cwd 
        # for use when running commands from now
        LOGGER.info('Unarchiving source file: %s', self.sources)
        self.__cwd = self.unarchive(self.sources)

        # Apply patches
        if self.patches:
            LOGGER.info('Applying patches')
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
        self.__create_package(package_files, env_prefix, package_dir)

        # Cleanup
        LOGGER.debug('Removing files installed in build environment')
        for package_file in package_files:
            package_file_path = os.path.join(env_prefix, package_file)
            os.unlink(package_file_path)

        if self.dependencies:
            LOGGER.debug('Uninstalling dependencies from build environment')
            for dependency in self.dependencies:
                self.env.uninstall(dependency)

        if remove_build_dir:
            LOGGER.debug('Removing build directory: %s', build_dir)
            shutil.rmtree(build_dir)

        LOGGER.info('Build done')

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
            'revision': self.revision,
            'os_name': self.env.os_name,
            'os_release': self.env.os_release,
            'arch': self.env.arch,
            'dependencies': self.dependencies,
            'homepage': self.homepage,
            'hostname': socket.gethostname().split('.')[0],
            #'user': pwd.getpwuid(os.getuid()).pw_name,
            'timestamp': time.time(),
            'files': tuple(files),
            'build_prefix': build_dir,
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
                pkg.add(os.path.join(self.env.prefix, pkg_file),
                        pkg_file, recursive=False)

        LOGGER.info('Package %s created', filepath)

    def unarchive(self, src_file):
        LOGGER.debug('unarchive(%r)', src_file)

        if src_file.url.endswith('.tar.gz') or \
           src_file.url.endswith('.tar.bz2'):
            archive = tarfile.open(fileobj=src_file.open())
            root_items = set(i.path.split('/')[0] for i in archive)
        elif src_file.url.endswith('.zip'):
            archive = zipfile.ZipFile(src_file.open())
            root_items = set(i.filename.split('/')[0] for i in
                             archive.filelist)
        else:
            LOGGER.error('Cannot unarchive %s', src_file.url)
            raise NotImplemented

        if len(root_items) != 1:
            raise BuildError('There must be strictly 1 item at '
                             'root of sources file archive')

        archive.extractall(self.src_root)
        archive.close()

        return os.path.join(self.src_root, root_items.pop())

    @classmethod
    def from_file(cls, filepath):
        LOGGER.debug('%s.from_file("%s")', cls.__name__, filepath)

        globals_ = {'Formula': cls, 'File': File}
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
        return '%s(%r)' % (self.__class__.__name__, self.env)


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
