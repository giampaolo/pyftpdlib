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

>>> from pyftpdlib.authorizers import DummyAuthorizer
>>> from pyftpdlib.handlers import FTPHandler
>>> from pyftpdlib.servers import FTPServer
>>>
>>> authorizer = DummyAuthorizer()
>>> authorizer.add_user("user", "12345", "/home/giampaolo", perm="elradfmw")
>>> authorizer.add_anonymous("/home/nobody")
>>>
>>> handler = FTPHandler
>>> handler.authorizer = authorizer
>>>
>>> server = FTPServer(("127.0.0.1", 21), handler)
>>> server.serve_forever()
[I 13-02-19 10:55:42] >>> starting FTP server on 127.0.0.1:21 <<<
[I 13-02-19 10:55:42] poller: <class 'pyftpdlib.ioloop.Epoll'>
[I 13-02-19 10:55:42] masquerade (NAT) address: None
[I 13-02-19 10:55:42] passive ports: None
[I 13-02-19 10:55:42] use sendfile(2): True
[I 13-02-19 10:55:45] 127.0.0.1:34178-[] FTP session opened (connect)
[I 13-02-19 10:55:48] 127.0.0.1:34178-[user] USER 'user' logged in.
[I 13-02-19 10:56:27] 127.0.0.1:34179-[user] RETR /home/giampaolo/.vimrc
                      completed=1 bytes=1700 seconds=0.001
[I 13-02-19 10:56:39] 127.0.0.1:34179-[user] FTP session closed (disconnect).
"""


__ver__ = '1.4.0'
__author__ = "Giampaolo Rodola' <g.rodola@gmail.com>"
__web__ = 'https://github.com/giampaolo/pyftpdlib/'


def _depwarn(msg):
    """
    Force DeprecationWarning to be temporarily shown (it's been
    disabled by default starting from python 2.7 / 3.2), then
    re-set the default behavior.
    """
    import warnings
    orig_filters = warnings.filters[:]
    try:
        # warnings.simplefilter('default')
        warnings.resetwarnings()
        warnings.warn(msg, category=DeprecationWarning, stacklevel=2)
    finally:
        warnings.filters = orig_filters
