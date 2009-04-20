#!/usr/bin/env python
# $Id$

"""A ftpd using local unix account database to authenticate users
(users must already exist).

It also provides a mechanism to (temporarily) impersonate the system
users every time they are going to perform filesystem operations.
"""

import os
import pwd, spwd, crypt

from pyftpdlib import ftpserver


class UnixAuthorizer(ftpserver.DummyAuthorizer):

    # the uid/gid the daemon runs under
    PROCESS_UID = os.getuid()
    PROCESS_GID = os.getgid()

    def __init__(self):
        ftpserver.DummyAuthorizer.__init__(self)
        self._anon_user = ''
        self._dynamic_home_users = []

    def add_user(self, username, homedir=None, **kwargs):
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
        if not homedir:
            homedir = pwd.getpwnam(username).pw_dir
            self._dynamic_home_users.append(username)
        ftpserver.DummyAuthorizer.add_user(self, username, '', homedir,**kwargs)

    def add_anonymous(self, homedir=None, realuser="ftp", **kwargs):
        """Add an anonymous user to the virtual users table.

        If no homedir argument is specified the realuser's home
        directory will possibly be determined and used.

        realuser argument specifies the system user to use for managing
        anonymous sessions.  On many UNIX systems "ftp" is tipically
        used but it may change (e.g. "nobody").
        """
        users = [entry.pw_name for entry in pwd.getpwall()]
        if not realuser in users:
            raise ftpserver.AuthorizerError('No such user "%s".' %realuser)
        if not homedir:
            homedir = pwd.getpwnam(realuser).pw_dir
            self._dynamic_home_users.append(realuser)
        ftpserver.DummyAuthorizer.add_anonymous(self, homedir, **kwargs)
        self._anon_user = realuser

    def get_home_dir(self, username):
        if username not in self._dynamic_home_users:
            return self.user_table[username]['home']
        else:
            if (username == "anonymous") and self.has_user('anonymous'):
                username = self._anon_user
            return pwd.getpwnam(username).pw_dir

    def validate_authentication(self, username, password):
        if (username == "anonymous") and self.has_user('anonymous'):
            username = self._anon_user
        pw1 = spwd.getspnam(username).sp_pwd
        pw2 = crypt.crypt(password, pw1)
        return pw1 == pw2

    def impersonate_user(self, username, password):
        if (username == "anonymous") and self.has_user('anonymous'):
            username = self._anon_user
        uid = pwd.getpwnam(username).pw_uid
        gid = pwd.getpwnam(username).pw_gid
        os.setegid(gid)
        os.seteuid(uid)

    def terminate_impersonation(self):
        os.setegid(self.PROCESS_GID)
        os.seteuid(self.PROCESS_UID)


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
