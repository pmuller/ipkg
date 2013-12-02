import __builtin__  # because we override sorted in this module

import pkg_resources


def compare(a, b):
    if a < b:
        return -1
    elif a == b:
        return 0
    else:  # a > b
        return 1


def extract(item):
    if isinstance(item, dict):
        version = item['version']
        revision = item['revision']
    else:
        version = item.version
        revision = item.revision
    return parse(version), parse(str(revision))


def parse(version):
    """Parses a ``version`` string.

    Currently a simple wrapper around ``pkg_resources.parse_version()``,
    for API purpose. Parsing could change later.
    """
    return pkg_resources.parse_version(version)


def sorted(versions, parser=parse, reverse=False):
    """Returned sorted ``versions``.
    """
    return __builtin__.sorted(versions, key=parser, cmp=compare,
                              reverse=reverse)


def most_recent(versions, parser=parse):
    """Returns the most recent version among ``versions``.

    * ``versions`` must be an iterable of versions.
    * ``parser`` defaults to ``parse`` which parses version strings.
    """
    return sorted(versions, reverse=True)[0]
