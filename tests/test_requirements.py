from unittest import TestCase
import operator

from ipkg.requirements import Requirement, InvalidRequirement, \
    RE_REQUIREMENT, RE_VERSION_REQUIREMENT, parse_version, parse, \
    remove_useless_version_selectors, ExclusiveVersionRequirements


class Package(object):

    def __init__(self, name, version):
        self.name = name
        self.version = version
        self.platform = 'any'


class TestPackageRequirement(TestCase):

    def test(self):
        req = Requirement('any:foo < 2')
        self.assertEqual(req.platform, 'any')

    def test_hash(self):
        self.assertEqual(hash(Requirement('foo >1,<2')),
                         hash(Requirement('foo >1,<2')))

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

    def test_complex_1(self):
        req = Requirement('foo>1,>2')
        self.assertFalse(req.satisfied_by({'name': 'foo', 'version': '1.5'}))
        self.assertFalse(req.satisfied_by({'name': 'foo', 'version': '2'}))
        self.assertTrue(req.satisfied_by({'name': 'foo', 'version': '2.1'}))
        req = Requirement('foo>2,>1')
        self.assertFalse(req.satisfied_by({'name': 'foo', 'version': '1.5'}))
        self.assertFalse(req.satisfied_by({'name': 'foo', 'version': '2'}))
        self.assertTrue(req.satisfied_by({'name': 'foo', 'version': '2.1'}))

    def test_complex_2(self):
        req = Requirement('foo<3,<2')
        self.assertFalse(req.satisfied_by({'name': 'foo', 'version': '3'}))
        self.assertFalse(req.satisfied_by({'name': 'foo', 'version': '2'}))
        self.assertTrue(req.satisfied_by({'name': 'foo', 'version': '1'}))
        req = Requirement('foo<2,<3')
        self.assertFalse(req.satisfied_by({'name': 'foo', 'version': '3'}))
        self.assertFalse(req.satisfied_by({'name': 'foo', 'version': '2'}))
        self.assertTrue(req.satisfied_by({'name': 'foo', 'version': '1'}))

    def test_complex_3(self):
        req = Requirement('foo<3,<=3')
        self.assertFalse(req.satisfied_by({'name': 'foo', 'version': '3'}))
        self.assertTrue(req.satisfied_by({'name': 'foo', 'version': '1'}))
        req = Requirement('foo<=3,<3')
        self.assertFalse(req.satisfied_by({'name': 'foo', 'version': '3'}))
        self.assertTrue(req.satisfied_by({'name': 'foo', 'version': '1'}))

    def test_merge(self):
        # should not merge requirements with other object types
        self.assertRaises(TypeError, Requirement('foo').__add__, None)
        # should not merge requirements for different packages
        self.assertRaises(InvalidRequirement, Requirement('foo').__add__,
                          Requirement('bar'))

        req = Requirement('foo>1.1,>1') + Requirement('foo<3,<2')
        self.assertTrue(req.satisfied_by({'name': 'foo', 'version': '1.5'}))
        self.assertFalse(req.satisfied_by({'name': 'foo', 'version': '1'}))
        self.assertFalse(req.satisfied_by({'name': 'foo', 'version': '2'}))


class TestRegexes(TestCase):

    def test_requirement(self):
        self.assertEqual(RE_REQUIREMENT.match('foo').groupdict(),
                         {'name': 'foo', 'extras': None, 'versions': None})
        self.assertEqual(RE_REQUIREMENT.match('foo == 2').groupdict(),
                         {'name': 'foo', 'extras': None, 'versions': '== 2'})
        self.assertEqual(RE_REQUIREMENT.match('foo ==2').groupdict(),
                         {'name': 'foo', 'extras': None, 'versions': '==2'})
        self.assertEqual(RE_REQUIREMENT.match('foo ==2, >= 3').groupdict(),
                         {'name': 'foo', 'extras': None, 'versions': '==2, >= 3'})
        self.assertEqual(RE_REQUIREMENT.match('foo [foo, bar,a-b ]==2, >= 3').groupdict(),
                         {'name': 'foo', 'extras': 'foo, bar,a-b ', 'versions': '==2, >= 3'})

    def test_version(self):
        self.assertEqual(RE_VERSION_REQUIREMENT.match('>1').groupdict(),
                         {'operator':'>','version':'1'})
        self.assertEqual(RE_VERSION_REQUIREMENT.match(' >= 1.0a42 ').groupdict(),
                         {'operator':'>=','version':'1.0a42'})


class TestParseVersion(TestCase):

    def test(self):
        self.assertEqual(parse_version('==1.0 '),
                         (operator.eq, ('00000001', '*final')))
        self.assertEqual(parse_version('> 4.0'),
                         (operator.gt, ('00000004', '*final')))


