from os.path import join, dirname, isfile
from os import mkdir
from shutil import rmtree, copyfile
from tempfile import mkdtemp
from unittest import TestCase
import json

from ipkg.packages import MetaPackage, PackageFile


DATA_DIR = join(dirname(__file__), 'data')
PACKAGE_DIR = join(DATA_DIR, 'packages')


class TestMetaPackage(TestCase):

    def test_str(self):
        self.assertEqual(
            str(MetaPackage({'version': '1.0',
                             'revision': '1', 'name': 'foo'})),
            'foo==1.0:1')


class TestPackageFile(TestCase):

    def setUp(self):
        self.tmpdir = mkdtemp()

    def tearDown(self):
        rmtree(self.tmpdir)

    def test_extract(self):
        pkg = PackageFile(join(PACKAGE_DIR,
                               'foo/foo-1.0-1-osx-10.8.4-x86_64.ipkg'))
        pkg.extract(self.tmpdir)
        readme = join(self.tmpdir, 'foo.README')
        self.assertTrue(isfile(readme))
        self.assertEqual(open(readme).read(), 'Hello world\n')
