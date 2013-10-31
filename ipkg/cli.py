import os
import sys
import argparse
import logging
import types
import pkg_resources

from . import packages, repositories
from .environments import current, Environment
from .exceptions import IpkgException
from .build import Formula


LOGGER = logging.getLogger(__name__)


class Ipkg(object):
    """ipkg CLI tool.
    """
    def __init__(self):
        self.parser = parser = argparse.ArgumentParser()
        parser.add_argument('--debug', '-D',
                            action='store_true', default=False,
                            help='Show debug messages.')
        parser.add_argument('--version', action='version',
                            version=pkg_resources.require('ipkg')[0].version)
        self.subparsers = parser.add_subparsers()

    def __call__(self):
        """Run ipkg.
        """
        args = self.parser.parse_args().__dict__
        func = args.pop('func')
        debug = args.pop('debug')

        log_level = logging.DEBUG if debug else logging.INFO
        logger = logging.getLogger('ipkg')
        logger.setLevel(log_level)
        handler = logging.StreamHandler()
        if debug:
            msg_format = '%(asctime)s.%(msecs)03d:%(levelname)s:' \
                         '%(name)s:%(message)s'
            time_format = '%H:%M:%S'
            formatter = logging.Formatter(msg_format, time_format)
            handler.setFormatter(formatter)
        logger.addHandler(handler)

        try:
            if func.func_name not in ('build', 'build_repository'):
                if 'env' in args and args['env'] is None:
                    args['env'] = current()
            func(**args)
        except IpkgException as exception:
            if debug:
                LOGGER.exception(exception)
            else:
                LOGGER.error('Error: %s' % exception)
            raise SystemExit(-1)

    def command(self, arg_or_func=None, *args):
        """Register an ipkg command.

        Usages::

            @command
            def foo():
                pass

            @command('foo-bar')
            def foo_bar():
                pass

            @command(Argument(), Argument())
            def foo():
                pass

            @command('foo-bar', Argument())
            def foo_bar():
                pass
        """
        command_args = args

        # Used by commands without arguments
        if type(arg_or_func) == types.FunctionType:
            func = arg_or_func
            cmd_parser = self.subparsers.add_parser(func.func_name,
                                                    help=func.__doc__)
            cmd_parser.set_defaults(func=func)
            return func

        # Used by commands with arguments
        else:
            def wrapper(func):
                if arg_or_func:

                    # If the first argument is a str object,
                    # use it as the command name.
                    if isinstance(arg_or_func, str):
                        func_name = arg_or_func
                        args = command_args
                    else:
                        func_name = func.func_name
                        args = (arg_or_func,) + command_args

                    # Create the sub command parser
                    cmd_parser = self.subparsers.add_parser(func_name,
                                                            help=func.__doc__)
                    cmd_parser.set_defaults(func=func)

                    # Add its arguments
                    for arg in args:
                        cmd_parser.add_argument(*arg.args, **arg.kw)

                else:
                    # Used when the decorated is used that way :
                    #   @ipkg.command()
                    #   def foo(): pass
                    cmd_parser = self.subparsers.add_parser(func.func_name,
                                                            help=func.__doc__)
                    cmd_parser.set_defaults(func=func)

                return func

            return wrapper


ipkg = Ipkg()


class Argument(object):
    """An ipkg command argument.
    """
    def __init__(self, *args, **kw):
        self.args = args
        self.kw = kw


@ipkg.command(
    'list',
    Argument('--environment', '-e',
             metavar='ENV', type=Environment,
             help='The environment in which the package will be installed.'),
)
def list_packages(environment):
    """List installed packages.
    """
    for package in environment.packages:
        print package


@ipkg.command(
    Argument('--environment', '-e',
             metavar='ENV', type=Environment,
             help='The environment in which the package will be installed.'),
    Argument('--repository', '-r',
             metavar='URL', type=repositories.PackageRepository,
             help='Use a repository to find the package'),
    Argument('package', metavar='PKG'),
)
def install(environment, package, repository):
    """Install a package."""
    environment.install(package, repository)


