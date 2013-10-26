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
from collections import OrderedDict

from .exceptions import IpkgException
from .packages import BasePackage, InstalledPackage, PackageFile
from .prefix_rewriters import rewrite_prefix


LOGGER = logging.getLogger(__name__)


class UnknownEnvironment(IpkgException):
    """No environment loaded.
    """
    def __str__(self):
        return self.__doc__.strip()


class ExecutionFailed(IpkgException):
    """A command failed to run.
    """
    def __init__(self, command, reason):
        self.command = command
        self.reason = reason

    def __str__(self):
        return 'Cannot execute %s: %s' % (self.command, self.reason)


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
        self.__name = name
        self.set(value)

    def set(self, value):
        if isinstance(value, basestring):
            self.__value = value
        else:
            raise InvalidVariableValue(name, value)

    @property
    def value(self):
        return self.__value

    def __str__(self):
        return "%s='%s'" % (self.__name, self.value)


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
            raise InvalidVariableValue(name, value)

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
            with open(self.__file_path) as f:
                self.update(json.load(f))

    def save(self):
        LOGGER.debug('Writing %s', self.__file_path)
        with open(self.__file_path, 'w') as f:
            json.dump(self, f, indent=4)


class Environment(object):
    """An ipkg environment.
    """

    def __init__(self, prefix, default_variables=os.environ):
        self.prefix = prefix

        directories = OrderedDict((
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
        variables['PS1'] = Variable('PS1',
                                    '(%s)\h:\w\$ ' % os.path.split(self.prefix)[1])
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

    def variables_dict(self):
        return {k: v.value for k, v in self.variables.items()}

    def variables_string(self, export=False):
        return '\n'.join('%s%s' % ('export ' if export else '', var)
                         for var in self.variables.values()) + '\n'

    def execute(self, command, arguments=None,
                stdin=sys.stdin, stdout=sys.stdout, stderr=sys.stderr,
                cwd=None, data=None):
        """Execute a command in the environment.
        """
        LOGGER.debug('execute(command="%s", arguments=%s, stdin=%s, '
                     'stdout=%s, stderr=%s, cwd="%s")' %
                     (command, arguments,
                      stdin, stdout, stderr, cwd))
        arguments = arguments or []

        kw = {'cwd': cwd,
              'env': self.variables_dict()}
        if data is None:
            if stdin:
                kw['stdin'] = stdin
        else:
            kw['stdin'] = subprocess.PIPE
        if stdout:
            kw['stdout'] = stdout
        if stderr:
            kw['stderr'] = stderr

        try:
            process = subprocess.Popen([command] + list(arguments), **kw)

        except OSError as exception:
            if exception.errno == errno.ENOENT:
                error = 'Command not found'
            else:
                error = exception.strerror
            raise ExecutionFailed(command, error)

        process.communicate(data)
        process.wait()

        LOGGER.debug('Exited with code: %i', process.returncode)

        return process.returncode

    def create_directories(self, fail_if_it_exist=True):
        """Create ipkg environment directories."""
        LOGGER.info('Creating environment directories at %s', self.prefix)
        for directory in self.directories.values():
            mkdir(directory, fail_if_it_exist)
        LOGGER.info('Environment directories %s created', self.prefix)

    def mktmpdir(self, prefix=None):
        return tempfile.mkdtemp(prefix=prefix, dir=self.directories['tmp'])

    def cleanup_tmpdir(self):
        tmpdir = self.directories['tmp']
        shutil.rmtree(tmpdir)
        mkdir(tmpdir)

    def __repr__(self):
        return 'Environment("%s")' % self.prefix

    def get_package_meta_file(self, package):
        if isinstance(package, BasePackage):
            package = package.name
        return os.path.join(self.directories['ipkg_packages'], package)

    def get_package_meta(self, package):
        return json.loads(open(self.get_package_meta_file(package)).read())

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
                package = PackageFile(package)
            else:
                if repository is None:
                    raise IpkgException('Cannot find package %s' % package)
                else:
                    package = repository.find(package,
                                              os_name=self.os_name,
                                              os_release=self.os_release,
                                              arch=self.arch)

        for installed_package in self.meta['packages'].values():
            if installed_package['name'] == package.name:
                if installed_package['version'] == package.version and \
                   installed_package['revision'] == package.revision:
                    LOGGER.warning('Package %(name)s %(version)s %(revision)s'
                                   ' is already installed' % package.meta)
                    return
                else:
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

        LOGGER.debug('Rewriting prefix in binaries and scripts')
        for package_file in package.meta['files']:
            file_dir, file_name = os.path.split(package_file)
            if file_dir in ('bin', 'sbin') or file_dir.startswith('lib'):
                file_path = os.path.join(self.prefix, package_file)
                if os.path.isfile(file_path) and not os.path.islink(file_path):
                    rewrite_prefix(package_file, package.meta['build_prefix'],
                                   self.prefix)

        # Write package meta data in environment
        self.meta['packages'][package.name] = package.meta
        self.meta.save()

        if hasattr(package, 'envvars'):
            self.__add_package_envvars(package.envvars)

        LOGGER.info('Package %s %s %s installed', package.name,
                    package.version, package.revision)

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
        dirs = {k + '_dir': v for k, v in self.directories.items()}
        return arg % dirs


class CannotCreateDirectory(IpkgException):
    """Raised when a directory cannot be created"""
    def __init__(self, directory, reason):
        self.directory = directory
        self.reason = reason

    def __str__(self):
        return 'Cannot create directory %s: %s' % (self.directory,
                                                   self.reason)


def mkdir(directory, fail_if_it_exist=True):
    """Create a directory"""
    LOGGER.debug('Creating directory %s', directory)
    try:
        os.mkdir(directory)
    except OSError as exception:
        if exception.errno != errno.EEXIST or fail_if_it_exist:
            raise CannotCreateDirectory(directory, exception.strerror)


def in_env():
    return 'IPKG_ENVIRONMENT' in os.environ


def current():
    if in_env():
        return Environment(os.environ['IPKG_ENVIRONMENT'])
    else:
        raise UnknownEnvironment()
