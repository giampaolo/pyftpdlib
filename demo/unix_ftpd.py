#!/usr/bin/env python
# $Id$

"""A ftpd using local unix account database to authenticate users
(users must already exist).

It also provides a mechanism to (temporarily) impersonate the system
users every time they are going to perform filesystem operations.
"""

from pyftpdlib import ftpserver
from pyftpdlib.contrib.authorizers import UnixAuthorizer


def main():
    authorizer = UnixAuthorizer(rejected_users=["root"])
    ftp_handler = ftpserver.FTPHandler
    ftp_handler.authorizer = authorizer
    address = ('', 8021)
    ftpd = ftpserver.FTPServer(address, ftp_handler)
    ftpd.serve_forever()

if __name__ == "__main__":
    main()

