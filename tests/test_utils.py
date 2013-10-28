from unittest import TestCase
from tempfile import mkdtemp
from shutil import rmtree
from os.path import join
import json

from ipkg.utils import DictFile, InvalidDictFileContent


class TestDictFile(TestCase):

    def setUp(self):
        self.tmpdir = mkdtemp()
        self.filepath = join(self.tmpdir, 'foo.json')

    def tearDown(self):
        rmtree(self.tmpdir)

    def test_not_existing(self):
        self.assertEqual(DictFile(self.filepath), {})

    def test_existing(self):
        d = {'truth': 42}
        with open(self.filepath, 'w') as f:
            json.dump(d, f)
        self.assertEqual(DictFile(self.filepath), d)

    def test_empty(self):
        open(self.filepath, 'w').close()
        self.assertEqual(DictFile(self.filepath), {})

    def test_invalid_content(self):
        with open(self.filepath, 'w') as f:
            f.write('foo')
        with self.assertRaises(InvalidDictFileContent):
            DictFile(self.filepath)

    def test_clear(self):
        d = {'truth': 42}
        with open(self.filepath, 'w') as f:
            json.dump(d, f)
        df = DictFile(self.filepath)
        df.clear()
        # Ensure its empty
        self.assertEqual(df, {})
        # Ensure its empty, even if we re-read the file from the filesystem
        self.assertEqual(DictFile(self.filepath), {})

    def test_save(self):
        df1 = DictFile(self.filepath)
        df1['truth'] = 42
        df1.save()
        df2 = DictFile(self.filepath)
        self.assertEqual(df2['truth'], 42)
