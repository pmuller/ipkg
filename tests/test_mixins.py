from unittest import TestCase

from ipkg.mixins import NameVersionRevisionComparable


class TestNameVersionRevisionComparable(TestCase):

    def setUp(self):
        obj1 = NameVersionRevisionComparable()
        obj1.name = 'foo'
        obj1.version = '1.0'
        obj1.revision = 1
        self.obj1 = obj1
        obj2 = NameVersionRevisionComparable()
        obj2.name = 'foo'
        obj2.version = '2.0'
        obj2.revision = 1
        self.obj2 = obj2

    def test_eq_package_like(self):
        self.assertTrue(self.obj1 == self.obj1)

    def test_eq_package_spec_full(self):
        self.assertTrue(self.obj1 == 'foo==1.0:1')

    def test_eq_package_spec_no_revision(self):
        self.assertTrue(self.obj1 == 'foo==1.0')

    def test_eq_package_spec_no_version(self):
        self.assertTrue(self.obj1 == 'foo')

    def test_eq_package_spec_different_version(self):
        self.assertFalse(self.obj1 == 'foo==1.1')

    def test_eq_package_spec_different_name(self):
        self.assertFalse(self.obj1 == 'bar')

    def test_eq_bad_obj_type(self):
        self.assertFalse(self.obj1 == None)

    def test_ne(self):
        self.assertTrue(self.obj1 != self.obj2)

    def test_lt_package_like_diff_version(self):
        self.assertTrue(self.obj1 < self.obj2)

    def test_lt_package_like_diff_revision(self):
        self.obj2.version = '1.0'
        self.obj2.revision = 2
        self.assertTrue(self.obj1 < self.obj2)

    def test_lt_package_like_other_name(self):
        self.obj2.name = 'bar'
        self.assertFalse(self.obj1 < self.obj2)

    def test_lt_package_spec_full_ver(self):
        self.assertTrue(self.obj1 < 'foo==1.1:1')

    def test_lt_package_spec_full_rev(self):
        self.assertTrue(self.obj1 < 'foo==1.0:2')

    def test_lt_package_spec_no_rev(self):
        self.assertFalse(self.obj1 < 'foo==1.0')

    def test_lt_package_spec_no_ver(self):
        self.assertFalse(self.obj1 < 'foo')

    def test_lt_package_spec_diff_name(self):
        self.assertFalse(self.obj1 < 'bar')

    def test_lt_bad_obj_type(self):
        self.assertFalse(self.obj1 < None)

    def test_gt(self):
        self.assertTrue(self.obj2 > self.obj1)

    def test_ge(self):
        self.assertTrue(self.obj1 >= self.obj1)
        self.assertTrue(self.obj2 >= self.obj1)

    def test_le(self):
        self.assertTrue(self.obj1 <= self.obj1)
        self.assertTrue(self.obj1 <= self.obj2)
