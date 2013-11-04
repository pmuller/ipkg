from logging import getLogger
from os import path, environ
from hashlib import sha256

from .exceptions import FilesException


LOGGER = getLogger(__name__)
ENVVAR_NAME = 'IPKG_CACHE_DIR'


class CacheException(FilesException):
    pass


def get_cache_dir():
    if ENVVAR_NAME in environ:
        cache_dir = environ[ENVVAR_NAME]
        if path.isdir(cache_dir):
            return cache_dir
        else:
            raise CacheException('Invalid cache directory: %s' % cache_dir)
    else:
        raise CacheException('Cannot store %s: no cache directory')


def is_active():
    try:
        get_cache_dir()
    except CacheException:
        return False
    else:
        return True


def get_cache_filepath(name):
    filename = sha256(name).hexdigest()
    return path.join(get_cache_dir(), filename)


def has(name):
    if is_active():
        return path.exists(get_cache_filepath(name))
    else:
        return False


def set(name, content):
    try:
        with open(get_cache_filepath(name), 'wb') as f:
            f.write(content)
    except Exception as exc:
        LOGGER.exception('Failed to add %s to cache', name)
    else:
        LOGGER.debug('Added %s to cache', name)


def get(name):
    if is_active():
        filepath = get_cache_filepath(name)
        LOGGER.debug('Found %s in cache', name)
        return open(filepath)
