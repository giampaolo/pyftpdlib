#!/usr/bin/env python
# $Id$

#  ======================================================================
#  Copyright (C) 2007-2012 Giampaolo Rodola' <g.rodola@gmail.com>
#
#                         All Rights Reserved
#
# Permission is hereby granted, free of charge, to any person
# obtaining a copy of this software and associated documentation
# files (the "Software"), to deal in the Software without
# restriction, including without limitation the rights to use,
# copy, modify, merge, publish, distribute, sublicense, and/or sell
# copies of the Software, and to permit persons to whom the
# Software is furnished to do so, subject to the following
# conditions:
#
# The above copyright notice and this permission notice shall be
# included in all copies or substantial portions of the Software.
#
# THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND,
# EXPRESS OR IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES
# OF MERCHANTABILITY, FITNESS FOR A PARTICULAR PURPOSE AND
# NONINFRINGEMENT. IN NO EVENT SHALL THE AUTHORS OR COPYRIGHT
# HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER LIABILITY,
# WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING
# FROM, OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR
# OTHER DEALINGS IN THE SOFTWARE.
#
#  ======================================================================

import sys
import os

from pyftpdlib._compat import PY3, print_

# --- loggers

def log(msg):
    """Log messages intended for the end user."""
#    print_(msg)  # XXX

def logline(msg):
    """Log commands and responses passing through the command channel."""
#    print_(msg)  # XXX

def logerror(msg):
    """Log traceback outputs occurring in case of errors."""
    sys.stderr.write(str(msg) + '\n')
    sys.stderr.flush()

# dirty hack which overwrites base ioloop's error logger
import pyftpdlib.ioloop
pyftpdlib.ioloop.logerror = logerror


# Hack for Windows console which is not able to print all unicode strings.
# http://bugs.python.org/issue1602
# http://stackoverflow.com/questions/5419/
if os.name in ('nt', 'ce'):
    def _safeprint(s, errors='replace'):
        try:
            print_(s)
        except UnicodeEncodeError:
            if PY3:
                print_(s.encode('utf8').decode(sys.stdout.encoding),
                       errors=errors)
            else:
                print_(s.encode('utf8', errors))
    log = logline = _safeprint
