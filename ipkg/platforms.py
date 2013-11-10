import platform

from .compat import basestring
from .exceptions import IpkgException


class InvalidPlatform(IpkgException):

    def __init__(self, platform):
        self.platform = platform

    def __str__(self):
        return 'Invalid platform: %s' % self.platform


class Platform(object):
    """A platform, as understood by ipkg.
    """
    def __init__(self, os_name, os_release, architecture):
        self.os_name = os_name
        self.os_release = os_release
        self.architecture = architecture

    def __str__(self):
        return '%s-%s-%s' % (self.os_name, self.os_release, self.architecture)

    def __eq__(self, platform):
        if isinstance(platform, basestring):
            try:
                platform = Platform.parse(platform)
            except InvalidPlatform:
                return False

        return (('any' in (self.os_name, platform.os_name) or
                 self.os_name == platform.os_name) and
                ('any' in (self.os_release, platform.os_release) or
                 self.os_release == platform.os_release) and
                ('any' in (self.architecture, platform.architecture) or
                 self.architecture == platform.architecture))

    @classmethod
    def parse(cls, platform):
        platform = platform.strip().lower()

        if platform == 'any':
            return cls('any', 'any', 'any')

        try:
            os_name, os_release, architecture = platform.lower().split('-')
        except ValueError:
            raise InvalidPlatform(platform)
        else:
            return cls(os_name, os_release, architecture)

    @classmethod
    def current(cls):

        system = platform.system()
        if system == 'Linux':
            name, release, _ = platform.dist()
            name = name.lower()
        elif system == 'Darwin':
            name = 'osx'
            release = platform.mac_ver()[0]
        else:
            raise InvalidPlatform(system)

        architecture = platform.machine()

        return cls(name, release, architecture)
