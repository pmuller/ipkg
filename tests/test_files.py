import hashlib
from unittest import TestCase
from os.path import dirname, join

from ipkg.files.backends import InvalidChecksum
from ipkg.files.backends.filesystem import LocalFile


class TestLocalFile(TestCase):

    FILE = join(dirname(__file__), 'data/sources/foo-1.0.tar.gz')
    CHECKSUM = '6ffae9495a2bf9ca344c1976d6a8f2d5'

    def test_verify_checksum(self):
        LocalFile(self.FILE, self.CHECKSUM, hashlib.md5).verify_checksum()

    def test_verify_checksum_invalid(self):
        f = LocalFile(self.FILE, 'foo')
        self.assertRaises(InvalidChecksum, f.verify_checksum)
