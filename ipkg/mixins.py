from .utils import is_package_like, parse_package_spec


class NameVersionRevisionComparable(object):
    """This mixin assumes sub classes has the ``name``, ``version`` and
       ``revision`` attributes and make them comparables using the
       standard operators.
    """
    def __eq__(self, other):

        if is_package_like(other):
            return self.name == other.name and \
                   self.version == other.version and \
                   self.revision == other.revision

        elif isinstance(other, basestring):
            spec = parse_package_spec(other)
            if spec['name'] == self.name:
                if 'version' in spec:
                    if spec['version'] == self.version:
                        if 'revision' in spec:
                            return str(spec['revision']) == str(self.revision)
                        else:
                            # No revision in spec, so it's ok
                            return True
                    else:
                        # Different version
                        return False
                else:
                    # No version in spec, so it's ok
                    return True
            else:
                # Different name
                return False

        else:
            # other is neither a package-like object, nor a string
            return False

    def __ne__(self, other):
        return not (self == other)

    def __lt__(self, other):
        return self.__compare(other, operator.lt)

    def __gt__(self, other):
        return self.__compare(other, operator.gt)

    def __compare(self, other, op):

        cmp_func = lambda a, b: op(parse_version(str(a)),
                                   parse_version(str(b)))

        if is_package_like(other):
            if self.name == other.name:
                if self.version == other.version:
                    return cmp_func(self.version, other.version)
                else:
                    return cmp_func(self.revision, other.revision)
            else:
                return False

        elif isinstance(other, basestring):
            spec = parse_package_spec(other)

            if spec['name'] == self.name:
                if 'version' in spec:
                    if spec['version'] == self.version:
                        if 'revision' in spec:
                            return cmp_func(self.revision, spec['revision'])
                        else:
                            # Same version as spec and no revision in spec,
                            # not ok
                            return False
                    else:
                        return cmp_func(self.version, spec['version'])
                else:
                    # No version in spec, not ok
                    return False
            else:
                # Different name
                return False

        else:
            # other is neither a package-like object, nor a string
            return False

    def __le__(self, other):
        return self == other or self < other

    def __ge__(self, other):
        return self == other or self > other
