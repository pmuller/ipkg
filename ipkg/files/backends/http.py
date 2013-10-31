import logging

try:
    from cStringIO import StringIO
except ImportError: # Python 3
    from io import StringIO

import requests

from . import BaseFile, BackendException


LOGGER = logging.getLogger(__name__)


class HttpFileException(BackendException):
    """An error occurred while accessing a file over HTTP/s."""


class HttpFile(BaseFile):
    """A file on a remote HTTP server.
    """
    def __init__(self, *args, **kw):
        super(HttpFile, self).__init__(*args, **kw)
        self.__file = None

    def __download(self):
        LOGGER.info('Downloading: %s', self.name)
        try:
            response = requests.get(self.name, stream=True)

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
            LOGGER.info('Downloaded: %s', self.name)

    def __get_file(self):
        if self.__file is None:
            self.__download()
        return self.__file

    def seek(self, *args):
        self.__get_file().seek(*args)

    def tell(self):
        return self.__get_file().tell()

    def read(self, *args):
        return self.__get_file().read(*args)
