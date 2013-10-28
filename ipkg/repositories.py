import logging
import hashlib
import os
import json
import re

from pkg_resources import parse_version

from .packages import PackageFile
from .exceptions import IpkgException
from .files import vopen
from .utils import DictFile, parse_package_spec, make_package_spec
from .build import Formula


LOGGER = logging.getLogger(__name__)

FORMULA_FILE_RE = re.compile(r"""
^
(?P<name>[A-Za-z0-9_\-]+)
-
(?P<version>[0-9a-zA-Z\.\-_]+)
-
(?P<revision>\w+)
\.py
$
""", re.X)

PACKAGE_FILE_RE = re.compile(r"""
^
(?P<name>[A-Za-z0-9_\-]+)
-
(?P<version>[0-9a-zA-Z\.\-_]+)
-
(?P<revision>\w+)
-
(?P<os_name>\w+)
-
(?P<os_release>[\.\w]+)
-
(?P<arch>[_\w]+)
\.ipkg
$
""", re.X)


class PackageRepository(object):

    META_FILE_NAME = 'repository.json'

    def __init__(self, base):
        self.__meta = None
        self.base = base
        self.meta = DictFile(os.path.join(base, self.META_FILE_NAME))

    def __repr__(self):
        return 'PackageRepository(%r)' % self.base

    def __str__(self):
        return self.base

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

    def __iter__(self):
        packages = []
        for name in self.meta:
            name_dir = os.path.join(self.base, name)
            if not os.path.isdir(name_dir):
                continue
            for package_file in os.listdir(name_dir):
                if PACKAGE_FILE_RE.match(package_file):
                    package_filepath = os.path.join(name_dir, package_file)
                    packages.append(PackageFile(package_filepath))
        return iter(packages)


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
        return package_file

    def build_formulas(self, formula_repository,
                       environment=None, verbose=False):
        """Build all formulas and store them in this repository.
        """
        LOGGER.info('Building repository packages list...')
        current_packages = list(self)

        LOGGER.info('Building formulas list...')
        formulas = list(formula_repository)

        build_formulas = []

        for formula_cls in formulas:
            spec = make_package_spec(formula_cls)

            if formula_cls in current_packages:
                LOGGER.debug('%s already in repository %s', spec, self)

            else:
                LOGGER.info('New formula: %s', spec)
                formula = formula_cls(environment, verbose)
                build_formulas.append(formula)

        new_packages = []

        while build_formulas:
            build_formula = build_formulas.pop(0)

            dependency_in_formulas = False

            for dependency in build_formula.dependencies:
                if ((environment is not None and
                     dependency in environment.packages)
                    or dependency in self):
                    continue
                elif dependency in build_formulas:
                    build_formulas.append(build_formula)
                    dependency_in_formulas = True
                    LOGGER.debug('Delaying build of %s because it requires '
                                 '%s which will be built later' %
                                 (build_formula, dependency))
                    break
                else:
                    raise IpkgException('Missing dependency: %s' % dependency)

            if dependency_in_formulas:
                continue

            try:
                package_file = self.build_formula(formula)

            except IpkgException as err:
                LOGGER.exception('Failed to build %s: %s'
                                 % (spec, str(err)))

            else:
                new_packages.append(package_file)

        return new_packages

    def __add_package(self, name, version, revision, filepath):
        """Add a package to the repository.
        """
        spec = make_package_spec(vars())
        LOGGER.debug('Adding %s to repository', spec)
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

        LOGGER.info('Package %s added to repository', spec)


class FormulaRepository(object):
    """A Formula repository.
    """
    def __init__(self, base):
        self.base = base

    def __iter__(self):
        formulas = []
        for name in os.listdir(self.base):
            name_dir = os.path.join(self.base, name)
            if not os.path.isdir(name_dir):
                continue
            for formula_file in os.listdir(name_dir):
                if FORMULA_FILE_RE.match(formula_file):
                    formula_filepath = os.path.join(name_dir, formula_file)
                    formulas.append(Formula.from_file(formula_filepath))
        return iter(formulas)