class TestParse(TestCase):

    def test(self):
        self.assertEqual(parse('foo==1.0'),
                         ('foo', [], [(operator.eq, ('00000001', '*final'))]))
        self.assertEqual(parse('foo[bar, blah]'),
                         ('foo', ['bar', 'blah'], []))
        self.assertEqual(parse('foo[wtf,bar]==1.0'),
                         ('foo', ['wtf', 'bar'], [(operator.eq, ('00000001', '*final'))]))

    def test_mix_versions(self):
        self.assertEqual(parse('foo>1,<=2'),
                         ('foo', [], [(operator.gt, ('00000001', '*final')),
                                      (operator.le, ('00000002', '*final'))]))
        self.assertEqual(parse('foo>1,>2'),
                         ('foo', [], [(operator.gt, ('00000002', '*final'))]))


class TestRemoveUselessVersionSelectors(TestCase):

    def test_dupplicate(self):
        a = [(operator.gt, ('00000001', '*final')),
             (operator.gt, ('00000001', '*final'))]
        b = [(operator.gt, ('00000001', '*final'))]
        self.assertEqual(remove_useless_version_selectors(a), b)

    def test_overlap_eq_raises(self):
        a = [(operator.eq, ('00000001', '*final')),
             (operator.eq, ('00000002', '*final'))]
        self.assertRaises(ExclusiveVersionRequirements,
                          remove_useless_version_selectors, a)

    def test_overlap_gt(self):
        a = [(operator.gt, ('00000001', '*final')),
             (operator.gt, ('00000002', '*final'))]
        b = [(operator.gt, ('00000002', '*final'))]
        self.assertEqual(remove_useless_version_selectors(a), b)

    def test_overlap_ge(self):
        a = [(operator.ge, ('00000001', '*final')),
             (operator.ge, ('00000002', '*final'))]
        b = [(operator.ge, ('00000002', '*final'))]
        self.assertEqual(remove_useless_version_selectors(a), b)

    def test_overlap_lt(self):
        a = [(operator.lt, ('00000001', '*final')),
             (operator.lt, ('00000002', '*final'))]
        b = [(operator.lt, ('00000001', '*final'))]
        self.assertEqual(remove_useless_version_selectors(a), b)

    def test_overlap_le(self):
        a = [(operator.le, ('00000001', '*final')),
             (operator.le, ('00000002', '*final'))]
        b = [(operator.le, ('00000001', '*final'))]
        self.assertEqual(remove_useless_version_selectors(a), b)

    def test_overlap_le_lt(self):
        # <=1,<2    <=1
        a = [(operator.le, ('00000001', '*final')),
             (operator.lt, ('00000002', '*final'))]
        b = [(operator.le, ('00000001', '*final'))]
        self.assertEqual(remove_useless_version_selectors(a), b)
        # <=1,<1    <1
        a = [(operator.le, ('00000001', '*final')),
             (operator.lt, ('00000001', '*final'))]
        b = [(operator.lt, ('00000001', '*final'))]
        self.assertEqual(remove_useless_version_selectors(a), b)
        # <=2,<1    <1
        a = [(operator.le, ('00000002', '*final')),
             (operator.lt, ('00000001', '*final'))]
        b = [(operator.lt, ('00000001', '*final'))]
        self.assertEqual(remove_useless_version_selectors(a), b)

    def test_overlap_ge_gt(self):
        # >=1,>2    >2
        a = [(operator.ge, ('00000001', '*final')),
             (operator.gt, ('00000002', '*final'))]
        b = [(operator.gt, ('00000002', '*final'))]
        self.assertEqual(remove_useless_version_selectors(a), b)
        # >=1,>1    >1
        a = [(operator.ge, ('00000001', '*final')),
             (operator.gt, ('00000001', '*final'))]
        b = [(operator.gt, ('00000001', '*final'))]
        self.assertEqual(remove_useless_version_selectors(a), b)
        # >=2,>1    >=2
        a = [(operator.ge, ('00000002', '*final')),
             (operator.gt, ('00000001', '*final'))]
        b = [(operator.ge, ('00000002', '*final'))]
        self.assertEqual(remove_useless_version_selectors(a), b)

    def test_exclusive_g_l_selectors(self):
        # >1,<1
        a = [(operator.gt, ('00000001', '*final')),
             (operator.lt, ('00000001', '*final'))]
        self.assertRaises(ExclusiveVersionRequirements,
                          remove_useless_version_selectors, a)
        # >=1,<1
        a = [(operator.ge, ('00000001', '*final')),
             (operator.lt, ('00000001', '*final'))]
        self.assertRaises(ExclusiveVersionRequirements,
                          remove_useless_version_selectors, a)
        # >1,<=1
        a = [(operator.gt, ('00000001', '*final')),
             (operator.le, ('00000001', '*final'))]
        self.assertRaises(ExclusiveVersionRequirements,
                          remove_useless_version_selectors, a)
        # >=1,<=1
        a = [(operator.ge, ('00000001', '*final')),
             (operator.le, ('00000001', '*final'))]
        b = [(operator.eq, ('00000001', '*final'))]
        self.assertEqual(remove_useless_version_selectors(a), b)
        # >2,<1
        # >=2,<1
        # >=2,<=1
        # >2,<=1
        a = [(operator.gt, ('00000002', '*final')),
             (operator.lt, ('00000001', '*final'))]
        self.assertRaises(ExclusiveVersionRequirements,
                          remove_useless_version_selectors, a)
