from unittest import TestCase

from ipkg.requirements import Requirement, InvalidRequirement


class Package(object):

    def __init__(self, name, version):
        self.name = name
        self.version = version
        self.platform = 'any'


class TestPackageRequirement(TestCase):

    def test(self):
        req = Requirement('any:foo < 2')
        self.assertEqual(req.platform, 'any')

    def test_satisfied_by(self):
        req = Requirement('foo >= 1.0, < 2')
        self.assertTrue(req.satisfied_by(Package('foo', '1.0')))
        self.assertFalse(req.satisfied_by(Package('foo', '2.0')))
        self.assertFalse(req.satisfied_by(Package('foo', '0.42')))


    def test_raises(self):
        self.assertRaises(InvalidRequirement,
                          Requirement, 'foo/bar > 42%')

    def test_eq(self):
        self.assertTrue(Requirement('foo==1.0') == Requirement('foo == 1.0'))
        self.assertTrue(Requirement('foo==1.0') == 'foo == 1.0')
        self.assertFalse(Requirement('foo') == 'fnioewf < &*')
        self.assertFalse(Requirement('foo') == 1)
