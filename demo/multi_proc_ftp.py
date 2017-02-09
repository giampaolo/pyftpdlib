#!/usr/bin/env python

# Copyright (C) 2007 Giampaolo Rodola' <g.rodola@gmail.com>.
# Use of this source code is governed by MIT license that can be
# found in the LICENSE file.

"""
A FTP server which handles every connection in a separate process.
Useful if your handler class contains blocking calls or your
filesystem is too slow.

POSIX only; requires python >= 2.6.
"""

from pyftpdlib.authorizers import DummyAuthorizer
from pyftpdlib.handlers import FTPHandler
from pyftpdlib.servers import MultiprocessFTPServer


def main():
    authorizer = DummyAuthorizer()
    authorizer.add_user('user', '12345', '.')
    handler = FTPHandler
    handler.authorizer = authorizer
    server = MultiprocessFTPServer(('', 2121), handler)
    server.serve_forever()


if __name__ == "__main__":
    main()
