import os
import json
import logging


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
            with open(self.__file_path) as f:
                self.update(json.load(f))

    def save(self):
        LOGGER.debug('Writing %s', self.__file_path)
        with open(self.__file_path, 'w') as f:
            json.dump(self, f, indent=4)
