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

PACKAGE_FILE = re.compile(r"""
^
(?P<name>[A-Za-z0-9_\-]+)
-
(?P<version>[0-9a-zA-Z\.\-_]+)
-
(?P<revision>\w+)
-
(?P<os_name>\w+)
-
(?P<os_release>[\.\w]+)
-
(?P<arch>[_\w]+)
\.ipkg
$
""", re.X)

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
