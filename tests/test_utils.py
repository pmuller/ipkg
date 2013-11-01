from unittest import TestCase
from tempfile import mkdtemp
from shutil import rmtree
from os.path import join, dirname
from os import listdir
import json

from ipkg.utils import DictFile, execute, make_package_spec, InvalidPackage, \
    PIPE, ExecutionFailed, InvalidDictFileContent, unarchive, which


DATA_DIR = join(dirname(__file__), 'data')


class TempDirTest(TestCase):

    def setUp(self):
        self.tmpdir = mkdtemp()

    def tearDown(self):
        rmtree(self.tmpdir)


class TestDictFile(TempDirTest):

    def setUp(self):
        TempDirTest.setUp(self)
        self.filepath = join(self.tmpdir, 'foo.json')

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
        self.assertRaises(InvalidDictFileContent, DictFile, self.filepath)

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


class TestExecute(TestCase):

    def test(self):
        execute('echo -n')

    def test_get_stdout_as_string(self):
        out = execute('echo 42', stdout=PIPE)[0]
        self.assertEqual(out, '42\n')

# FIXME: Why does it fails?!
#    def test_get_stderr_as_string(self):
#        err = execute('echo 42', stderr=PIPE)
#        self.assertEqual(err, '42\n')

    def test_exit_code_not_0(self):
        self.assertRaises(ExecutionFailed,
            execute, 'ls /I-HOPE-THIS-FILE-WILL-NEVER-EXISTS', stderr=PIPE)

    def test_command_not_found(self):
        self.assertRaises(ExecutionFailed,
            execute, 'I-HOPE-THIS-COMMAND-WILL-NEVER-EXISTS', stderr=PIPE)

    def test_with_data(self):
        out = execute('cat', data='42', stdout=PIPE)[0]
        self.assertEqual(out, '42')

    def test_with_env(self):
        out = execute(['sh', '-c', 'echo $FOO'],
                      env={'FOO': '42'}, stdout=PIPE)[0]
        self.assertEqual(out, '42\n')


class TestMakePackageSpec(TestCase):

    SAMPLE = {'name': 'foo', 'version' : '1.0', 'revision': 1}

    def test_package_like_obj(self):
        obj = type('foo', (object,), self.SAMPLE)()
        self.assertEqual(make_package_spec(obj), 'foo==1.0:1')

    def test_dict_full(self):
        self.assertEqual(make_package_spec(self.SAMPLE), 'foo==1.0:1')

    def test_dict_name_only(self):
        self.assertEqual(make_package_spec({'name': 'foo'}), 'foo')

    def test_dict_name_version(self):
        spec = make_package_spec({'name': 'foo', 'version': '1.0'})
        self.assertEqual(spec, 'foo==1.0')

    def test_dict_empty(self):
        self.assertRaises(InvalidPackage, make_package_spec, {})

    def test_bad_obj_type(self):
        self.assertRaises(InvalidPackage, make_package_spec, None)


class TestWhich(TestCase):

    def test(self):
        self.assertEqual(which('ls'), '/bin/ls')


class TestUnarchive(TempDirTest):

    DATA_BASE = 'foo-1.0'

    def test_tar_gz(self):
        self._test('.tar.gz')

    def test_tar_bz2(self):
        self._test('.tar.bz2')

    def test_zip(self):
        self._test('.zip')

    def _test(self, extension):
        f = open(join(DATA_DIR, self.DATA_BASE + extension))
        unarchive(f, self.tmpdir)
        dirlist = listdir(self.tmpdir)
        self.assertEqual(len(dirlist), 1)
        self.assertEqual(dirlist[0], self.DATA_BASE)
        self.assertEqual(
            open(join(self.tmpdir, self.DATA_BASE, 'README')).read(),
            open(join(DATA_DIR, self.DATA_BASE, 'README')).read())
