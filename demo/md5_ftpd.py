#!/usr/bin/env python
# md5_ftpd.py

# FTPd storing passwords as hash digest (platform independent).

from pyftpdlib import FTPServer
import md5
import os

class dummy_encrypted_authorizer(FTPServer.dummy_authorizer):
         
    def __init__(self):
        FTPServer.dummy_authorizer.__init__(self)
 
    def validate_authentication(self, username, password):
        if username == 'anonymous':
            if self.has_user('anonymous'):
                return 1
        hash = md5.new(password).hexdigest()
        return self.user_table[username]['pwd'] == hash
 
if __name__ == "__main__":
    hash = md5.new('12345').hexdigest()
    authorizer = dummy_encrypted_authorizer()
    authorizer.add_user('user', hash, os.getcwd(), perm=('r', 'w'))
 
    ftp_handler = FTPServer.ftp_handler
    ftp_handler.authorizer = authorizer
    address = ('', 21)
    ftpd = FTPServer.ftp_server(address, ftp_handler)
    ftpd.serve_forever()
