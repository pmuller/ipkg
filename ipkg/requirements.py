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
import re
import operator
from collections import defaultdict

import pkg_resources as pkgres

from .exceptions import IpkgException
from .platforms import Platform, InvalidPlatform
from .compat import basestring


class InvalidRequirement(IpkgException):

    MESSAGE = 'Invalid requirement: %s'


class ExclusiveVersionRequirements(InvalidRequirement):

    MESSAGE = 'Exclusive version requirements for operator %s: %s'


class Requirement(object):

    def __init__(self, requirement):
        if ':' in requirement:
            platform, package = requirement.split(':', 1)
            platform = Platform.parse(platform)
        else:
            package = requirement
            platform = Platform.current()

        self.platform = platform
        self.name, self.extras, self.versions = parse(package)

    def __hash__(self):
        return hash(str(self.platform)) ^ hash(self.name) ^ \
            hash(tuple(self.extras)) ^ hash(tuple(self.versions))

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

    def __make_extras_str(self, extras):
        return '[' + ','.join(extras) + ']' if extras else ''

    def __make_versions_str(self, versions):
        operators = dict((op, s) for s, op in OPERATORS.items())
        versions_str = []
        for version_operator, version_tuple in versions:
            version_parts = []
            for version_part in version_tuple:
                if version_part == '*final':
                    break
                elif version_part[0] == '*':
                    version_parts.append(version_part[1:])
                else:
                    version_parts.append(str(int(version_part)))
            operator = operators[version_operator]
            version = '.'.join(version_parts)
            versions_str.append(operator + version)
        return ','.join(versions_str)

    def __str__(self):
        extras = self.__make_extras_str(self.extras)
        versions = self.__make_versions_str(self.versions)
        return '%s:%s%s%s' % (self.platform, self.name, extras, versions)

    def __repr__(self):
        return 'Requirement(%r)' % str(self)

    def __add__(self, other):
        if isinstance(other, basestring):
            other = Requirement(other)
        elif not isinstance(other, Requirement):
            raise TypeError(other)
        if self.name != other.name:
            raise InvalidRequirement(other)
        if self.platform != other.platform:
            raise InvalidPlatform(other.platform)
        extras_str = self.__make_extras_str(set(self.extras + other.extras))
        versions_str = self.__make_versions_str(
            set(self.versions + other.versions))
        return Requirement('%s:%s%s%s' % (self.platform, self.name,
                                          extras_str, versions_str))

    def satisfied_by_version(self, version):
        if isinstance(version, basestring):
            version = pkgres.parse_version(version)
        return all(op(version, v) for op, v in self.versions)

    def satisfied_by(self, obj):
        """Returns ``True`` if ``obj`` satisfies this ``Requirement``.

        ``obj`` should be a ``Formula`` or a ``Package`` object.
        """
        if isinstance(obj, dict):
            return obj.get('platform', 'any') == self.platform and \
                obj.get('name') == self.name and \
                self.satisfied_by_version(obj.get('version'))
        else:
            return (not hasattr(obj, 'platform') or
                    obj.platform == self.platform) and \
                hasattr(obj, 'name') and \
                obj.name == self.name and \
                hasattr(obj, 'version') and \
                self.satisfied_by_version(obj.version)


RE_REQUIREMENT = re.compile("""
^
\s*
(?P<name>[A-Za-z0-9_\-]+)
\s*
(
    \[
    (?P<extras>[A-Za-z0-9_\-, ]+)
    \]
)?
\s*
(?P<versions>[A-Za-z0-9_\-,!=\>\<\. ]+)*
\s*
$
""", re.X)
RE_VERSION_REQUIREMENT = re.compile("""
^
\s*
(?P<operator>==|!=|\<|\>|\<=|\>=)
\s*
(?P<version>[0-9A-Za-z_\-\.]+)
\s*
$
""", re.X)

