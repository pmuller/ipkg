from unittest import TestCase

from ipkg.environments import Variable, InvalidVariableValue, PathListVariable


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
