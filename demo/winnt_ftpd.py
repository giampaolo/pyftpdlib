#!/usr/bin/env python
# $Id$

"""A ftpd using local Windows NT account database to authenticate users
(users must already exist).

It also provides a mechanism to (temporarily) impersonate the system
users every time they are going to perform filesystem operations.
"""

from pyftpdlib import ftpserver
from pyftpdlib.contrib.authorizers import WindowsAuthorizer


def main():
    authorizer = WindowsAuthorizer()
    # Use Guest user with empty password to handle anonymous sessions.
    # Guest user must be enabled first, empty password set and profile
    # directory specified.
    #authorizer = WindowsAuthorizer(anonymous_user="Guest", anonymous_password="")
    ftp_handler = ftpserver.FTPHandler
    ftp_handler.authorizer = authorizer
    address = ('', 21)
    ftpd = ftpserver.FTPServer(address, ftp_handler)
    ftpd.serve_forever()

if __name__ == "__main__":
    main()
