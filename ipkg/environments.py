import sys
import os
import logging
import shutil
import tempfile

from .exceptions import IpkgException
from .packages import MetaPackage, PackageFile
from .prefix_rewriters import rewrite_prefix
from .utils import DictFile, execute, make_package_spec, mkdir
from .compat import basestring
from .files.exceptions import FilesException
from .platforms import Platform


LOGGER = logging.getLogger(__name__)


class UnknownEnvironment(IpkgException):
    """No environment loaded.
    """
    def __str__(self):
        return self.__doc__.strip()


class NotInstalled(IpkgException):
    """A package is missing.
    """
    def __init__(self, package):
        self.package = package

    def __str__(self):
        return 'Package %s is not installed' % self.package


class InvalidVariableValue(IpkgException):
    """Raised when trying to assign an invalid value to an environment
       variable.
    """
    def __init__(self, name, value):
        self.name = name
        self.value = value

    def __str__(self):
        return 'Invalid value for environment variable %s: %s' % (self.name,
                                                                  self.value)


def in_env():
    """Returns ``True`` if running inside an ipkg environment.
    """
    return 'IPKG_ENVIRONMENT' in os.environ


def current():
    """Get the ``Environment`` we are currently using.
    """
    if in_env():
        return Environment(os.environ['IPKG_ENVIRONMENT'])
    else:
        raise UnknownEnvironment()


class Variable(object):
    """An environment variable with free text value.
    """
    def __init__(self, name, value=None):
        self.name = name
        self.set(value)

    def set(self, value):
        if isinstance(value, basestring):
            self.value = value
        else:
            raise InvalidVariableValue(self.name, value)

    def __str__(self):
        return str(self.value)

    def __repr__(self):
        return '%s(%r)' % (self.__class__.__name__, str(self))


class ListVariable(Variable):
    """Base class for environment variables using a list of values as a value.

    Sub classes just have to override the LIST_SEPARATOR attribute.
    """
    LIST_SEPARATOR = None

    def set(self, value):
        if value is None:
            self.__list = []
        elif isinstance(value, basestring):
            self.__list = value.split(self.LIST_SEPARATOR)
        else:
            raise InvalidVariableValue(self.name, value)

    def remove(self, item):
        if item in self.__list:
            item_index = self.__list.index(item)
            self.__list.pop(item_index)

    def insert(self, item, index=0):
        self.remove(item)
        self.__list.insert(index, item)

    def append(self, item):
        self.remove(item)
        self.__list.append(item)

    def __str__(self):
        return self.LIST_SEPARATOR.join(self.__list)


class PathListVariable(ListVariable):
    """This represents an environment variable whose value is a path list.
    """
    LIST_SEPARATOR = ':'


#class ArgumentListVariable(ListVariable):
#    """A list of strings"""
#    LIST_SEPARATOR = ' '


class EnvironmentDirectories(dict):
    """Directories of an ipkg environment.
    """
    def __init__(self, prefix):
        self.__prefix = prefix

        self.update((
            ('prefix',      prefix),
            ('bin',         os.path.join(prefix, 'bin')),
            ('sbin',        os.path.join(prefix, 'sbin')),
            ('include',     os.path.join(prefix, 'include')),
            ('lib',         os.path.join(prefix, 'lib')),
            ('share',       os.path.join(prefix, 'share')),
            ('man',         os.path.join(prefix, 'share', 'man')),
            ('pkgconfig',   os.path.join(prefix, 'lib', 'pkgconfig')),
            ('tmp',         os.path.join(prefix, 'tmp')),
        ))

    def create(self, fail_if_it_exists=True):
        """Create environment directories.
        """
        LOGGER.debug('Creating environment directories at %s', self.__prefix)
        for directory in sorted(self.values()):
            mkdir(directory, fail_if_it_exists)
        LOGGER.debug('Environment directories %s created', self.__prefix)


