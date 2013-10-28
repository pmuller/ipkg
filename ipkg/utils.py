import os
import re
import sys
import json
import logging
import subprocess
import tarfile
import zipfile

from .vfiles import vopen
from .exceptions import IpkgException


LOGGER = logging.getLogger(__name__)

PACKAGE_SPEC_RE = re.compile(r"""
^
(?P<name>[A-Za-z0-9_\-]+)
(
    (?P<operator>==)
    (?P<version>[0-9a-zA-Z\.\-_]+)
    (
        :
        (?P<revision>\w+)
    )?
)?
$
""", re.X)


class ExecutionFailed(IpkgException):
    """A command failed to run.
    """
    def __init__(self, command, reason):
        self.command = command
        self.reason = reason

    def __str__(self):
        return 'Cannot execute %s: %s' % (' '.join(self.command), self.reason)


class InvalidPackage(IpkgException):
    """Failed parse a package spec or argument is not package like.
    """
    def __init__(self, spec):
        self.spec = spec

    def __str__(self):
        return 'Invalid package: %s' % self.spec


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
            self.update(json.load(vopen(self.__file_path)))

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
        kw['stdin'] = subprocess.PIPE

    # If command is a string, split it to get a format that Popen understands
    if isinstance(command, basestring):
        command_ = command.split()
    else:
        command_ = command

    try:
        process = subprocess.Popen(command_, **kw)

    except OSError as exception:
        if exception.errno == errno.ENOENT:
            error = 'Command not found'
        else:
            error = exception.strerror
        raise ExecutionFailed(command, error)

    stdout_str, stderr_str = process.communicate(data)

    if process.returncode != 0:
        raise ExecutionFailed(command,
                              'exited with code %i' % process.returncode)

    return stdout_str, stderr_str


def is_package_like(obj):
    """Check if ``obj`` has the ``name``, ``version`` and ``revision``
       attributes.
    """
    return hasattr(obj, 'name') and \
           hasattr(obj, 'version') and \
           hasattr(obj, 'revision')


def make_package_spec(obj):

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
    match = PACKAGE_SPEC_RE.match(spec)
    if match:
        return match.groupdict()
    else:
        raise InvalidPackage(spec)


def unarchive(fileobj, target):
    LOGGER.debug('unarchive(%r, %r)', fileobj, target)

    if fileobj.name.endswith('.tar.gz') or \
       fileobj.name.endswith('.tar.bz2'):
        archive = tarfile.open(fileobj=fileobj)
        root_items = set(i.path.split('/')[0] for i in archive)

    elif fileobj.name.endswith('.zip'):
        archive = zipfile.ZipFile(fileobj)
        root_items = set(i.filename.split('/')[0] for i in
                         archive.filelist)

    else:
        raise IpkgException('Unrecognized file type %s' % fileobj.name)

    if len(root_items) != 1:
        raise BuildError('There must be strictly 1 item at '
                         'root of sources file archive')

    LOGGER.info('Extracting: %s', fileobj)
    archive.extractall(target)
    LOGGER.info('Extracted: %s', fileobj)
    archive.close()

    return os.path.join(target, root_items.pop())
