from unittest import TestCase

from ipkg import requirements


class Package(object):

    def __init__(self, name, version):
        self.name = name
        self.version = version


class TestPackageRequirement(TestCase):

    def test(self):
        req = requirements.PackageRequirement('foo >= 1.0, < 2')
        self.assertTrue(req.is_satisfied_by(Package('foo', '1.0')))
        self.assertFalse(req.is_satisfied_by(Package('foo', '2.0')))
        self.assertFalse(req.is_satisfied_by(Package('foo', '0.42')))

    def test_raises(self):
        self.assertRaises(requirements.InvalidRequirement,
                          requirements.PackageRequirement, 'foo/bar > 42%')

    def test_str(self):
        string = 'foo'
        req = requirements.PackageRequirement(string)
        self.assertEqual(string, str(req))

    def test_eq(self):
        self.assertTrue(requirements.PackageRequirement('foo==1.0') ==
                        requirements.PackageRequirement('foo == 1.0'))
        self.assertTrue(requirements.PackageRequirement('foo==1.0')
                        == 'foo == 1.0')