OPERATORS = {
    '==': operator.eq,
    '!=': operator.ne,
    '>': operator.gt,
    '>=': operator.ge,
    '<': operator.lt,
    '<=': operator.le,
}

def parse_version(version_string):
    match = RE_VERSION_REQUIREMENT.match(version_string)

    if not match:
        raise InvalidRequirementVersion(version_string)

    version_dict = match.groupdict()

    if version_dict['operator'] not in OPERATORS:
        raise InvalidRequirementVersionOperator(version_dict['operator'])

    return OPERATORS[version_dict['operator']], \
        pkgres.parse_version(version_dict['version'])


def parse(requirement):
    requirement_match = RE_REQUIREMENT.match(requirement)

    if not requirement_match:
        raise InvalidRequirement(requirement)

    requirement_dict = requirement_match.groupdict()

    version_strings = []
    if requirement_dict['versions']:
        version_strings = re.split(r'\s*,\s*', requirement_dict['versions'])
        if len(version_strings) == 1 and not version_strings[0]:
            version_strings = []

    version_selectors = remove_useless_version_selectors(map(parse_version,
                                                             version_strings))

    if requirement_dict['extras']:
        extras = re.split(r'\s*,\s*', requirement_dict['extras'].strip())
    else:
        extras = []

    return requirement_dict['name'], extras, version_selectors


def remove_useless_version_selectors(version_selectors):
    selectors = defaultdict(set)

    for op, version in version_selectors:
        selectors[op].add(version)

    if operator.gt in selectors:
        gt_ver = sorted(selectors[operator.gt])[-1]
    else:
        gt_ver = None

    if operator.ge in selectors:
        ge_ver = sorted(selectors[operator.ge])[-1]
    else:
        ge_ver = None

    if operator.lt in selectors:
        lt_ver = sorted(selectors[operator.lt])[0]
    else:
        lt_ver = None

    if operator.le in selectors:
        le_ver = sorted(selectors[operator.le])[0]
    else:
        le_ver = None

    l_selector, g_selector = None, None

    if le_ver:
        if lt_ver:
            if le_ver < lt_ver:
                # <= 1, < 2
                l_selector = operator.le, le_ver
            else:
                # <= 2, < 1
                # <= 2, < 2
                l_selector = operator.lt, lt_ver
        else:
            l_selector = operator.le, le_ver
    elif lt_ver:
        l_selector = operator.lt, lt_ver

    if ge_ver:
        if gt_ver:
            if ge_ver <= gt_ver:
                # >= 1, > 2
                # >= 2, > 2
                g_selector = operator.gt, gt_ver
            else:
                # >= 2, > 1
                g_selector = operator.ge, ge_ver
        else:
            g_selector = operator.ge, ge_ver
    elif gt_ver:
        g_selector = operator.gt, gt_ver

    if g_selector and l_selector:
        g_op, g_ver = g_selector
        l_op, l_ver = l_selector
        if g_ver == l_ver:
            if g_op == operator.ge and l_op == operator.le:
                selectors[operator.eq].add(l_ver)
                g_selector, l_selector = None, None
            else:
                raise ExclusiveVersionRequirements(g_selector, l_selector)
        elif g_ver > l_ver:
            raise ExclusiveVersionRequirements(g_selector, l_selector)

    eq_ver = None
    eq_ver_count = len(selectors[operator.eq])
    if eq_ver_count == 1:
        eq_ver = selectors[operator.eq].pop()
    elif eq_ver_count > 1:
        raise ExclusiveVersionRequirements(operator.eq,
                                           list(selectors[operator.eq]))

    result = []

    if eq_ver:
        if l_selector or g_selector:
            raise ExclusiveVersionRequirements(operator.eq,
                                               'incompatible with other version operators')
        else:
            result.append((operator.eq, eq_ver))

    if g_selector:
        result.append(g_selector)
    if l_selector:
        result.append(l_selector)

    return result
