from unittest import TestCase

from ipkg.exceptions import IpkgException


class TestIpkgException(TestCase):

    def test_str(self):

        self.assertEqual(str(IpkgException()), '')
        self.assertEqual(str(IpkgException('a')), "('a',)")

        class A(IpkgException):
            MESSAGE = 'Foo'
        self.assertEqual(str(A()), 'Foo')
        self.assertEqual(str(A('a')), 'Foo')
