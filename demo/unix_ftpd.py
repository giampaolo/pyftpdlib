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
    authorizer = UnixAuthorizer()
    # add a user (note: user must already exists)
    authorizer.add_user('giampaolo', perm='elradfmw')
    # add an anonymous user forcing its home directory
    authorizer.add_anonymous(realuser="ftp", homedir="/home/ftp")

    ftp_handler = ftpserver.FTPHandler
    ftp_handler.authorizer = authorizer
    address = ('', 21)
    ftpd = ftpserver.FTPServer(address, ftp_handler)
    ftpd.serve_forever()

if __name__ == "__main__":
    main()

