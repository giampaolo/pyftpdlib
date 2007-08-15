#!/usr/bin/env python
# md5_ftpd.py

"""A basic FTPd storing passwords as hash digests (platform independent).
"""

import md5
import os
from pyftpdlib import FTPServer

class DummyMD5Authorizer(FTPServer.DummyAuthorizer):

    def __init__(self):
        FTPServer.DummyAuthorizer.__init__(self)
 
    def validate_authentication(self, username, password):
        if username == 'anonymous':
            if self.has_user('anonymous'):
                return 1
            else:
                return 0
        hash = md5.new(password).hexdigest()
        return self.user_table[username]['pwd'] == hash
 
if __name__ == "__main__":
    # get a hash digest from a clear-text password
    hash = md5.new('12345').hexdigest()
    authorizer = DummyMD5Authorizer()
    authorizer.add_user('user', hash, os.getcwd(), perm=('r', 'w'))
    authorizer.add_anonymous(os.getcwd())    
    ftp_handler = FTPServer.FTPHandler
    ftp_handler.authorizer = authorizer
    address = ('', 21)
    ftpd = FTPServer.FTPServer(address, ftp_handler)
    ftpd.serve_forever()