class EnvironmentVariables(dict):
    """Environment variables of an ipkg environment.
    """
    def __init__(self, directories, defaults=os.environ):

        self.__directories = directories

        if isinstance(defaults, dict) or \
           defaults is os.environ:
            defaults = dict(defaults)
        else:
            defaults = {}

        if 'MANPATH' not in defaults:
            defaults['MANPATH'] = '/usr/share/man'

        var_models = {
            PathListVariable: ['PATH', 'PKG_CONFIG_PATH',
                               'MANPATH', 'C_INCLUDE_PATH'],
            #ArgumentListVariable: ['LDFLAGS', 'CFLAGS', 'CXXFLAGS'],
        }

        if Platform.current().os_name == 'osx':
            dyn_lib_var_name = 'DYLD_LIBRARY_PATH'
        else:
            dyn_lib_var_name = 'LD_LIBRARY_PATH'
        var_models[PathListVariable].append(dyn_lib_var_name)

        variables = {}
        for baseclass, names in var_models.items():
            for name in names:
                default = defaults.get(name)
                variables[name] = baseclass(name, default)

        # Scan default variables for variables we don't have
        for name, value in defaults.items():
            if name not in variables:
                variables[name] = Variable(name, value)

        variables['IPKG_ENVIRONMENT'] = Variable('IPKG_ENVIRONMENT',
                                                 directories['prefix'])
        variables['TMPDIR'] = Variable('TMPDIR', directories['tmp'])
        variables['HOME'] = Variable('HOME', os.environ.get('HOME', '/'))
        shortname = os.path.split(os.path.realpath(directories['prefix']))[1]
        variables['PS1'] = Variable('PS1', '(%s)\h:\w\$ ' % shortname)
        variables['PATH'].insert(directories['bin'])
        variables['PATH'].insert(directories['sbin'])
        variables['C_INCLUDE_PATH'].insert(directories['include'])
        variables[dyn_lib_var_name].insert(directories['lib'])
        variables['MANPATH'].insert(directories['man'])
        variables['PKG_CONFIG_PATH'].insert(directories['pkgconfig'])
        #variables['LDFLAGS'].insert('-L%s' % directories['lib'])
        #variables['CFLAGS'].insert('-I%s' % directories['include'])
        #variables['CXXFLAGS'].insert('-I%s' % directories['include'])

        self.update(variables)

    def as_string_dict(self):
        result = {}
        for name, value in self.items():
            result[name] = str(value)
        return result

    def as_string(self, export=False):
        return '\n'.join('%s%s=%s' % ('export ' if export else '', n, v)
                         for n, v in self.items()) + '\n'

    def __str__(self):
        return self.as_string()

    def add(self, name, value=None):
        """Add an environment variable.
        """
        if isinstance(name, dict):
            variables = name
        else:
            variables = {name: value}

        for var_name, var_value in variables.items():
            try:
                var_value = var_value % self.__directories
            except KeyError:
                # invalid format string ?
                pass

            LOGGER.debug('Adding variable %s=%s', var_name, var_value)
            self[var_name] = Variable(var_name, var_value)


