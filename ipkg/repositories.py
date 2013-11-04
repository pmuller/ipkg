import logging
import hashlib
import os
import json

from pkg_resources import parse_version

from .packages import MetaPackage, PackageFile
from .exceptions import IpkgException
from .files import vopen
from .utils import DictFile, parse_package_spec, make_package_spec, mkdir
from .build import Formula
from .regex import FORMULA_FILE


LOGGER = logging.getLogger(__name__)


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
            else:  # a > b
                return 1

        if version is None:
            versions = self.meta[name].keys()
            versions = sorted(versions, key=parse_version, cmp=compare)
            version = versions[-1]

        revisions = [str(r) for r in self.meta[name][version]]
        revisions = sorted(revisions, key=parse_version, cmp=compare)
        revision = revisions[-1]

        return version, revision

    def __iter__(self):
        packages = []
        for name, versions in self.meta.items():
            for version, revisions in versions.items():
                for revision, meta in revisions.items():
                    packages.append(MetaPackage(meta))
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
            mkdir(package_dir)
        package_file = formula.build(package_dir, remove_build_dir, self)
        self.__add_package(formula.name, formula.version,
                           formula.revision, package_file)
        self.meta.save()
        return package_file

    def build_formulas(self, formula_repository,
                       environment=None, verbose=False):
        """Build all formulas and store them in this repository.
        """
        formulas = []  # formulas not already built
        built_packages = []  # new packages

        LOGGER.debug('Building repository packages list...')
        repo_packages = list(self)

        for formula_cls in formula_repository:
            if formula_cls not in repo_packages:
                formulas.append(formula_cls(environment, verbose))
        LOGGER.debug('Formulas: %r', formulas)

        while formulas:
            build_later = False
            formula = formulas.pop(0)

            for dependency in formula.dependencies:

                if dependency in formulas:
                    formulas.append(formula)
                    build_later = True
                    LOGGER.debug('Delaying build of %s because it requires '
                                 '%s which will be built later' %
                                 (formula, dependency))
                    break

                # If the dependency is installed in the environment or present
                # in this repository, it is satisfied.
                if ((environment is not None and
                     dependency in environment.packages)
                        or dependency in repo_packages
                        or dependency in built_packages):
                    continue

                else:
                    LOGGER.error('Cannot build %s: Missing dependency: %s' %
                                 (formula, dependency))
                    break

            if not build_later:

                try:
                    package_file = self.build_formula(formula)

                except IpkgException as err:
                    LOGGER.exception('Failed to build %s: %s' %
                                     (make_package_spec(formula), str(err)))

                else:
                    built_packages.append(package_file)

        return built_packages

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

        package_meta = dict(PackageFile(filepath).meta)
        package_meta['checksum'] = checksum

        meta[name][version][revision] = package_meta

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
                if FORMULA_FILE.match(formula_file):
                    formula_filepath = os.path.join(name_dir, formula_file)
                    formulas.append(Formula.from_file(formula_filepath))
        return iter(formulas)
