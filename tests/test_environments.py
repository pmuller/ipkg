from unittest import TestCase

from ipkg.environments import Variable, InvalidVariableValue


class TestVariable(TestCase):

    def test(self):
        var = Variable('foo', '42')
        self.assertEqual(var.value, '42')
        self.assertEqual(str(var), "foo='42'")