class Environment(object):
    """An ipkg environment.
    """

    def __init__(self, prefix, directories=None, variables=None):
        self.prefix = prefix
        self.directories = directories or EnvironmentDirectories(prefix)
        self.variables = variables or EnvironmentVariables(self.directories)

        # Load environment meta data
        meta_path = os.path.join(prefix, '.ipkg.meta')
        self.meta = DictFile(meta_path)

        # If packages are already installed,
        # add their custom environment variables
        if 'packages' in self.meta:
            for name, data in self.meta['packages'].items():
                if 'envvars' in data and data['envvars'] is not None:
                    self.variables.add(data['envvars'])
        else:
            self.meta['packages'] = {}

        if 'config' not in self.meta:
            self.meta['config'] = {}

    def __repr__(self):
        return 'Environment("%s")' % self.prefix

    def execute(self, command,
                stdin=sys.stdin, stdout=sys.stdout, stderr=sys.stderr,
                cwd=None, data=None):
        """Execute a command in the environment.
        """
        return execute(command, stdin, stdout, stderr, cwd, data,
                       self.variables.as_string_dict())

    def mktmpdir(self, prefix=None):
        """Create a temporary directory.

           It will be stored in the environment ``tmp`` sub-directory.
        """
        return tempfile.mkdtemp(prefix=prefix, dir=self.directories['tmp'])

    def cleanup_tmpdir(self):
        """Remove then re-create the temporary files directory.
        """
        tmpdir = self.directories['tmp']
        shutil.rmtree(tmpdir)
        mkdir(tmpdir)

    def uninstall(self, package):
        """Uninstall a package.
        """
        if package not in self.meta['packages']:
            raise NotInstalled(package)

        LOGGER.info('Uninstalling %s', package)

        for rel_path in self.meta['packages'][package]['files']:
            path = os.path.join(self.prefix, rel_path)

            if os.path.isfile(path) or os.path.islink(path):
                #LOGGER.debug('Removing file %s', path)
                os.unlink(path)
                parent = os.path.dirname(path)
                if not os.listdir(parent):
                    #LOGGER.debug('Parent directory %s is empty, removing it',
                    #             parent)
                    os.rmdir(parent)
            else:
                LOGGER.debug('Ignoring %s', path)

        # Remove package from environment meta data
        self.meta['packages'].pop(package)
        self.meta.save()

        LOGGER.info('Package %s uninstalled', package)

    def install(self, package, repository=None):
        """Install a package.
        """
        LOGGER.info('Installing %s', package)

        if isinstance(package, basestring):

            if os.path.isfile(package):
                package = PackageFile(package)

            else:
                # If it does not exist, and this environment has a repository,
                # try to find it using the repository.
                if repository is None:
                    raise IpkgException('Cannot find package %s' % package)
                else:
                    package = repository[package]

        if not isinstance(package, MetaPackage):
            raise IpkgException('Invalid package: %r' % package)

        # Check if the package is already installed
        for installed_package in self.meta['packages'].values():
            if installed_package['name'] == package.name:
                # Package already installed
                if installed_package['version'] == package.version and \
                   installed_package['revision'] == package.revision:
                    # Same version/revision, just warn
                    LOGGER.warning('Package %(name)s %(version)s %(revision)s'
                                   ' is already installed' % package.meta)
                    return
                else:
                    # Different version/revision, uninstall it
                    LOGGER.debug('Another version of %r is installed, '
                                 'uninstalling it first' % package)
                    self.uninstall(package)
                break

        # Install dependencies
        if package.dependencies:
            for dependency in package.dependencies:
                if dependency not in self.meta['packages']:
                    LOGGER.info('Installing dependency: %s', dependency)
                    self.install(dependency, repository)

        package.extract(self.prefix)

        # Rewrite files prefix if this environment prefix is different than
        # package build prefix.
        isfile, islink = os.path.isfile, os.path.islink
        build_prefix = package.meta['build_prefix']
        if build_prefix != self.prefix:
            LOGGER.debug('Rewriting prefix in binaries and scripts')
            for pkg_file in package.meta['files']:
                file_dir, file_name = os.path.split(pkg_file)
                if file_dir in ('bin', 'sbin') or file_dir.startswith('lib'):
                    file_path = os.path.join(self.prefix, pkg_file)
                    if isfile(file_path) and not islink(file_path):
                        rewrite_prefix(pkg_file, build_prefix, self.prefix)

        # Write package meta data in environment
        self.meta['packages'][package.name] = package.meta
        self.meta.save()

        # Load package custom environment variables
        if package.envvars is not None:
            self.variables.add(package.envvars)

        LOGGER.info('Package %s installed', make_package_spec(package))

    @property
    def packages(self):
        return map(MetaPackage, self.meta['packages'].values())

    def get_config(self, key):
        return self.meta['config'].get(key)

    def set_config(self, key, value):
        self.meta['config'][key] = value
        self.meta.save()
