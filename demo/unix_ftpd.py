#!/usr/bin/env python
# unix_ftpd.py

"""A ftpd using local unix account database to authenticate users and get
their home directories (users must already exist).
"""

import os
import pwd, spwd, crypt

from pyftpdlib import ftpserver


class UnixAuthorizer(ftpserver.DummyAuthorizer):

    def add_user(self, username, home='', perm=('r')):
        # get the list of all available users on the system and check if
        # username provided exists
        users = [entry.pw_name for entry in pwd.getpwall()]
        if not username in users:
             raise ftpserver.AuthorizerError('No such user "%s".' %username)
        ftpserver.DummyAuthorizer.add_user(self, username, '', home, perm)

    def validate_authentication(self, username, password):
        pw1 = spwd.getspnam(username).sp_pwd
        pw2 = crypt.crypt(password, pw1)
        return pw1 == pw2

if __name__ == "__main__":
    authorizer = UnixAuthorizer()
    # add a user (note: user must already exists)
    authorizer.add_user('user', perm=('r', 'w'))
    authorizer.add_anonymous(os.getcwd())
    ftp_handler = ftpserver.FTPHandler
    ftp_handler.authorizer = authorizer
    address = ('', 21)
    ftpd = ftpserver.FTPServer(address, ftp_handler)
    ftpd.serve_forever()