@ipkg.command(
    Argument('--environment', '-e',
             metavar='ENV', type=Environment,
             help='The environment from which the '
                  'package will be uninstalled.'),
    Argument('package', metavar='PKG'),
)
def uninstall(environment, package):
    """Uninstall a package.
    """
    environment.uninstall(package)


@ipkg.command(
    Argument('environment',
             metavar='ENV', type=Environment,
             help='Path of the environment.'),
)
def mkenv(environment):
    """Create an environment.
    """
    environment.directories.create()


@ipkg.command(
    Argument('--export', '-x', action='store_true', default=False,
             help='Prefix variables with the export keyword.'),
    Argument('environment',
             metavar='ENV', type=Environment,
             help='Path of the environment.')
)
def printenv(environment, export):
    """Show the environment variables of an ipkg environment.
    """
    sys.stdout.write(environment.variables.as_string(export))


@ipkg.command(
    'exec',
    Argument('environment',
             metavar='ENV', type=Environment,
             help='Path of the environment.'),
    Argument('command', metavar='COMMAND', help='Path of the executable.'),
    Argument('arguments', metavar='ARG', nargs='*', help='Command arguments.'),
)
def execute(environment, command, arguments):
    """Run a command in an environment.
    """
    command = [command]
    command.extend(arguments)
    environment.execute(command)


@ipkg.command(
    Argument('--shell', '-s',
             default='/bin/bash',
             help='Shell executable (Default: "%(default)s")'),
    Argument('environment',
             metavar='ENV', type=Environment,
             help='Path of the environment.'),
)
def shell(environment, shell):
    """Launch an interactive shell."""
    environment.execute(shell)


@ipkg.command(
    Argument('--environment', '-e',
             metavar='ENV', type=Environment,
             help='The environment in which the '
                  'package will be built.'),
    Argument('--repository', '-r',
             metavar='URL', type=repositories.PackageRepository,
             help='Use a repository to find the dependencies.'),
    Argument('--package-dir', '-p',
             metavar='DIR', default=os.getcwd(),
             help='Where to store the package. Default: current directory.'),
    Argument('--keep-build-dir', '-k',
             action='store_false', default=True, dest='remove_build_dir',
             help="Don't remove the build directory."),
    Argument('--update-repository', '-u',
             action='store_true', default=False,
             help='Add the newly built package to the repository. '
                  'Only works with local repositories.'),
    Argument('--verbose', '-v',
             action='store_true', default=False,
             help='Show commands output.'),
    Argument('build_file',
             help='A python module which contains a Formula class.'),
)
def build(build_file, environment, verbose, repository, package_dir,
          remove_build_dir, update_repository):
    """Build a package.
    """
    formula = Formula.from_file(build_file)(environment, verbose)

    if update_repository:
        repository = repositories.LocalPackageRepository(repository.base)
        repository.build_formula(formula, remove_build_dir)
    else:
        formula.build(package_dir, remove_build_dir, repository)


@ipkg.command(
    Argument('repository',
             metavar='PATH', type=repositories.LocalPackageRepository,
             help='Path of the repository.'),
)
def mkrepo(repository):
    repository.update_metadata()


@ipkg.command(
    'build-repository',
    Argument('--environment', '-e',
             metavar='ENV', type=Environment,
             help='The environment in which the '
                  'packages will be built.'),
    Argument('--verbose', '-v',
             action='store_true', default=False,
             help='Show commands output.'),
    Argument('package_repository',
             type=repositories.LocalPackageRepository,
             help='Path of the repository.'),
    Argument('formula_repository',
             type=repositories.FormulaRepository,
             help='Path of the formulas.'),
)
def build_repository(environment, verbose,
                     package_repository, formula_repository):
    """Build all formulas and store them in a repository.
    """
    new_packages = package_repository.build_formulas(formula_repository,
                                                     environment, verbose)
    if new_packages:
        LOGGER.info('New packages:')
        for package_file in new_packages:
            filename = os.path.basename(package_file)
            LOGGER.info(filename)
    else:
        LOGGER.info('Repository is up to date')


if __name__ == '__main__':
    ipkg()
