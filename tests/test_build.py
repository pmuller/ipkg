from unittest import TestCase
from os.path import isdir, join, dirname, exists
from shutil import rmtree
from tempfile import mkdtemp
from tarfile import open as taropen
import json

from ipkg.repositories import PackageRepository
from ipkg.build import Formula


DATA_DIR = join(dirname(__file__), 'data')
FORMULA_DIR = join(DATA_DIR, 'formulas')
PACKAGE_DIR = join(DATA_DIR, 'packages')


class TestFormula(TestCase):

    def setUp(self):
        self.tmpdir = mkdtemp()

    def tearDown(self):
        rmtree(self.tmpdir)

    def test_from_file(self):
        formula_file = join(FORMULA_DIR, 'foo/foo-1.0.py')
        formula_cls = Formula.from_file(formula_file)
        self.assertTrue(issubclass(formula_cls, Formula))

    def test_build(self):
        formula_file = join(FORMULA_DIR, 'foo/foo-1.0.py')
        formula_cls = Formula.from_file(formula_file)
        formula = formula_cls()
        package_file = formula.build(self.tmpdir)
        f = taropen(package_file)
        meta = json.load(f.extractfile('.ipkg.meta'))
        self.assertEqual(meta['name'], 'foo')

    # FIXME: This test works on my mac, 
    # but fails on travis because there are no linux packages in the test data
#    def test_build_dependencies(self):
#        formula_file = join(FORMULA_DIR, 'foo-bar/foo-bar-1.0-1.py')
#        formula_cls = Formula.from_file(formula_file)
#        formula = formula_cls()
#        repository = PackageRepository(PACKAGE_DIR)
#        package_file = formula.build(self.tmpdir, True, repository)
#        f = taropen(package_file)
#        meta = json.load(f.extractfile('.ipkg.meta'))
#        self.assertEqual(meta['name'], 'foo-bar')
