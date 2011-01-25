#!/usr/bin/env python
# $Id$

"""A basic ftpd storing passwords as hash digests (platform independent).
"""

import os
try:
    from hashlib import md5
except ImportError:
    # backward compatibility with Python < 2.5
    from md5 import new as md5

from pyftpdlib import ftpserver


class DummyMD5Authorizer(ftpserver.DummyAuthorizer):

    def validate_authentication(self, username, password):
        hash = md5(password).hexdigest()
        return self.user_table[username]['pwd'] == hash


def main():
    # get a hash digest from a clear-text password
    hash = md5('12345').hexdigest()
    authorizer = DummyMD5Authorizer()
    authorizer.add_user('user', hash, os.getcwd(), perm='elradfmw')
    authorizer.add_anonymous(os.getcwd())
    ftp_handler = ftpserver.FTPHandler
    ftp_handler.authorizer = authorizer
    address = ('', 21)
    ftpd = ftpserver.FTPServer(address, ftp_handler)
    ftpd.serve_forever()

if __name__ == "__main__":
    main()
