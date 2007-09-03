#!/usr/bin/env python
# winNT_ftpd.py

"""FTPd using local Windows NT account database to authenticate users
(users must be created previously).
"""

import os
import win32security, win32net, pywintypes
from pyftpdlib import ftpserver


class WinNtAuthorizer(ftpserver.DummyAuthorizer):

    def __init__(self):
        ftpserver.DummyAuthorizer.__init__(self)

    def add_user(self, username, home, perm=('r')):
        # check if user exists
        users = [elem['name'] for elem in win32net.NetUserEnum(None, 0)[0]]
        assert username in users, 'No such user "%s".' %username
        assert os.path.isdir(home), 'No such directory "%s".' %home
        dic = {'pwd'  : None,
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
            try:
                # check credentials
                win32security.LogonUser (
                    username,
                    None,
                    password,
                    win32security.LOGON32_LOGON_NETWORK,
                    win32security.LOGON32_PROVIDER_DEFAULT
                    )
                return 1
            except pywintypes.error, err:
                return 0


if __name__ == "__main__":
    authorizer = WinNtAuthorizer()
    # add a user (note: user must already exists)
    authorizer.add_user ('user', os.getcwd(),perm=('r', 'w'))
    authorizer.add_anonymous (os.getcwd())
    ftp_handler = ftpserver.FTPHandler
    ftp_handler.authorizer = authorizer
    address = ('', 21)
    ftpd = ftpserver.FTPServer(address, ftp_handler)
    ftpd.serve_forever()
