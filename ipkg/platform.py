# Without absolute imports, we cannot import the system platform
# module because we use the same name.
from __future__ import absolute_import

import platform as pf
from socket import gethostname

from .exceptions import IpkgException
from . import regex


__all__ = ['RELEASE', 'NAME', 'ARCHITECTURE', 'PLATFORM',
           'HOSTNAME', 'SYSTEM', 'InvalidPlatform', 'parse']


class InvalidPlatform(IpkgException):

    def __init__(self, platform):
        self.platform = platform

    def __str__(self):
        return 'Invalid platform: %s' % self.platform


SYSTEM = pf.system()

if SYSTEM == 'Linux':
    NAME, RELEASE, _ = pf.dist()
    NAME = NAME.lower()
elif SYSTEM == 'Darwin':
    NAME = 'osx'
    RELEASE = pf.mac_ver()[0]
else:
    raise InvalidPlatform(SYSTEM)


ARCHITECTURE = pf.machine()
PLATFORM = '%s-%s-%s' % (NAME, RELEASE, ARCHITECTURE)
HOSTNAME = gethostname().split('.')[0]


def parse(string):
    """Parse a platform string and returns a tuple of
       (os_name, os_release, architecture).
    """
    match = regex.PLATFORM.match(string)
    if match:
        return match.groups()
    else:
        raise InvalidPlatform(string)
