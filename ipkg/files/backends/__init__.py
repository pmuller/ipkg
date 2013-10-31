"""vfiles backend classes handle protocol access to files.
"""
import logging
import hashlib

from ..exceptions import FilesException


LOGGER = logging.getLogger(__name__)


class BackendException(FilesException):
    """Raised by a backend."""


class InvalidChecksum(BackendException):
    """The file checksum is invalid."""


class BaseFile(object):
    """Base class for virtual files.
    """
    def __init__(self, name, expected_hash=None, hash_class=hashlib.sha256):
        self.name = name
        self.expected_hash = expected_hash
        self.hash_class = hash_class

    def __str__(self):
        return self.name

    def verify_checksum(self):
        """Validates a file checksum.
        """
        if self.expected_hash is None:
            LOGGER.debug('No checksum for %s', self.name)
            return

        else:
            hash_obj = self.hash_class()
            current_position = self.tell()
            file_content = self.read()
            self.seek(current_position)
            hash_obj.update(file_content)
            file_hash = hash_obj.hexdigest()

            if file_hash != self.expected_hash:
                LOGGER.error('File checksum is %s, expected %s (%s)',
                             file_hash, self.expected_hash, hash_obj.name)
                raise InvalidChecksum()

            else:
                LOGGER.debug('Checksum ok for %s', self.name)

    def seek(self, *args):
        pass

    def tell(self):
        return 0

    def read(self, *args):
        raise NotImplentedError
