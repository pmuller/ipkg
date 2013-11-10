import os
import json
import tarfile
import logging

from .files import vopen
from .exceptions import IpkgException
from .mixins import NameVersionRevisionComparable


LOGGER = logging.getLogger(__name__)
META_FILE = '.ipkg.meta'


class UnknownMeta(IpkgException):
    """An unknown meta data was requested.
    """
    def __init__(self, meta):
        self.meta = meta

    def __str__(self):
        return 'Unknown meta data: %s' % self.meta


class MetaPackage(NameVersionRevisionComparable):
    """Base package class.
    """
    def __init__(self, meta):
        self.meta = meta

    def __getattr__(self, attr):
        """Make package meta data accessible as attributes.
        """
        if attr in self.meta:
            return self.meta[attr]
        else:
            raise UnknownMeta(attr)

    def as_requirement(self):
        return '%(name)s==%(version)s' % self.meta

    def __str__(self):
        return self.as_requirement()

    def __repr__(self):
        return '%s(%r)' % (self.__class__.__name__, self.meta)


class PackageFile(MetaPackage):
    """An ipkg package file.
    """
    def __init__(self, path, meta=None):
        self.__path = path
        self.__tarfile = None
        self.__meta = meta

    @property
    def meta(self):
        if not self.__meta:
            self.__meta = json.load(self._tarfile.extractfile(META_FILE))
        return self.__meta

    @property
    def _tarfile(self):
        if self.__tarfile is None:
            self.__tarfile = tarfile.open(fileobj=vopen(self.__path))
        return self.__tarfile

    def extract(self, path):
        """Extract the package to ``path``.
        """
        LOGGER.debug('Extracting %s in %s', self, path)
        files = [m for m in self._tarfile.getmembers() if m.path != META_FILE]
        self._tarfile.extractall(path, files)


def make_filename(**meta):
    return '%(name)s-%(version)s-%(revision)s-%(platform)s.ipkg' % meta
