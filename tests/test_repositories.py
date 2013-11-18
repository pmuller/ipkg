from os.path import join, dirname, isfile
from os import mkdir
from shutil import rmtree, copyfile
from tempfile import mkdtemp
from unittest import TestCase
import json

from ipkg.repositories import PackageRepository, LocalPackageRepository, \
    FormulaRepository
from ipkg.build import Formula


DATA_DIR = join(dirname(__file__), 'data')
PACKAGE_DIR = join(DATA_DIR, 'packages')
FORMULA_DIR = join(DATA_DIR, 'formulas')


class TestPackageRepository(TestCase):

    def setUp(self):
        self.repo = PackageRepository(PACKAGE_DIR)

    def test_find(self):
        package = self.repo.find('osx-10.8.4-x86_64:foo==1.0')
        self._check_package(package[0], 'foo', '1.0', '1')

    def test_find_without_version(self):
        package = self.repo.find('osx-10.8.4-x86_64:foo')
        self._check_package(package[0], 'foo', '1.0', '1')

    def _check_package(self, package, name, version, revision):
        self.assertEqual(package.name, name)
        self.assertEqual(package.version, version)
        self.assertEqual(package.revision, revision)

    def test_iter(self):
        self.assertEqual(
            [(p.name, p.version, p.revision) for p in self.repo],
            [(u'foo', u'1.0', u'1'),
             (u'bar', u'1.0', u'1'),
             (u'foo-bar', u'1.0', u'1')])


class TestLocalPackageRepository(TestCase):

    def setUp(self):
        self.tmpdir = mkdtemp()
        self.repo = LocalPackageRepository(self.tmpdir)
        self.meta_path = join(self.tmpdir, 'repository.json')

    def tearDown(self):
        rmtree(self.tmpdir)

    def test_update_metadata(self):
        mkdir(join(self.tmpdir, 'foo'))
        copyfile(join(PACKAGE_DIR, 'foo/foo-1.0-1-osx-10.8.4-x86_64.ipkg'),
                 join(self.tmpdir, 'foo/foo-1.0-1-osx-10.8.4-x86_64.ipkg'))
        self.repo.update_metadata()
        self.assertTrue(isfile(self.meta_path))
        meta = json.load(open(self.meta_path))
        self.assertEqual(meta.keys(), ['foo'])

    def test_build_formula(self):
        formula_file = join(FORMULA_DIR, 'foo/foo-1.0.py')
        formula = Formula.from_file(formula_file)()
        package_file = self.repo.build_formula(formula)
        meta = json.load(open(self.meta_path))
        self.assertTrue(meta.keys(), ['foo'])
        self.assertTrue(isfile(package_file))

    # This test need to be isolated because of new test formulas
    #
    #def test_build_formulas(self):
    #    formulas = FormulaRepository(FORMULA_DIR)
    #    package_files = self.repo.build_formulas(formulas)
    #    self.assertEqual(map(isfile, package_files), [True, True, True])
    #    meta = json.load(open(self.meta_path))
    #    self.assertTrue(meta.keys(), ['foo', 'bar', 'foo-bar'])


class TestFormulaRepository(TestCase):

    def test_iter(self):
        repo = FormulaRepository(FORMULA_DIR)
        packages = [(f.name, f.version, f.revision) for f in repo]
        self.assertTrue(('bar', '1.0', 1) in packages)
        self.assertTrue(('foo', '1.0', 1) in packages)
        self.assertTrue(('foo-bar', '1.0', 1) in packages)
