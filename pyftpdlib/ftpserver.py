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

"""
Note: this module is here only for backward compatibility.
The new import system which is supposed to be used is:

from pyftpdlib.handlers import FTPHandler, TLS_FTPHandler, ...
from pyftpdlib.authorizers import DummyAuthorizer, UnixAuthorizer, ...
from pyftpdlib.servers import FTPServer, ...
"""

import logging

from pyftpdlib.handlers import *
from pyftpdlib.authorizers import *
from pyftpdlib.servers import *

from pyftpdlib import _depwarn, __ver__

__all__ = ['proto_cmds', 'Error', 'log', 'logline', 'logerror', 'DummyAuthorizer',
           'AuthorizerError', 'FTPHandler', 'FTPServer', 'PassiveDTP',
           'ActiveDTP', 'DTPHandler', 'ThrottledDTPHandler', 'FileProducer',
           'BufferedIteratorProducer', 'AbstractedFS']

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
    logging.info(msg)

def logline(msg):
    _depwarn("pyftpdlib.ftpserver.logline() is deprecated")
    logging.debug(msg)

def logerror(msg):
    _depwarn("pyftpdlib.ftpserver.logline() is deprecated")
    logging.error(msg)

def main():
    """Start a stand alone anonymous FTP server."""
    import optparse
    import sys
    import os

    from pyftpdlib.authorizers import DummyAuthorizer
    from pyftpdlib.handlers import FTPHandler
    from pyftpdlib.servers import FTPServer
    from pyftpdlib._compat import getcwdu

    class CustomizedOptionFormatter(optparse.IndentedHelpFormatter):
        """Formats options shown in help in a prettier way."""

        def format_option(self, option):
            result = []
            opts = self.option_strings[option]
            result.append('  %s\n' % opts)
            if option.help:
                help_text = '     %s\n\n' % self.expand_default(option)
                result.append(help_text)
            return ''.join(result)

    usage = "python -m pyftpdlib.ftpserver [options]"
    parser = optparse.OptionParser(usage=usage, description=main.__doc__,
                                   formatter=CustomizedOptionFormatter())
    parser.add_option('-i', '--interface', default='', metavar="ADDRESS",
                      help="specify the interface to run on (default all "
                           "interfaces)")
    parser.add_option('-p', '--port', type="int", default=21, metavar="PORT",
                      help="specity port number to run on (default 21)")
    parser.add_option('-w', '--write', action="store_true", default=False,
                      help="grants write access for the anonymous user "
                           "(default read-only)")
    parser.add_option('-d', '--directory', default=getcwdu(), metavar="FOLDER",
                      help="specify the directory to share (default current "
                           "directory)")
    parser.add_option('-n', '--nat-address', default=None, metavar="ADDRESS",
                      help="the NAT address to use for passive connections")
    parser.add_option('-r', '--range', default=None, metavar="FROM-TO",
                      help="the range of TCP ports to use for passive "
                           "connections (e.g. -r 8000-9000)")
    parser.add_option('-v', '--version', action='store_true',
                      help="print pyftpdlib version and exit")

    options, args = parser.parse_args()
    if options.version:
        sys.exit("pyftpdlib %s" % __ver__)
    passive_ports = None
    if options.range:
        try:
            start, stop = options.range.split('-')
            start = int(start)
            stop = int(stop)
        except ValueError:
            parser.error('invalid argument passed to -r option')
        else:
            passive_ports = list(range(start, stop + 1))
    # On recent Windows versions, if address is not specified and IPv6
    # is installed the socket will listen on IPv6 by default; in this
    # case we force IPv4 instead.
    if os.name in ('nt', 'ce') and not options.interface:
        options.interface = '0.0.0.0'

    authorizer = DummyAuthorizer()
    perm = options.write and "elradfmwM" or "elr"
    authorizer.add_anonymous(options.directory, perm=perm)
    handler = FTPHandler
    handler.authorizer = authorizer
    handler.masquerade_address = options.nat_address
    handler.passive_ports = passive_ports
    ftpd = FTPServer((options.interface, options.port), FTPHandler)
    ftpd.serve_forever()

if __name__ == '__main__':
    main()
