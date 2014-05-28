#!/usr/bin/env python

#  ======================================================================
#  Copyright (C) 2007-2014 Giampaolo Rodola' <g.rodola@gmail.com>
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

"""
Note: this module is here only for backward compatibility.
The new import system which is supposed to be used is:

from pyftpdlib.handlers import FTPHandler, TLS_FTPHandler, ...
from pyftpdlib.authorizers import DummyAuthorizer, UnixAuthorizer, ...
from pyftpdlib.servers import FTPServer, ...
"""


from pyftpdlib.log import logger
from pyftpdlib.handlers import *  # NOQA
from pyftpdlib.authorizers import *  # NOQA
from pyftpdlib.servers import *  # NOQA

from pyftpdlib import _depwarn, __ver__  # NOQA

__all__ = ['proto_cmds', 'Error', 'log', 'logline', 'logerror',
           'DummyAuthorizer', 'AuthorizerError', 'FTPHandler', 'FTPServer',
           'PassiveDTP', 'ActiveDTP', 'DTPHandler', 'ThrottledDTPHandler',
           'FileProducer', 'BufferedIteratorProducer', 'AbstractedFS']

_depwarn("pyftpdlib.ftpserver module is deprecated")


class CallLater(object):
    def __init__(self, *args, **kwargs):
        _depwarn("CallLater is deprecated; use "
                 "pyftpdlib.ioloop.IOLoop.instance().call_later() instead")
        from pyftpdlib.ioloop import IOLoop
        IOLoop.instance().call_later(*args, **kwargs)


class CallEvery(object):
    def __init__(self, *args, **kwargs):
        _depwarn("CallEvery is deprecated; use "
                 "pyftpdlib.ioloop.IOLoop.instance().call_every() instead")
        from pyftpdlib.ioloop import IOLoop
        IOLoop.instance().call_every(*args, **kwargs)


def log(msg):
    _depwarn("pyftpdlib.ftpserver.log() is deprecated")
    logger.info(msg)


def logline(msg):
    _depwarn("pyftpdlib.ftpserver.logline() is deprecated")
    logger.debug(msg)


def logerror(msg):
    _depwarn("pyftpdlib.ftpserver.logline() is deprecated")
    logger.error(msg)


if __name__ == '__main__':
    from pyftpdlib import main
    main()
