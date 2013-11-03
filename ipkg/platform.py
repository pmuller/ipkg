# Without absolute imports, we cannot import the system platform
# module because we use the same name.
from __future__ import absolute_import

import platform as pf
from socket import gethostname

from .exceptions import IpkgException


__all__ = ['UnknownSystem', 'RELEASE', 'NAME', 'ARCHITECTURE']


system = pf.system()

if system == 'Linux':
    NAME, RELEASE, _ = pf.dist()
    NAME = NAME.lower()
elif system == 'Darwin':
    NAME = 'osx'
    RELEASE = pf.mac_ver()[0]
else:
    raise IpkgException('Unsupported system: %s' % system)


ARCHITECTURE = pf.machine()
PLATFORM = '%s-%s-%s' % (NAME, RELEASE, ARCHITECTURE)
HOSTNAME = gethostname().split('.')[0]
