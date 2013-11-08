class IpkgException(Exception):
    """Base exception for ipkg."""

    MESSAGE = None

    def __init__(self, *args):
        self.args = args

    def __str__(self):
        if self.MESSAGE:
            if self.args:
                try:
                    return self.MESSAGE % self.args
                except TypeError:
                    pass
            return self.MESSAGE
        else:
            if self.args:
                return str(self.args)
            else:
                return ''
