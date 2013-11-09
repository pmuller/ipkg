import logging
import hashlib
import os

from pkg_resources import parse_version

from .packages import MetaPackage, PackageFile
from .exceptions import IpkgException, InvalidPackage
from .utils import DictFile, make_package_spec, mkdir
from .build import Formula
from .regex import FORMULA_FILE
from .compat import basestring
from .requirements import PackageRequirement


LOGGER = logging.getLogger(__name__)


class RequirementNotFound(IpkgException):

    MESSAGE = 'Cannot find requirement %s for platform %s'


def compare_versions(a, b):
    if a < b:
        return -1
    elif a == b:
        return 0
    else:  # a > b
        return 1


class PackageRepository(object):

    META_FILE_NAME = 'repository.json'

    # easier to catch the exception when raised by find()
    RequirementNotFound = RequirementNotFound

    def __init__(self, base):
        self.__meta = None
        self.base = base
        self.meta = DictFile(os.path.join(base, self.META_FILE_NAME))

    def __repr__(self):
        return 'PackageRepository(%r)' % self.base

    def __str__(self):
        return self.base

    def find(self, requirement, platform):
        """Find the more recent package built for ``platform`` and which
           matches ``requirement``.
        """
        if not isinstance(requirement, PackageRequirement):
            requirement = PackageRequirement(requirement)
        version, revision = self.__match(requirement, platform)
        return self.__make_package_file(requirement.name,
                                        version, revision, platform)

    def __match(self, requirement, platform):
        name = requirement.name

        for version in self.__versions(name):
            for revision in self.__revisions(name, version):
                package = MetaPackage({'name': name,
                                       'version': version,
                                       'revision': revision})
                if requirement.is_satisfied_by(package):
                    return version, revision
        else:
            raise RequirementNotFound(requirement, platform)

    def __make_package_file(self, name, version, revision, platform):
        filepath = '%(name)s/%(name)s-%(version)s-%(revision)s-' \
                   '%(platform)s.ipkg' % vars()
        return PackageFile(os.path.join(self.base, filepath))

    def __versions(self, name):
        if name in self.meta:
            return sorted(self.meta[name].keys(), reverse=True,
                          key=parse_version, cmp=compare_versions)
        else:
            return []

    def __revisions(self, name, version):
        if name in self.meta and version in self.meta[name]:
            revisions = [str(r) for r in self.meta[name][version]]
            return sorted(revisions, key=parse_version, cmp=compare_versions,
                          reverse=True)
        else:
            return []

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

                    self.add(filepath)

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
        meta = self.meta

        if isinstance(package, basestring):
            if os.path.exists(package):
                package = PackageFile(package)
            else:
                raise InvalidPackage(package)

        # Check if the package obj is package-like
        if not hasattr(package, 'meta') or \
           not hasattr(package, 'name') or \
           not hasattr(package, 'version') or \
           not hasattr(package, 'revision'):
            raise InvalidPackage(package)

        if package.name not in meta:
            meta[package.name] = {}
        if package.version not in meta[package.name]:
            meta[package.name][package.version] = {}

        package_meta = dict(package.meta)

        if compute_checksum:
            hashobj = hashlib.sha256()
            with open(str(package)) as fileobj:
                hashobj.update(fileobj.read())
            checksum = hashobj.hexdigest()
            LOGGER.debug('sha256: %s', checksum)
            package_meta['checksum'] = checksum

        meta[package.name][package.version][package.revision] = package_meta

        LOGGER.info('Package %s added to repository', package)


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
