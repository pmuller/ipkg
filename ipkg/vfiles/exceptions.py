from ..exceptions import IpkgException


class VFilesException(IpkgException):
    """A vfiles error."""


class UnknownScheme(VFilesException):
    pass
