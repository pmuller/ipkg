try:
    from urlparse import urlparse
except ImportError:  # Python 3
    from urllib.parse import urlparse

from pkg_resources import iter_entry_points
from .exceptions import UnknownScheme


__all__ = ['vopen']
DEFAULT_SCHEME = 'file'


def vopen(url, **kw):
    """Open a file, regardless of its location.

       Its URL is used to determine which backend will handle it,
       making HTTP requests or filesystem calls as needed.
    """
    info = urlparse(url)
    scheme = info.scheme or DEFAULT_SCHEME

    for backend_ep in iter_entry_points(group='ipkg.files.backend'):
        if backend_ep.name == scheme:
            backend_cls = backend_ep.load()
            backend = backend_cls(url, **kw)
            return backend
    else:
        raise UnknownScheme('No backend found for scheme: %s' % scheme)
