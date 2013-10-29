import sys
import os
import stat
import time
import logging
import shutil
import subprocess
import errno
import tempfile
import shutil
import bz2
import json
import platform

from .exceptions import IpkgException
from .packages import BasePackage, InstalledPackage, PackageFile
from .prefix_rewriters import rewrite_prefix
from .utils import DictFile, execute, make_package_spec, mkdir
from .compat import basestring


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


class Variable(object):
    """An environment variable with free text value.
    """
    def __init__(self, name, value=None):
        self.name = name
        self.set(value)

    def set(self, value):
        if isinstance(value, basestring):
            self.__value = value
        else:
            raise InvalidVariableValue(self.name, value)

    @property
    def value(self):
        return self.__value

    def __str__(self):
        return "%s='%s'" % (self.name, self.value)


def in_env():
    return 'IPKG_ENVIRONMENT' in os.environ


def current():
    if in_env():
        return Environment(os.environ['IPKG_ENVIRONMENT'])
    else:
        raise UnknownEnvironment()


class ListVariable(Variable):
    """Base class for environment variables using a list of values as a value.

    Sub classes just have to override the LIST_SEPARATOR attribute.
    """
    LIST_SEPARATOR = None

    def set(self, value):
        if value is None:
            self.__paths = []
        elif isinstance(value, basestring):
            self.__paths = value.split(self.LIST_SEPARATOR)
        else:
            raise InvalidVariableValue(self.name, value)

    def remove(self, path):
        if path in self.__paths:
            path_index = self.__paths.index(path)
            self.__paths.pop(path_index)

    def insert(self, path, index=0):
        self.remove(path)
        self.__paths.insert(index, path)

    def append(self, path):
        self.remove(path)
        self.__paths.append(path)

    @property
    def value(self):
        return self.LIST_SEPARATOR.join(self.__paths)


class PathListVariable(ListVariable):
    """This represents an environment variable whose value is a path list.
    """
    LIST_SEPARATOR = ':'


#class ArgumentListVariable(ListVariable):
#    """A list of strings"""
#    LIST_SEPARATOR = ' '


