import os
import json
import logging

from .vfiles import vopen


LOGGER = logging.getLogger(__name__)


class DictFile(dict):
    """A ``dict``, storable as a JSON file.
    """
    def __init__(self, file_path):
        super(DictFile, self).__init__()
        self.__file_path = file_path
        self.reload()

    def reload(self):
        if os.path.isfile(self.__file_path):
            LOGGER.debug('Loading %s', self.__file_path)
            self.update(json.load(vopen(self.__file_path)))

    def clear(self):
        """Force the dictionary to be empty.
        """
        if os.path.isfile(self.__file_path):
            os.unlink(self.__file_path)
            super(DictFile, self).clear()

    def save(self):
        LOGGER.debug('Writing %s', self.__file_path)
        # This will break if trying to call save() on a remote DictFile
        with open(self.__file_path, 'w') as f:
            json.dump(self, f, indent=4)
