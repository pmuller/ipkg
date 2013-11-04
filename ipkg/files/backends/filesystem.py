import os

try:
    from urlparse import urlparse
except ImportError:  # Python 3
    from urllib.parse import urlparse

from . import BaseFile, BackendException


class LocalFileException(BackendException):
    """An error occurred while accessing a local file."""


class LocalFile(BaseFile):
    """A file on the local filesystem.
    """
    def __init__(self, *args, **kw):
        super(LocalFile, self).__init__(*args, **kw)
        filepath = urlparse(self.name).path
        if os.path.isfile(filepath):
            self.__file = open(filepath)
        else:
            raise LocalFileException('Not a file: %s' % filepath)

    def seek(self, *args):
        self.__file.seek(*args)

    def tell(self):
        return self.__file.tell()

    def read(self, *args):
        return self.__file.read(*args)
