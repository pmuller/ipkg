import logging
import hashlib
import os
import json
import re

from pkg_resources import parse_version

from .packages import PackageFile
from .exceptions import IpkgException
from .vfiles import vopen


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

    def __repr__(self):
        return 'Repository(%r)' % self.base

    def get(self, path):
        full_path = os.path.join(self.base, path)
        return vopen(full_path)

    @property
    def meta(self):
        if self.__meta == None:
            raw = self.get(self.META_FILE_NAME).read()
            self.__meta = json.loads(raw)
        return self.__meta

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

    def update_metadata(self):
        """Update the repository meta data file."""
        LOGGER.debug('Updating repository metadata')
        meta = {}
        package_names = os.listdir(self.base)

        for package_name in package_names:
            if package_name == self.META_FILE_NAME:
                continue

            meta_package = {}
            meta[package_name] = meta_package
            package_path = os.path.join(self.base, package_name)
            package_files = os.listdir(package_path)
            #LOGGER.debug('package files: %r', package_files)

            for package_file in package_files:
                filepath = os.path.join(package_path, package_file)
                package = PackageFile(filepath)
                version = package.version
                revision = package.revision
                #LOGGER.debug('package: %r', package)

                if version not in meta_package:
                    meta_package[version] = {}

                hashobj = hashlib.sha256()
                hashobj.update(open(filepath).read())
                checksum = hashobj.hexdigest()

                meta_revision = {'checksum': checksum}
                meta_package[version][revision] = meta_revision

        LOGGER.debug('meta: %r', meta)
        with open(os.path.join(self.base, self.META_FILE_NAME), 'w') as f:
            f.write(json.dumps(meta, indent=4))

        LOGGER.info('Repository meta data updated')
