#!/usr/bin/env python
# $Id$

"""
Compatibility module similar to six which helps maintaining
a single code base working with python from 2.4 to 3.x.
"""

import sys
import os

PY3 = sys.version_info[0] == 3

if PY3:
    import builtins

    def u(s):
        return s

    def b(s):
        return s.encode("latin-1")

    print_ = getattr(builtins, "print")
    getcwdu = os.getcwd
    unicode = str
    xrange = range
else:
    def u(s):
        return unicode(s)

    def b(s):
        return s

    def print_(s):
        sys.stdout.write(s + '\n')
        sys.stdout.flush()

    getcwdu = os.getcwdu
    unicode = unicode
    xrange = xrange

# introduced in 2.6
if hasattr(sys, 'maxsize'):
    MAXSIZE = sys.maxsize
else:
    class X(object):
        def __len__(self):
            return 1 << 31
    try:
        len(X())
    except OverflowError:
        MAXSIZE = int((1 << 31) - 1)  # 32-bit
    else:
        MAXSIZE = int((1 << 63) - 1)  # 64-bit
    del X

# removed in 3.0, reintroduced in 3.2
try:
    callable = callable
except Exception:
    def callable(obj):
        for klass in type(obj).__mro__:
            if "__call__" in klass.__dict__:
                return True
        return False

# introduced in 2.6
_default = object()
try:
    next = next
except NameError:
    def next(iterable, default=_default):
        if default == _default:
            return iterable.next()
        else:
            try:
                return iterable.next()
            except StopIteration:
                return default
