import urlparse

from pkg_resources import iter_entry_points
from .exceptions import UnknownScheme


__all__ = ['vopen']
DEFAULT_SCHEME = 'file'


def vopen(url, **kw):
    info = urlparse.urlparse(url)
    scheme = info.scheme or DEFAULT_SCHEME

    for backend_ep in iter_entry_points(group='ipkg.vfiles.backend'):
        if backend_ep.name == scheme:
            backend_cls = backend_ep.load()
            backend = backend_cls(url, **kw)
            return backend
    else:
        raise UnknownScheme('No backend found for scheme: %s' % scheme)
