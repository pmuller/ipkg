from ..exceptions import IpkgException


class FilesException(IpkgException):
    """A vfiles error."""


class UnknownScheme(FilesException):
    """Unknown file scheme."""
