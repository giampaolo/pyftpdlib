#!/usr/bin/env python
# unix_ftpd.py

"""A ftpd using local unix account database to authenticate users
(users must already exist).
"""

import os
import pwd, spwd, crypt

from pyftpdlib import ftpserver


class UnixAuthorizer(ftpserver.DummyAuthorizer):

    def add_user(self, username, home=None, **kwargs):
        """Add a "real" system user to the virtual users table.
        
        If no home argument is specified the user's home directory will
        be used.
        The keyword arguments in kwargs are the same expected by the
        original add_user method: "perm", "msg_login" and "msg_quit".
        """
        # get the list of all available users on the system and check
        # if provided username exists
        users = [entry.pw_name for entry in pwd.getpwall()]
        if not username in users:
            raise ftpserver.AuthorizerError('No such user "%s".' %username)
        if not home:
            home = pwd.getpwnam(username).pw_dir
        ftpserver.DummyAuthorizer.add_user(self, username, '', home, **kwargs)

    def validate_authentication(self, username, password):
        pw1 = spwd.getspnam(username).sp_pwd
        pw2 = crypt.crypt(password, pw1)
        return pw1 == pw2

if __name__ == "__main__":
    authorizer = UnixAuthorizer()
    # add a user (note: user must already exists)
    authorizer.add_user('user', perm='elradfmw')
    authorizer.add_anonymous(os.getcwd())
    ftp_handler = ftpserver.FTPHandler
    ftp_handler.authorizer = authorizer
    address = ('', 21)
    ftpd = ftpserver.FTPServer(address, ftp_handler)
    ftpd.serve_forever()
