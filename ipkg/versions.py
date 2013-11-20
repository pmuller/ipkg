from pkg_resources import parse_version


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
    return parse_version(version), parse_version(str(revision))
