#!/usr/bin/env python
# $Id$

"""An "authorizer" is a class handling authentications and permissions
of the FTP server. It is used by pyftpdlib.ftpserver.FTPHandler
class for:

- verifying user's passwords
- getting user home directories
- checking user permissions when a filesystem read/write event occurs
- changing user when accessing the filesystem

This module contains a serie of classes which implements such
functionalities in a system-specific way for both Unix and Windows.
Both implementations share the same API and functionalities.
"""

__all__ = []


import os

from pyftpdlib.ftpserver import DummyAuthorizer, AuthorizerError


try:
    import pwd, spwd, crypt
except ImportError:
    pass
else:
    # the uid/gid the server runs under
    PROCESS_UID = os.getuid()
    PROCESS_GID = os.getgid()

    class UnixAuthorizer(DummyAuthorizer):
        """An authorizer compatible with Unix user account and password
        database.

        Every user must be explicitly added via add_user() method and it
        must first exists in the system.
        Every time a filesystem operation occurs (e.g. a file is created
        or renamed) the id of the process is temporarily changed to
        the effective user id.

        In order to use this class super user (root) privileges are
        required.
        """

        def __init__(self):
            if os.geteuid() != 0 or not spwd.getspall():
                raise RuntimeError("root privileges are required")
            DummyAuthorizer.__init__(self)
            self._anon_user = ''
            self._dynamic_home_users = []

        def add_user(self, username, homedir=None, **kwargs):
            """Add a "real" system user to the virtual users table.

             - (string) homedir:
                The user home directory.  If this is not specified the
                real user home directory will be determined (if any)
                and used.

             - (dict) **kwargs:
                the same keyword arguments expected by the original
                add_user method: "perm", "msg_login" and "msg_quit".
            """
            # get the list of all available users on the system and check
            # if provided username exists
            users = [entry.pw_name for entry in pwd.getpwall()]
            if not username in users:
                raise AuthorizerError('No such user "%s".' %username)
            if not homedir:
                homedir = pwd.getpwnam(username).pw_dir
                self._dynamic_home_users.append(username)
            DummyAuthorizer.add_user(self, username, '', homedir, **kwargs)

        def add_anonymous(self, homedir=None, realuser="ftp", **kwargs):
            """Add an anonymous user to the virtual users table.

             - (string) homedir:
                The anonymous user home directory.  If this is not
                specified the "realuser" home directory will be
                determined (if any) and used.

             - (string) realuser:
                specifies the system user to use for managing anonymous
                sessions.  On some UNIX systems "ftp" is available and
                usually used by end-user FTP servers but it can vary
                (e.g. "nobody").

             - (dict) **kwargs:
                the same keyword arguments expected by the original
                add_user method: "perm", "msg_login" and "msg_quit".
            """
            users = [entry.pw_name for entry in pwd.getpwall()]
            if not realuser in users:
                raise AuthorizerError('No such user "%s".' %realuser)
            if not homedir:
                homedir = pwd.getpwnam(realuser).pw_dir
                self._dynamic_home_users.append(realuser)
            DummyAuthorizer.add_anonymous(self, homedir, **kwargs)
            self._anon_user = realuser

        def get_home_dir(self, username):
            if username not in self._dynamic_home_users:
                return self.user_table[username]['home']
            else:
                if (username == "anonymous") and self.has_user('anonymous'):
                    username = self._anon_user
                try:
                    return pwd.getpwnam(username).pw_dir
                except KeyError:
                    raise AuthorizerError('No such user %s' % username)

        def validate_authentication(self, username, password):
            if (username == "anonymous") and self.has_user('anonymous'):
                return True
            try:
                pw1 = spwd.getspnam(username).sp_pwd
                pw2 = crypt.crypt(password, pw1)
            except KeyError:
                return False
            else:
                return pw1 == pw2

        def impersonate_user(self, username, password):
            if (username == "anonymous") and self.has_user('anonymous'):
                username = self._anon_user
            try:
                uid = pwd.getpwnam(username).pw_uid
                gid = pwd.getpwnam(username).pw_gid
            except KeyError:
                raise AuthorizerError('No such user %s' % username)
            os.setegid(gid)
            os.seteuid(uid)

        def terminate_impersonation(self):
            os.setegid(PROCESS_GID)
            os.seteuid(PROCESS_UID)

    __all__.append('UnixAuthorizer')


