import re


PKGCONFIG_FILE = re.compile(r'^lib(64)?/pkgconfig/[^/]+\.pc$')
LIBTOOL_FILE = re.compile(r'^lib(64)?/[^/]+\.la$')

FORMULA_FILE = re.compile(r"""
^
(?P<name>[A-Za-z0-9_\-]+)
-
(?P<version>[0-9a-zA-Z\.\-_]+)
-
(?P<revision>\w+)
\.py
$
""", re.X)

_PLATFORM = r'(?P<os_name>\w+)-(?P<os_release>[\.\w]+)-(?P<arch>[_\w]+)'
PLATFORM = re.compile(_PLATFORM)

PACKAGE_FILE = re.compile(r"""
^
(?P<name>[A-Za-z0-9_\-]+)
-
(?P<version>[0-9a-zA-Z\.\-_]+)
-
(?P<revision>\w+)
-
%s
\.ipkg
$
""" % _PLATFORM, re.X)

PACKAGE_SPEC = re.compile(r"""
^
(?P<name>[A-Za-z0-9_\-]+)
(
    (?P<operator>==)
    (?P<version>[0-9a-zA-Z\.\-_]+)
    (
        :
        (?P<revision>\w+)
    )?
)?
$
""", re.X)
