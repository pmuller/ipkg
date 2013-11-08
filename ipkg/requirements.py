import pkg_resources as pkgres

from .exceptions import IpkgException


class InvalidRequirement(IpkgException):

    MESSAGE = 'Invalid requirement: %s'


class PackageRequirement(object):

    def __init__(self, requirement, **kw):
        try:
            self.__requirement = pkgres.Requirement.parse(requirement)
        except ValueError:
            raise InvalidRequirement(requirement)

        self.name = self.__requirement.project_name

    def __str__(self):
        return str(self.__requirement)

    def is_satisfied_by(self, obj):
        return obj.name == self.name and obj.version in self.__requirement
