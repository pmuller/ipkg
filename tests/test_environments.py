from os.path import isdir, join, dirname, exists
from shutil import rmtree
from tempfile import mkdtemp
from unittest import TestCase

from ipkg.repositories import PackageRepository
from ipkg.environments import Variable, InvalidVariableValue, \
    PathListVariable, EnvironmentDirectories, EnvironmentVariables, \
    Environment


DATA_DIR = join(dirname(__file__), 'data')
FORMULA_DIR = join(DATA_DIR, 'formulas')
PACKAGE_DIR = join(DATA_DIR, 'packages')


class TestVariable(TestCase):

    def test(self):
        var = Variable('foo', '42')
        self.assertEqual(str(var), '42')


class TestPathListVariable(TestCase):

    def test_set(self):
        var = PathListVariable('foo')
        self.assertEqual(str(var), '')
        var.set('/bin:/sbin')
        self.assertEqual(str(var), '/bin:/sbin')
        self.assertRaises(InvalidVariableValue, var.set, 42)

    def test_remove(self):
        var = PathListVariable('foo', '/bin:/sbin:/usr/local/bin')
        var.remove('/sbin')
        self.assertEqual(str(var), '/bin:/usr/local/bin')

    def test_insert(self):
        var = PathListVariable('foo', '/a:/b:/c')
        var.insert('/1')
        var.insert('/2', 1)
        self.assertEqual(str(var), '/1:/2:/a:/b:/c')

    def test_append(self):
        var = PathListVariable('foo', '/a:/b')
        var.append('/c')
        self.assertEqual(str(var), '/a:/b:/c')


class TestEnvironmentDirectories(TestCase):

    def setUp(self):
        self.tmpdir = mkdtemp()

    def tearDown(self):
        rmtree(self.tmpdir)

    def test(self):
        env_dir = join(self.tmpdir, 'env')
        EnvironmentDirectories(env_dir).create()
        self.assertTrue(isdir(env_dir))
        self.assertTrue(isdir(join(env_dir, 'bin')))


class TestEnvironmentVariables(TestCase):

    def setUp(self):
        self.env = '/foo'
        self.directories = EnvironmentDirectories(self.env)
        self.variables = EnvironmentVariables(self.directories, defaults=None)

    def test_IPKG_ENVIRONMENT(self):
        self.assertTrue('IPKG_ENVIRONMENT' in self.variables)
        self.assertEqual(str(self.variables['IPKG_ENVIRONMENT']), self.env)

    def test_add(self):
        self.variables.add('BAR', '%(prefix)s/bar')
        self.assertEqual(str(self.variables['BAR']), '/foo/bar')


class TestEnvironment(TestCase):

    def setUp(self):
        self.tmpdir = mkdtemp()
        self.prefix = join(self.tmpdir, 'env')
        self.env = Environment(self.prefix)
        self.env.directories.create()

    def tearDown(self):
        rmtree(self.tmpdir)

    def test_uninstall(self):
        self.test_install_file()
        self.env.uninstall('foo')
        readme = join(self.prefix, 'foo.README')
        self.assertFalse(exists(readme))

    def test_install_file(self):
        filepath = join(PACKAGE_DIR, 'foo/foo-1.0-1-osx-10.8.4-x86_64.ipkg')
        self.env.install(filepath)
        readme = join(self.prefix, 'foo.README')
        self.assertEqual(open(readme).read(), 'Hello world\n')

    def test_install_repository(self):
        repository = PackageRepository(PACKAGE_DIR)
        self.env.install('osx-10.8.4-x86_64:foo', repository)
        readme = join(self.prefix, 'foo.README')
        self.assertEqual(open(readme).read(), 'Hello world\n')

    def test_install_dependencies(self):
        repository = PackageRepository(PACKAGE_DIR)
        self.env.install('osx-10.8.4-x86_64:foo-bar', repository)
        # From 'foo'
        readme = join(self.prefix, 'foo.README')
        self.assertEqual(open(readme).read(), 'Hello world\n')
        # From 'bar'
        readme = join(self.prefix, 'bar.README')
        self.assertEqual(open(readme).read(), 'bar\n')
        # From 'foo-bar'
        readme = join(self.prefix, 'foo-bar.README')
        self.assertEqual(open(readme).read(), 'foo-bar\n')
