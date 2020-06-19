#!/usr/bin/env python

"""
Compatibility module similar to six which helps maintaining
a single code base working with python from 2.6 to 3.x.
"""

import os
import errno
import sys

PY3 = sys.version_info[0] == 3

if PY3:
    def u(s):
        return s

    def b(s):
        return s.encode("latin-1")

    getcwdu = os.getcwd
    unicode = str
    xrange = range
    long = int
else:
    def u(s):
        return unicode(s)

    def b(s):
        return s

    getcwdu = os.getcwdu
    unicode = unicode
    xrange = xrange
    long = long


# removed in 3.0, reintroduced in 3.2
try:
    callable = callable
except Exception:
    def callable(obj):
        for klass in type(obj).__mro__:
            if "__call__" in klass.__dict__:
                return True
        return False


# --- exceptions


if PY3:
    FileNotFoundError = FileNotFoundError  # NOQA
    FileExistsError = FileExistsError  # NOQA
else:
    # https://github.com/PythonCharmers/python-future/blob/exceptions/
    #     src/future/types/exceptions/pep3151.py
    import platform

    _SENTINEL = object()

    def _instance_checking_exception(base_exception=Exception):
        def wrapped(instance_checker):
            class TemporaryClass(base_exception):

                def __init__(self, *args, **kwargs):
                    if len(args) == 1 and isinstance(args[0], TemporaryClass):
                        unwrap_me = args[0]
                        for attr in dir(unwrap_me):
                            if not attr.startswith('__'):
                                setattr(self, attr, getattr(unwrap_me, attr))
                    else:
                        super(TemporaryClass, self).__init__(*args, **kwargs)

                class __metaclass__(type):
                    def __instancecheck__(cls, inst):
                        return instance_checker(inst)

                    def __subclasscheck__(cls, classinfo):
                        value = sys.exc_info()[1]
                        return isinstance(value, cls)

            TemporaryClass.__name__ = instance_checker.__name__
            TemporaryClass.__doc__ = instance_checker.__doc__
            return TemporaryClass

        return wrapped

    @_instance_checking_exception(EnvironmentError)
    def FileNotFoundError(inst):
        return getattr(inst, 'errno', _SENTINEL) == errno.ENOENT

    @_instance_checking_exception(EnvironmentError)
    def FileExistsError(inst):
        return getattr(inst, 'errno', _SENTINEL) == errno.EEXIST

    if platform.python_implementation() != "CPython":
        try:
            raise OSError(errno.EEXIST, "perm")
        except FileExistsError:
            pass
        except OSError:
            raise RuntimeError(
                "broken or incompatible Python implementation, see: "
                "https://github.com/giampaolo/psutil/issues/1659")
