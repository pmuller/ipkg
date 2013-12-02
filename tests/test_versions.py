from unittest import TestCase

from ipkg import versions


class TestSorted(TestCase):

    def test(self):
        self.assertEqual(versions.sorted(['1.5', '1.3', '1.0', '2.0']),
                         ['1.0', '1.3', '1.5', '2.0'])


class TestMostRecent(TestCase):

    def test(self):
        self.assertEqual(versions.most_recent(['1.1', '1.3', '1.0', '0.7']),
                         '1.3')
