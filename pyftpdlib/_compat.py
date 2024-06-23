# Copyright (C) 2007 Giampaolo Rodola' <g.rodola@gmail.com>.
# Use of this source code is governed by MIT license that can be
# found in the LICENSE file.

"""
Compatibility module similar to six lib, which helps maintaining
a single code base working with both python 2.7 and 3.x.
"""

import sys


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
