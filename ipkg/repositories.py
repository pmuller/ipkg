import logging
import hashlib
import os
import json
import re

from pkg_resources import parse_version

from .packages import PackageFile
from .exceptions import IpkgException
from .vfiles import vopen
from .utils import DictFile, parse_package_spec


LOGGER = logging.getLogger(__name__)


class PackageRepository(object):

    META_FILE_NAME = 'repository.json'

    def __init__(self, base):
        self.__meta = None
        self.base = base
        self.meta = DictFile(os.path.join(base, self.META_FILE_NAME))

    def __repr__(self):
        return 'PakageRepository(%r)' % self.base

    def find(self, spec, os_name, os_release, arch):
        meta = self.meta
        spec = parse_package_spec(spec)
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


class LocalPackageRepository(PackageRepository):
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
                    self.__add_package(name, package.version,
                                       package.revision, filepath)

                # Remove package name if no version was added
                if not meta[name].keys():
                    meta.pop(name)

        if not names or not meta.keys():
            LOGGER.warning('No package found')

        meta.save()

        LOGGER.info('Repository meta data updated')

    def build_formula(self, formula, remove_build_dir=True):
        """Build a formula and add the package to the repository.
        """
        package_dir = os.path.join(self.base, formula.name)
        if not os.path.exists(package_dir):
            os.mkdir(package_dir)
        package_file = formula.build(package_dir, remove_build_dir, self)
        self.__add_package(formula.name, formula.version,
                           formula.revision, package_file)
        self.meta.save()

    def __add_package(self, name, version, revision, filepath):
        """Add a package to the repository.
        """
        LOGGER.debug('Adding %s==%s:%s to repository',
                     name, version, revision)
        meta = self.meta

        if name not in meta:
            meta[name] = {}
        if version not in meta[name]:
            meta[name][version] = {}
        
        hashobj = hashlib.sha256()
        with open(filepath) as f:
            hashobj.update(f.read())
        checksum = hashobj.hexdigest()

        LOGGER.debug('sha256: %s', checksum)

        meta[name][version][revision] = {'checksum': checksum}

        LOGGER.info('Package %s==%s:%s added to repository',
                    name, version, revision)
