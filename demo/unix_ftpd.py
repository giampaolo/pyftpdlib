#!/usr/bin/env python
# $Id$

"""A FTPd using local UNIX account database to authenticate users.

It temporarily impersonate the system users every time they are going
to perform a filesystem operations.
"""

from pyftpdlib import ftpserver
from pyftpdlib.contrib.authorizers import UnixAuthorizer
from pyftpdlib.contrib.filesystems import UnixFilesystem


def main():
    authorizer = UnixAuthorizer(rejected_users=["root"])
    ftp_handler = ftpserver.FTPHandler
    ftp_handler.authorizer = authorizer
    ftp_handler.abstracted_fs = UnixFilesystem
    address = ('', 21)
    ftpd = ftpserver.FTPServer(address, ftp_handler)
    ftpd.serve_forever()

if __name__ == "__main__":
    main()

