import os
import json
import tarfile
import logging
from cStringIO import StringIO

from pkg_resources import parse_version

from .vfiles import vopen
from .exceptions import IpkgException
from .mixins import NameVersionRevisionComparable
from .utils import make_package_spec


LOGGER = logging.getLogger(__name__)
META_FILE = '.ipkg.meta'


class UnknownMeta(IpkgException):
    """An unknown meta data was requested.
    """
    def __init__(self, meta):
        self.meta = meta

    def __str__(self):
        return 'Unknown meta data: %s' % self.meta


class BasePackage(NameVersionRevisionComparable):
    """Base package class.
    """
    def __init__(self):
        self.meta = {}
        self.__file = None

    def __getattr__(self, attr):
        """Make package meta data accessible as attributes.
        """
        if attr in self.meta:
            return self.meta[attr]
        else:
            raise UnknownMeta(attr)


class InstalledPackage(BasePackage):
    """A package which is already installed.
    """
    def __init__(self, meta):
        super(InstalledPackage, self). __init__()
        self.meta = meta

    def __repr__(self):
        return 'InstalledPackage(%r)' % self.meta

    def __str__(self):
        return make_package_spec(self.meta)


class PackageFile(BasePackage):
    """An ipkg package file.
    """
    def __init__(self, package_spec):
        super(PackageFile, self). __init__()
        self.__spec = package_spec
        vfile = vopen(package_spec)
        self.__file = tarfile.open(fileobj=vfile)
        # WARNING : This is slow on big packages !
        #LOGGER.debug('%r: Extracting meta file', self)
        meta_string = self.__file.extractfile(META_FILE).read()
        #LOGGER.debug('%r: Meta file extracted', self)
        self.meta = json.loads(meta_string)

    def extract(self, path):
        """Extract the package to ``path``.
        """
        LOGGER.debug('%r.extract("%s")', self, path)
        files = [m for m in self.__file.getmembers() if m.path != META_FILE]
        self.__file.extractall(path, files)

    def __repr__(self):
        return 'PackageFile("%s")' % self.__spec

    def __str__(self):
        return self.__spec
