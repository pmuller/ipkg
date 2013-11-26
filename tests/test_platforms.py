from unittest import TestCase
import platform

from ipkg.platforms import Platform, InvalidPlatform


class TestPlatform(TestCase):

    def test_str(self):
        p = Platform('a', 'b', 'c')
        self.assertEqual(str(p), 'a-b-c')

    def test_eq(self):
        p = Platform('a', 'b', 'c')
        self.assertEqual('a-b-c', p)
        self.assertEqual(p, 'a-b-c')
        self.assertEqual('any', p)
        self.assertEqual(p, 'any')
        self.assertEqual('any-any-any', p)
        self.assertEqual(p, 'any-any-any')
        self.assertFalse(p == 'a-b')

    def test_ne(self):
        self.assertTrue(Platform('osx','10.9','x86_64') != 'osx-10.8-x86_64')

    def test_parse_any(self):
        p = Platform.parse('ANY')
        self.assertEqual(p.os_name, 'any')
        self.assertEqual(p.os_release, 'any')
        self.assertEqual(p.architecture, 'any')

    def test_parse(self):
        p = Platform.parse('a-b-c')
        self.assertEqual(p.os_name, 'a')
        self.assertEqual(p.os_release, 'b')
        self.assertEqual(p.architecture, 'c')

    def test_parse_invalid(self):
        self.assertRaises(InvalidPlatform, Platform.parse, 'a-b')

    def test_current(self):
        p = Platform.current()
        if platform.system() == 'Darwin':
            self.assertEqual(p.os_name, 'osx')
        self.assertEqual(p.architecture, platform.machine())
