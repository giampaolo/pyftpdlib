#!/usr/bin/env python
# md5_ftpd.py

"""A basic ftpd storing passwords as hash digests (platform independent).
"""

import md5
import os

from pyftpdlib import ftpserver


class DummyMD5Authorizer(ftpserver.DummyAuthorizer):

    def validate_authentication(self, username, password):
        hash = md5.new(password).hexdigest()
        return self.user_table[username]['pwd'] == hash

if __name__ == "__main__":
    # get a hash digest from a clear-text password
    hash = md5.new('12345').hexdigest()
    authorizer = DummyMD5Authorizer()
    authorizer.add_user('user', hash, os.getcwd(), perm='elradfmw')
    authorizer.add_anonymous(os.getcwd())
    ftp_handler = ftpserver.FTPHandler
    ftp_handler.authorizer = authorizer
    address = ('', 21)
    ftpd = ftpserver.FTPServer(address, ftp_handler)
    ftpd.serve_forever()
