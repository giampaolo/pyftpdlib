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
pyftpdlib: RFC-959 asynchronous FTP server.

pyftpdlib implements a fully functioning asynchronous FTP server as
defined in RFC-959.  A hierarchy of classes outlined below implement
the backend functionality for the FTPd:

    [pyftpdlib.ftpservers.FTPServer]
      accepts connections and dispatches them to a handler

    [pyftpdlib.handlers.FTPHandler]
      a class representing the server-protocol-interpreter
      (server-PI, see RFC-959). Each time a new connection occurs
      FTPServer will create a new FTPHandler instance to handle the
      current PI session.

    [pyftpdlib.handlers.ActiveDTP]
    [pyftpdlib.handlers.PassiveDTP]
      base classes for active/passive-DTP backends.

    [pyftpdlib.handlers.DTPHandler]
      this class handles processing of data transfer operations (server-DTP,
      see RFC-959).

    [pyftpdlib.authorizers.DummyAuthorizer]
      an "authorizer" is a class handling FTPd authentications and
      permissions. It is used inside FTPHandler class to verify user
      passwords, to get user's home directory and to get permissions
      when a filesystem read/write occurs. "DummyAuthorizer" is the
      base authorizer class providing a platform independent interface
      for managing virtual users.

    [pyftpdlib.filesystems.AbstractedFS]
      class used to interact with the file system, providing a high level,
      cross-platform interface compatible with both Windows and UNIX style
      filesystems.

Usage example:

>>> from pyftpdlib.authorizer import DummyAuthorizer
>>> from pyftpdlib.handlers import FTPHandler
>>> from pyftpdlib.servers import FTPServer
>>>
>>> authorizer = DummyAuthorizer()
>>> authorizer.add_user('user', 'password', '/home/user', perm='elradfmw')
>>> authorizer.add_anonymous('/home/nobody')
>>>
>>> handler = FTPHandler
>>> handler.authorizer = authorizer
>>>
>>> server = FTPServer(("127.0.0.1", 21), handler)
>>> server.serve_forever()
[I] []127.0.0.1:2503 connected.
[D] 127.0.0.1:2503 -> 220 Ready.
[D] 127.0.0.1:2503 <- USER anonymous
[D] 127.0.0.1:2503 -> 331 Username ok, send password.
[D] 127.0.0.1:2503 <- PASS ******
[D] 127.0.0.1:2503 -> 230 Login successful.
[I] [anonymous]@127.0.0.1:2503 User anonymous logged in.
[D] 127.0.0.1:2503 <- TYPE A
[D] 127.0.0.1:2503 -> 200 Type set to: ASCII.
[D] 127.0.0.1:2503 <- PASV
[D] 127.0.0.1:2503 -> 227 Entering passive mode (127,0,0,1,9,201).
[D] 127.0.0.1:2503 <- LIST
[D] 127.0.0.1:2503 -> 150 File status okay. About to open data connection.
[I] [anonymous]@127.0.0.1:2503 OK LIST "/". Transfer starting.
[D] 127.0.0.1:2503 -> 226 Transfer complete.
[D] [anonymous]@127.0.0.1:2503 Transfer complete. 706 bytes transmitted.
[D] 127.0.0.1:2503 <- QUIT
[D] 127.0.0.1:2503 -> 221 Goodbye.
[I] [anonymous]@127.0.0.1:2503 Disconnected.
"""

__ver__     = '1.0.0'
__date__    = 'XXXX-XX-XX'
__author__  = "Giampaolo Rodola' <g.rodola@gmail.com>"
__web__     = 'http://code.google.com/p/pyftpdlib/'


def _depwarn(msg):
    """
    Force DeprecationWarning to be temporarily shown (it's been
    disabled by default starting from python 2.7 / 3.2), then
    re-set the default behavior.
    """
    import warnings
    orig_filters = warnings.filters[:]
    try:
        #warnings.simplefilter('default')
        warnings.resetwarnings()
        warnings.warn(msg, category=DeprecationWarning, stacklevel=2)
    finally:
        warnings.filters = orig_filters

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
