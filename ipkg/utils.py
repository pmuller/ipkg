import os
import sys
import json
import logging
import subprocess
import tarfile
import zipfile
import errno
import shlex

from .files import vopen
from .exceptions import IpkgException, InvalidPackage
from .compat import basestring, StringIO
from .regex import PACKAGE_SPEC


LOGGER = logging.getLogger(__name__)
PIPE = subprocess.PIPE


class ExecutionFailed(IpkgException):
    """A command failed to run.
    """
    def __init__(self, command, reason):
        self.command = command
        self.reason = reason

    def __str__(self):
        return 'Command "%s" failed: %s' % (
            ' '.join(self.command), self.reason)


class InvalidDictFileContent(IpkgException):
    """Raised when a DictFile load data from an invalid meta data file.
    """
    def __init__(self, filepath):
        self.filepath = filepath

    def __str__(self):
        return 'Invalid JSON data: %s' % self.filepath


class CannotCreateDirectory(IpkgException):
    """Raised when a directory cannot be created"""
    def __init__(self, directory, reason):
        self.directory = directory
        self.reason = reason

    def __str__(self):
        return 'Cannot create directory %s: %s' % (self.directory,
                                                   self.reason)


class DictFile(dict):
    """A ``dict``, storable as a JSON file.
    """
    def __init__(self, file_path):
        super(DictFile, self).__init__()
        self.__file_path = file_path
        self.reload()

    def reload(self):
        if os.path.isfile(self.__file_path):
            LOGGER.debug('Loading %s', self.__file_path)
            raw = vopen(self.__file_path).read()
            if raw:
                try:
                    data = json.loads(raw)
                except ValueError:
                    raise InvalidDictFileContent(self.__file_path)
                else:
                    self.update(json.loads(raw))

    def clear(self):
        """Force the dictionary to be empty.
        """
        if os.path.isfile(self.__file_path):
            os.unlink(self.__file_path)
            super(DictFile, self).clear()

    def save(self):
        LOGGER.debug('Writing %s', self.__file_path)
        # This will break if trying to call save() on a remote DictFile
        with open(self.__file_path, 'w') as f:
            json.dump(self, f, indent=4)


def execute(command,
            stdin=sys.stdin, stdout=sys.stdout, stderr=sys.stderr,
            cwd=None, data=None, env=None):
    """Execute a command.
    """
    env_str = '{...}' if env else None
    LOGGER.debug('execute(command=%r, stdin=%s, stdout=%s, stderr=%s, cwd=%r'
                 ', env=%s)' % (command, stdin, stdout, stderr, cwd, env_str))

    kw = {'cwd': cwd}

    if env:
        kw['env'] = env

    if stdout:
        kw['stdout'] = stdout

    if stderr:
        kw['stderr'] = stderr

    if data is None:
        if stdin:
            kw['stdin'] = stdin
    else:
        #data = data.encode('UTF-8') # Python 3 compat
        kw['stdin'] = PIPE

    # If command is a string, split it to get a format that Popen understands
    if isinstance(command, basestring):
        command_ = shlex.split(command)
    else:
        command_ = command

    try:
        process = subprocess.Popen(command_, **kw)

    except OSError as exception:
        if exception.errno == errno.ENOENT:
            error = 'Command not found'
        else:
            error = exception.strerror
        raise ExecutionFailed(command_, error)

    stdout_str, stderr_str = process.communicate(data)

    if process.returncode != 0:
        raise ExecutionFailed(command_,
                              'exited with code %i' % process.returncode)

    #if hasattr(stdout_str, 'decode'):
    #    stdout_str = stdout_str.decode('UTF-8')
    #if hasattr(stderr_str, 'decode'):
    #    stderr_str = stderr_str.decode('UTF-8')

    return stdout_str, stderr_str


def is_package_like(obj):
    """Check if ``obj`` has the ``name``, ``version`` and ``revision``
       attributes.
    """
    return hasattr(obj, 'name') and \
        hasattr(obj, 'version') and \
        hasattr(obj, 'revision')


def make_package_spec(obj):
    """Returns a package specification string,
       formatted as ``name==version:revision``.

       Accepts package-like objects and dicts.
    """
    if is_package_like(obj):
        return '%s==%s:%s' % (obj.name, obj.version, obj.revision)

    elif isinstance(obj, dict):
        if 'name' in obj:
            spec = obj['name']
            if obj.get('version') is not None:
                spec += '==' + obj['version']
                if obj.get('revision') is not None:
                    spec += ':%s' % obj['revision']
            return spec

    raise InvalidPackage(obj)


def parse_package_spec(spec):
    """Parse a package ``spec``.
    """
    match = PACKAGE_SPEC.match(spec)
    if match:
        return match.groupdict()
    else:
        raise InvalidPackage(spec)


def which(command):
    """Find a command in ``$PATH``.
    """
    for directory in os.environ['PATH'].split(':'):
        path = os.path.join(directory, command)
        if os.path.exists(path) and os.path.isfile(path):
            return path


def unarchive(fileobj, target):
    """Extract an archive, detecting its format.

    Supports: tar.bz2, tar.gz, tar.xz, zip
    """
    LOGGER.debug('unarchive(%r, %r)', fileobj, target)

    filename = fileobj.name

    # Since tarfile cannot handle xz archives,
    # we first use the xz tool to uncompress it
    if filename.endswith('.tar.xz'):
        xz = which('xz')
        if not xz:
            raise IpkgException('Cannot find the xz tool')
        fileobj = StringIO(
            execute('xz -d -c', data=fileobj.read(), stdout=PIPE)[0])

    tar_extensions = (['tar', 'bz2'], ['tar', 'gz'], ['tar', 'xz'])
    if filename.split('.')[-2:] in tar_extensions:
        archive = tarfile.open(fileobj=fileobj)
        root_items = set(i.path.split('/')[0] for i in archive)

    elif filename.endswith('.zip'):
        archive = zipfile.ZipFile(fileobj)
        root_items = set(i.filename.split('/')[0] for i in
                         archive.filelist)

    else:
        raise IpkgException('Unrecognized file type %s' % filename)

    if len(root_items) != 1:
        raise IpkgException('There must be strictly 1 item at '
                            'root of sources file archive')

    LOGGER.info('Extracting: %s', fileobj)
    archive.extractall(target)
    LOGGER.info('Extracted: %s', fileobj)
    archive.close()

    return os.path.join(target, root_items.pop())


def mkdir(directory, fail_if_it_exist=True):
    """Create a directory"""
    LOGGER.debug('Creating directory %s', directory)
    try:
        os.mkdir(directory)
    except OSError as exception:
        if exception.errno != errno.EEXIST or fail_if_it_exist:
            raise CannotCreateDirectory(directory, exception.strerror)
