"""vfiles backend classes handle protocol access to files.
"""
import urlparse
import logging
import hashlib
from cStringIO import StringIO

import requests

from .exceptions import VFilesException


LOGGER = logging.getLogger(__name__)


class BackendException(VFilesException):
    """Raised by a backend."""


class LocalFileException(BackendException):
    """An error occurred while accessing a local file."""


class HttpFileException(BackendException):
    """An error occurred while accessing a file over HTTP/s."""


class InvalidChecksum(BackendException):
    """The file checksum is invalid."""


class BaseFile(object):
    """Base class for virtual files.
    """
    def __init__(self, url, expected_hash=None, hash_class=hashlib.sha256):
        self.url = url
        self.expected_hash = expected_hash
        self.hash_class = hash_class

    def verify_checksum(self):
        """Validates a file checksum.
        """
        if self.expected_hash is None:
            LOGGER.debug('No hash for %s', url)
            return
        else:
            hash_obj = self.hash_class()
            current_position = self.tell()
            file_content = self.read()
            self.seek(current_position)
            hash_obj.update(file_content)
            file_hash = hash_obj.hexdigest()
            if file_hash != self.expected_hash:
                LOGGER.error('File hash is %s, expected hash is %s (%s)',
                             file_hash, self.expected_hash, hash_obj.name)
                raise InvalidChecksum()
            else:
                LOGGER.debug('Checksum ok for %s', self.url)

    def seek(self, *args):
        pass

    def tell(self):
        return 0

    def read(self, *args):
        raise NotImplentedError


class DummyFile(BaseFile):
    """A dummy file.
    """
    def read(self):
        return self.url


class LocalFile(BaseFile):
    """A file on the local filesystem.
    """
    def __init__(self, url, expected_hash=None, hash_class=hashlib.sha256):
        super(LocalFile, self).__init__(url, expected_hash, hash_class)
        filepath = urlparse.urlparse(url).path
        self.__file = open(filepath)

    def seek(self, *args):
        self.__file.seek(*args)

    def tell(self):
        return self.__file.tell()

    def read(self, *args):
        return self.__file.read(*args)


class HttpFile(BaseFile):
    """A file on a remote HTTP server.
    """
    def __init__(self, url, expected_hash=None, hash_class=hashlib.sha256):
        super(HttpFile, self).__init__(url, expected_hash, hash_class)
        self.__file = None

    def __get_file(self):
        if self.__file is None:
            try:
                response = requests.get(self.url, stream=True)

            except requests.RequestException as exc:
                raise HttpFileException(str(exc))

            else:
                content = StringIO()
                while True:
                    data = response.raw.read(1024 * 1024)
                    if data:
                        content.write(data)
                    else:
                        break
                content.seek(0)
                self.__file = content

        return self.__file

    def seek(self, *args):
        self.__get_file().seek(*args)

    def tell(self):
        return self.__get_file().tell()

    def read(self, *args):
        return self.__get_file().read(*args)
