import logging
import hashlib
import os
import json
import re

from pkg_resources import parse_version

from .packages import PackageFile
from .exceptions import IpkgException
from .vfiles import vopen
from .utils import DictFile


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


class Repository(object):

    META_FILE_NAME = 'repository.json'

    def __init__(self, base):
        self.__meta = None
        self.base = base
        self.meta = DictFile(os.path.join(base, self.META_FILE_NAME))

    def __repr__(self):
        return 'Repository(%r)' % self.base

    def find(self, spec, os_name, os_release, arch):
        meta = self.meta

        match = PACKAGE_SPEC_RE.match(spec)
        if match:
            spec = match.groupdict()
        else:
            raise IpkgException('Invalid package: %s' % spec)

        name = spec['name']
        version = spec['version']
        revision = spec['revision']

        if name not in meta:
            raise IpkgException('Package %s not found' % name)
        elif version is not None and version not in meta[name]:
            raise IpkgException('Package %s version %s not found' %
                                (name, version))
        elif revision is not None and revision not in meta[name][version]:
            raise IpkgException('Package %s version %s revision %s not found' %
                                (name, version, revision))
        
        if version is None or revision is None:
            version, revision = self.__find_latest(name, version)

        filepath = '%(name)s/%(name)s-%(version)s-%(revision)s-' \
                   '%(os_name)s-%(os_release)s-%(arch)s.ipkg' % vars()
        return PackageFile(os.path.join(self.base, filepath))

    def __find_latest(self, name, version=None):
        
        def compare(a, b):
            if a < b:
                return -1
            elif a == b:
                return 0
            else: # a > b
                return 1

        if version is None:
            versions = self.meta[name].keys()
            versions = sorted(versions, key=parse_version, cmp=compare)
            version = versions[-1]

        revisions = self.meta[name][version].keys()
        revisions = sorted(revisions, key=parse_version, cmp=compare)
        revision = revisions[-1]

        return version, revision


class LocalRepository(Repository):
    """A Repository stored on the local filesystem.
    """
    def update_metadata(self):
        """Update the repository meta data file."""
        LOGGER.info('Updating metadata of %r', self)
        meta = self.meta
        meta.clear()
        names = os.listdir(self.base)

        if names:
            LOGGER.debug('Repository package names: %s', ' '.join(names))

            for name in names:
                if name == self.META_FILE_NAME:
                    # Ignore the meta data file at repository root
                    continue

                if name not in meta:
                    meta[name] = {}

                package_dir = os.path.join(self.base, name)

                if not os.path.isdir(package_dir):
                    LOGGER.debug('Ignoring, because it is not '
                                 'a directory: %s', name)
                    continue

                files = os.listdir(package_dir)

                for filename in files:
                    filepath = os.path.join(package_dir, filename)

                    if not os.path.isfile(filepath):
                        LOGGER.debug('Ignoring, because it is not a file: %s',
                                     filepath)
                        continue

                    package = PackageFile(filepath)
                    version = package.version
                    revision = package.revision

                    if version not in meta[name]:
                        meta[name][version] = {}

                    LOGGER.debug('Adding %s to repository', package)

                    hashobj = hashlib.sha256()
                    with open(filepath) as f:
                        hashobj.update(f.read())
                    checksum = hashobj.hexdigest()

                    meta[name][version][revision] = {'checksum': checksum}

                # Remove package name if no version was added
                if not meta[name].keys():
                    meta.pop(name)

        elif not names or not meta.keys():
            LOGGER.warning('No package found')

        meta.save()

        LOGGER.info('Repository meta data updated')
