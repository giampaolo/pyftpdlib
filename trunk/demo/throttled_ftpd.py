#!/usr/bin/env python
# $Id$

"""An FTP server which uses the ThrottledDTPHandler class for limiting the
speed of downloads and uploads.
"""

import os

from pyftpdlib import ftpserver


def main():
    authorizer = ftpserver.DummyAuthorizer()
    authorizer.add_user('user', '12345', os.getcwd(), perm='elradfmw')
    authorizer.add_anonymous(os.getcwd())

    dtp_handler = ftpserver.ThrottledDTPHandler
    dtp_handler.read_limit = 30720  # 30 Kb/sec (30 * 1024)
    dtp_handler.write_limit = 30720  # 30 Kb/sec (30 * 1024)

    ftp_handler = ftpserver.FTPHandler
    ftp_handler.authorizer = authorizer
    # have the ftp handler use the alternative dtp handler class
    ftp_handler.dtp_handler = dtp_handler

    ftpd = ftpserver.FTPServer(('', 21), ftp_handler)
    ftpd.serve_forever()

if __name__ == '__main__':
    main()

