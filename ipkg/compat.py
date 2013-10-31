"""
Portability code to make ipkg works on Python 2.x and 3.x
"""

# Use case: isinstance(obj, basestring)
try:
    basestring = basestring
except NameError:
    basestring = str


try:
    from cStringIO import StringIO
except ImportError:
    from io import StringIO
