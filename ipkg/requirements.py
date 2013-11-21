"""Package requirements handling.

Package requirements are strings defined in the ``dependencies`` attribute of
``Formula`` and ``Package`` objects.

These strings express what's needed at runtime for the software package to
work.

Examples::
    
    platform:package==version
    package==version
    package

"""
import pkg_resources as pkgres

from .exceptions import IpkgException
from .platforms import Platform


class InvalidRequirement(IpkgException):

    MESSAGE = 'Invalid requirement: %s'


class Requirement(object):

    def __init__(self, requirement):
        if ':' in requirement:
            platform, package = requirement.split(':', 1)
            platform = Platform.parse(platform)
        else:
            package = requirement
            platform = Platform.current()

        self.__platform = platform

        try:
            self.__pkg_req = pkgres.Requirement.parse(package)
        except ValueError:
            raise InvalidRequirement(requirement)

        self.__hash = hash(str(platform)) ^ hash(self.__pkg_req)

    def __hash__(self):
        return self.__hash

    def __eq__(self, other):
        if isinstance(other, Requirement):
            return str(self) == str(other)
        elif isinstance(other, basestring):
            try:
                requirement = Requirement(other)
            except InvalidRequirement:
                return False
            else:
                return str(self) == str(requirement)
        else:
            return False

    @property
    def name(self):
        return self.__pkg_req.project_name

    @property
    def version(self):
        return ''.join(op + ver for op, ver in self.__pkg_req.specs)

    @property
    def extras(self):
        return self.__pkg_req.extras

    @property
    def platform(self):
        return self.__platform

    def __str__(self):
        extras = '[' + ','.join(self.extras) + ']' if self.extras else ''
        return '%s:%s%s%s' % (self.platform, self.name, extras, self.version)

    def __repr__(self):
        return 'Requirement(%r)' % str(self)

    def satisfied_by(self, obj):
        """Returns ``True`` if ``obj`` satisfies this ``Requirement``.

        ``obj`` should be a ``Formula`` or a ``Package`` object.
        """
        if isinstance(obj, dict):
            return obj.get('platform', 'any') == self.__platform and \
                obj.get('name') == self.__pkg_req.project_name and \
                obj.get('version') in self.__pkg_req
        else:
            return (not hasattr(obj, 'platform') or
                    obj.platform == self.__platform) and \
                hasattr(obj, 'name') and \
                obj.name == self.__pkg_req.project_name and \
                hasattr(obj, 'version') and \
                obj.version in self.__pkg_req
