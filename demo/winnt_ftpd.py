#!/usr/bin/env python
# winnt_ftpd.py

"""A ftpd using local Windows NT account database to authenticate users
(users must already exist).
"""

import os
import win32security, win32net, pywintypes

from pyftpdlib import ftpserver


class WinNtAuthorizer(ftpserver.DummyAuthorizer):

    def add_user(self, username, home=None, **kwargs):
        """Add a "real" system user to the virtual users table.
        If no home argument is specified the user's home directory will be used.
        The keyword arguments in kwargs are the same expected by add_user
        method: "perm", "msg_login" and "msg_quit".
        """
        # get the list of all available users on the system and check if
        # username provided exists
        users = [entry['name'] for entry in win32net.NetUserEnum(None, 0)[0]]
        if not username in users:
            raise ftpserver.AuthorizerError('No such user "%s".' %username)
        if not home:
            home = os.environ['USERPROFILE']
        ftpserver.DummyAuthorizer.add_user(self, username, '', home, **kwargs)

    def validate_authentication(self, username, password):
        try:
            win32security.LogonUser(username, None, password,
                win32security.LOGON32_LOGON_NETWORK,
                win32security.LOGON32_PROVIDER_DEFAULT)
            return 1
        except pywintypes.error:
            return 0

if __name__ == "__main__":
    authorizer = WinNtAuthorizer()
    # add a user (note: user must already exists)
    authorizer.add_user('user', perm=('r', 'w'))
    authorizer.add_anonymous(os.getcwd())
    ftp_handler = ftpserver.FTPHandler
    ftp_handler.authorizer = authorizer
    address = ('', 21)
    ftpd = ftpserver.FTPServer(address, ftp_handler)
    ftpd.serve_forever()
