import logging
import hashlib
import os
from collections import defaultdict

from pkg_resources import parse_version

from .packages import PackageFile, make_filename
from .exceptions import IpkgException, InvalidPackage
from .utils import DictFile, make_package_spec, mkdir
from .build import Formula
from .regex import FORMULA_FILE
from .compat import basestring
from .requirements import Requirement


LOGGER = logging.getLogger(__name__)


class RequirementNotFound(IpkgException):

    MESSAGE = 'Cannot find requirement %s'


def compare_versions(a, b):
    if a < b:
        return -1
    elif a == b:
        return 0
    else:  # a > b
        return 1


def extract_version(item):
    if isinstance(item, dict):
        version = item['version']
        revision = item['revision']
    else:
        version = item.version
        revision = item.revision
    return parse_version(version), parse_version(str(revision))


class BaseRepository(object):

    def __init__(self, base):
        self.base = base
        self.meta = {}

    def __repr__(self):
        return '%s(%r)' % (self.__class__.__name__, self.base)

    def __str__(self):
        return self.base

    def __getitem__(self, requirement):
        """Find the more recent package matching ``requirement``.
        """
        items = self.find(requirement)
        if items:
            return items[0]
        else:
            raise RequirementNotFound(requirement)

    def find(self, requirement):
        if isinstance(requirement, basestring):
            requirement = Requirement(requirement)

        if not isinstance(requirement, Requirement):
            raise TypeError(requirement)

        items = self.meta.get(requirement.name)
        if items:
            results = [item for item in items
                       if requirement.satisfied_by(item)]

            return sorted(results, key=extract_version,
                          cmp=compare_versions, reverse=True)

        else:
            return []


class PackageRepository(BaseRepository):

    META_FILE_NAME = 'repository.json'

    # easier to catch the exception when raised by find()
    RequirementNotFound = RequirementNotFound

    def __init__(self, base):
        super(PackageRepository, self).__init__(base)
        self.meta = DictFile(os.path.join(base, self.META_FILE_NAME))

    def __make_package_file(self, meta):
        filepath = os.path.join(self.base, meta['name'],
                                make_filename(**meta))
        return PackageFile(filepath, meta)

    def __iter__(self):
        for meta_list in self.meta.values():
            for meta in meta_list:
                yield self.__make_package_file(meta)

    def find(self, requirement):
        results = super(PackageRepository, self).find(requirement)
        return map(self.__make_package_file, results)


class LocalPackageRepository(PackageRepository):
    """A Repository stored on the local filesystem.
    """
    def update_metadata(self):
        """Update the repository meta data file."""
        LOGGER.info('Updating metadata of %r', self)
        meta = self.meta
        meta.clear()
        names = os.listdir(self.base)

        for name in names:
            if name == self.META_FILE_NAME:
                # Ignore the meta data file at repository root
                continue

            package_dir = os.path.join(self.base, name)

            if not os.path.isdir(package_dir):
                #LOGGER.debug('Ignoring, because it is not '
                #             'a directory: %s', name)
                continue

            for filename in os.listdir(package_dir):
                filepath = os.path.join(package_dir, filename)

                if not os.path.isfile(filepath):
                    #LOGGER.debug('Ignoring, because it is not a file: %s',
                    #             filepath)
                    continue

                self.add(filepath)

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
        self.add(package_file)
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

    def add(self, package, compute_checksum=True):
        """Add a package to the repository.

        ``package`` can be a ``PackageFile`` or string.
        If it is a string, it is expected to be a valid path to an ipkg
        package file.
        """
        LOGGER.debug('Adding %s to repository', package)

        if isinstance(package, basestring) and os.path.exists(package):
            package = PackageFile(package)

        if not isinstance(package, PackageFile):
            raise InvalidPackage(package)

        meta = self.meta

        if package.name not in meta:
            meta[package.name] = []

        package_meta = dict(package.meta)

        if compute_checksum:
            hashobj = hashlib.sha256()
            with open(package.path) as fileobj:
                hashobj.update(fileobj.read())
            checksum = hashobj.hexdigest()
            LOGGER.debug('sha256: %s', checksum)
            package_meta['checksum'] = checksum

        meta[package.name].append(package_meta)

        LOGGER.info('Package %s added to repository', package)


class FormulaRepository(BaseRepository):
    """A Formula repository.
    """
    def __init__(self, base):
        super(FormulaRepository, self).__init__(base)
        self.meta = defaultdict(list)

        for name in os.listdir(self.base):
            name_dir = os.path.join(self.base, name)

            if not os.path.isdir(name_dir):
                continue

            for formula_file in os.listdir(name_dir):
                if FORMULA_FILE.match(formula_file):
                    formula_filepath = os.path.join(name_dir, formula_file)
                    formula = Formula.from_file(formula_filepath)
                    self.meta[formula.name].append(formula)

    def __iter__(self):
        for formula_list in self.meta.values():
            for formula in formula_list:
                yield formula
