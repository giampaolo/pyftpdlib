#!/usr/bin/env python
# unix_ftpd.py

# FTPd using local unix account database to authenticate users and get
# their home directories (users must be created previously).

import os
import pwd, spwd, crypt
from pyftpdlib import FTPServer

class unix_authorizer(FTPServer.dummy_authorizer):

    def __init__(self):
        FTPServer.dummy_authorizer.__init__(self)

    def add_user(self, username, home='', perm=('r')):
        assert username in [i[0] for i in pwd.getpwall()], 'No such user "%s".' %username
        pw = spwd.getspnam(username).sp_pwd
        if not home:
            home = pwd.getpwnam(username).pw_dir
        assert os.path.isdir(home), 'No such directory "%s".' %home
        dic = {'pwd'  : pw,
               'home' : home,
               'perm' : perm
               }
        self.user_table[username] = dic

    def validate_authentication(self, username, password):
        if username == 'anonymous':
            if self.has_user('anonymous'):
                return 1
            else:
                return 0
        else:
            pw1 = spwd.getspnam(username).sp_pwd
            pw2 = crypt.crypt(password, pw1)
            return pw1 == pw2

if __name__ == "__main__":
    authorizer = unix_authorizer()
    authorizer.add_user('user', perm=('r', 'w'))
    authorizer.add_anonymous(os.getcwd())
    ftp_handler = FTPServer.ftp_handler
    ftp_handler.authorizer = authorizer
    address = ('', 21)
    ftpd = FTPServer.ftp_server(address, ftp_handler)
    ftpd.serve_forever()