class Environment(object):
    """An ipkg environment.
    """

    def __init__(self, prefix, default_variables=os.environ):
        self.prefix = prefix

        directories = dict((
            ('env', self.prefix),
            ('bin', os.path.join(prefix, 'bin')),
            ('sbin', os.path.join(prefix, 'sbin')),
            ('include', os.path.join(prefix, 'include')),
            ('lib', os.path.join(prefix, 'lib')),
            #('lib64', os.path.join(prefix, 'lib64')),
            ('share', os.path.join(prefix, 'share')),
            ('man', os.path.join(prefix, 'share', 'man')),
            ('pkgconfig', os.path.join(prefix, 'lib', 'pkgconfig')),
            #('pkgconfig_64', os.path.join(prefix, 'lib64', 'pkgconfig')),
            ('tmp', os.path.join(prefix, 'tmp')),
        ))
        self.directories = directories

        if isinstance(default_variables, dict) or \
           default_variables is os.environ:
            default_variables = dict(default_variables)
        else:
            default_variables = {}
        
        if 'MANPATH' not in default_variables:
            default_variables['MANPATH'] = '/usr/share/man'

        var_models = {
            PathListVariable: ['PATH', 'PKG_CONFIG_PATH',
                               'MANPATH', 'C_INCLUDE_PATH'],
            #ArgumentListVariable: ['LDFLAGS', 'CFLAGS', 'CXXFLAGS'],
        }

        if self.os_name == 'osx':
            dyn_lib_var_name = 'DYLD_LIBRARY_PATH'
        else:
            dyn_lib_var_name = 'LD_LIBRARY_PATH'
        var_models[PathListVariable].append(dyn_lib_var_name)

        variables = {}
        for baseclass, variable_names in var_models.items():
            for variable in variable_names:
                default = default_variables.get(variable)
                variables[variable] = baseclass(variable, default)

        for name, value in default_variables.items():
            if name not in variables:
                variables[name] = Variable(name, value)

        variables['IPKG_ENVIRONMENT'] = Variable('IPKG_ENVIRONMENT',
                                                 self.prefix)
        variables['TMPDIR'] = Variable('TMPDIR', directories['tmp'])
        variables['HOME'] = Variable('HOME', os.environ.get('HOME', '/'))
        ps1 = '(%s)\h:\w\$ ' % os.path.split(os.path.realpath(self.prefix))[1]
        variables['PS1'] = Variable('PS1', ps1)
        variables['PATH'].insert(directories['bin'])
        variables['PATH'].insert(directories['sbin'])
        variables['C_INCLUDE_PATH'].insert(directories['include'])
        #variables['LD_LIBRARY_PATH'].insert(directories['lib64'])
        variables[dyn_lib_var_name].insert(directories['lib'])
        variables['MANPATH'].insert(directories['man'])
        #variables['PKG_CONFIG_PATH'].insert(directories['pkgconfig_64'])
        variables['PKG_CONFIG_PATH'].insert(directories['pkgconfig'])
        #variables['LDFLAGS'].insert('-L%s' % directories['lib64'])
        #variables['LDFLAGS'].insert('-L%s' % directories['lib'])
        #variables['CFLAGS'].insert('-I%s' % directories['include'])
        #variables['CXXFLAGS'].insert('-I%s' % directories['include'])
        self.variables = variables

        # Load environment meta data
        meta_path = os.path.join(prefix, '.ipkg.meta')
        self.meta = DictFile(meta_path)
        # If packages are already installed,
        # add their custom environment variables
        if 'packages' in self.meta:
            for name, data in self.meta['packages'].items():
                if 'envvars' in data:
                    self.__add_package_envvars(data['envvars'])
        else:
            self.meta['packages'] = {}

    def __str__(self):
        return self.variables_string()

    def __repr__(self):
        return 'Environment("%s")' % self.prefix

    def variables_dict(self):
        result = {}
        for k, v in self.variables.items():
            result[k] = v.value
        return result

    def variables_string(self, export=False):
        return '\n'.join('%s%s' % ('export ' if export else '', var)
                         for var in self.variables.values()) + '\n'

    def execute(self, command,
                stdin=sys.stdin, stdout=sys.stdout, stderr=sys.stderr,
                cwd=None, data=None):
        """Execute a command in the environment.
        """
        env_dict = self.variables_dict()
        return execute(command, stdin, stdout, stderr, cwd, data, env_dict)

    def create_directories(self, fail_if_it_exist=True):
        """Create ipkg environment directories.
        """
        LOGGER.debug('Creating environment directories at %s', self.prefix)
        for directory in self.directories.values():
            mkdir(directory, fail_if_it_exist)
        LOGGER.debug('Environment directories %s created', self.prefix)

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
            if os.path.exists(package):
                # If package is a string and exists on the filesystem,
                # use it
                package = PackageFile(package)
            else:
                # If it does not exist, and this environment has a repository,
                # try to find it using the repository.
                if repository is None:
                    raise IpkgException('Cannot find package %s' % package)
                else:
                    package = repository.find(package,
                                              os_name=self.os_name,
                                              os_release=self.os_release,
                                              arch=self.arch)

        elif not isinstance(package, BasePackage):
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
        if hasattr(package, 'envvars'):
            self.__add_package_envvars(package.envvars)

        LOGGER.info('Package %s installed', make_package_spec(package))

    def __add_package_envvars(self, envvars):
        """Load package custom environment variables."""
        if isinstance(envvars, dict):
            for name, value in envvars.items():
                value = self.render_arg(value)
                LOGGER.debug('Adding variable %s=%s', name, value)
                self.variables[name] = Variable(name, value)

    @property
    def os_release(self):
        """The OS release of the OS running the environment.
        """
        system = platform.system()
        if system == 'Linux':
            _, release, _ = platform.dist()
        elif system == 'Darwin':
            release = platform.mac_ver()[0]
        else:
            raise UnknownSystem(system)
        return release

    @property
    def os_name(self):
        """Return the OS name for the environment.

        Currently only supports Linux distributions and Mac OS X.

        Linux distribution names: ???
        Mac OS X name: ``osx``
        """
        system = platform.system()
        if system == 'Linux':
            name, _, _ = platform.dist()
        elif system == 'Darwin':
            name = 'osx'
        else:
            raise UnknownSystem(system)
        return name

    @property
    def arch(self):
        """The environment architecture. eg ``x86_64``.
        """
        return platform.machine()

    @property
    def platform(self):
        """The platform running the environment.
           A string formatted as ``os_name-os_release-arch``.
        """
        return '%s-%s-%s' % (self.os_name, self.os_release, self.arch)

    @property
    def packages(self):
        return map(InstalledPackage, self.meta['packages'].values())

    def render_arg(self, arg):
        """Render a string, replacing environment directories path."""
        dirs = {}
        for k, v in self.directories.items():
            dirs[k + '_dir'] = v
        return arg % dirs
