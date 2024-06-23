# Copyright (C) 2007 Giampaolo Rodola' <g.rodola@gmail.com>.
# Use of this source code is governed by MIT license that can be
# found in the LICENSE file.

"""
Compatibility module similar to six lib, which helps maintaining
a single code base working with both python 2.7 and 3.x.
"""

import sys
import types


PY3 = sys.version_info[0] >= 3
_SENTINEL = object()

if PY3:

    def u(s):
        return s

    def b(s):
        return s.encode("latin-1")

    unicode = str
else:

    def u(s):
        return unicode(s)

    def b(s):
        return s

    unicode = unicode

# Python 3 super().
# Taken from "future" package.
# Credit: Ryan Kelly
if PY3:
    super = super
else:
    _builtin_super = super

    def super(type_=_SENTINEL, type_or_obj=_SENTINEL, framedepth=1):
        """Like Python 3 builtin super(). If called without any arguments
        it attempts to infer them at runtime.
        """
        if type_ is _SENTINEL:
            f = sys._getframe(framedepth)
            try:
                # Get the function's first positional argument.
                type_or_obj = f.f_locals[f.f_code.co_varnames[0]]
            except (IndexError, KeyError):
                raise RuntimeError('super() used in a function with no args')
            try:
                # Get the MRO so we can crawl it.
                mro = type_or_obj.__mro__
            except (AttributeError, RuntimeError):
                try:
                    mro = type_or_obj.__class__.__mro__
                except AttributeError:
                    raise RuntimeError('super() used in a non-newstyle class')
            for type_ in mro:
                #  Find the class that owns the currently-executing method.
                for meth in type_.__dict__.values():
                    # Drill down through any wrappers to the underlying func.
                    # This handles e.g. classmethod() and staticmethod().
                    try:
                        while not isinstance(meth, types.FunctionType):
                            if isinstance(meth, property):
                                # Calling __get__ on the property will invoke
                                # user code which might throw exceptions or
                                # have side effects
                                meth = meth.fget
                            else:
                                try:
                                    meth = meth.__func__
                                except AttributeError:
                                    meth = meth.__get__(type_or_obj, type_)
                    except (AttributeError, TypeError):
                        continue
                    if meth.func_code is f.f_code:
                        break  # found
                else:
                    # Not found. Move onto the next class in MRO.
                    continue
                break  # found
            else:
                raise RuntimeError('super() called outside a method')

        # Dispatch to builtin super().
        if type_or_obj is not _SENTINEL:
            return _builtin_super(type_, type_or_obj)
        return _builtin_super(type_)
