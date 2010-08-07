#!/usr/bin/env python
# $Id$

"""An "authorizer" is a class handling authentications and permissions
of the FTP server. It is used by pyftpdlib.ftpserver.FTPHandler
class for:

- verifying user's passwords
- getting user home directories
- checking user permissions when a filesystem read/write event occurs
- changing user when accessing the filesystem

This module contains a series of classes which implements such
functionalities in a system-specific way for both Unix and Windows.
Both implementations share the same API and functionalities.
"""

__all__ = []


import os

from pyftpdlib.ftpserver import DummyAuthorizer, AuthorizerError


def replace_anonymous(callable):
    def wrapper(self, username, *args, **kwargs):
        if username == 'anonymous':
            username = self.anonymous_user or username
        return callable(self, username, *args, **kwargs)
    return wrapper


try:
    import pwd, spwd, crypt
except ImportError:
    pass
else:
    # the uid/gid the server runs under
    PROCESS_UID = os.getuid()
    PROCESS_GID = os.getgid()

    class BaseUnixAuthorizer:
        """A basic authorizer compatible with Unix user account and
        password database which does not provide any configurable
        option.

        This class can be used as a base class to build more complex
        authorizers.
        """

        def __init__(self, anonymous_user=None):
            if os.geteuid() != 0 or not spwd.getspall():
                raise AuthorizerError("super user privileges are required")
            self.anonymous_user = anonymous_user
            if anonymous_user is not None:
                if not self.has_user(anonymous_user):
                    raise AuthorizerError('no such user %s' % anonymous_user)
                home = pwd.getpwnam(anonymous_user).pw_dir
                if not os.path.isdir(home):
                    raise AuthorizerError('no valid home set for user %s'
                                          % anonymous_user)

        @replace_anonymous
        def validate_authentication(self, username, password):
            """Authenticates against shadow password db; return
            True on success.
            """
            try:
                pw1 = spwd.getspnam(username).sp_pwd
                pw2 = crypt.crypt(password, pw1)
            except KeyError:
                return False
            else:
                return pw1 == pw2

        @replace_anonymous
        def impersonate_user(self, username, password):
            """Change process effective user/group ids to reflect
            logged in user.
            """
            try:
                uid = pwd.getpwnam(username).pw_uid
                gid = pwd.getpwnam(username).pw_gid
            except KeyError:
                raise AuthorizerError('no such user %s' % username)
            os.setegid(gid)
            os.seteuid(uid)

        def terminate_impersonation(self):
            """Revert process effective user/group ids."""
            os.setegid(PROCESS_GID)
            os.seteuid(PROCESS_UID)

        @replace_anonymous
        def has_user(self, username):
            return username in [entry.pw_name for entry in pwd.getpwall()]

        @replace_anonymous
        def get_home_dir(self, username):
            try:
                return pwd.getpwnam(username).pw_dir
            except KeyError:
                raise AuthorizerError('no such user %s' % username)

        def get_msg_login(self, username):
            raise NotImplementedError("must be implemented in subclass")

        def get_msg_quit(self, username):
            raise NotImplementedError("must be implemented in subclass")

        def get_perms(self, username):
            raise NotImplementedError("must be implemented in subclass")

        def has_perm(self, username, perm, path=None):
            raise NotImplementedError("must be implemented in subclass")


    class UnixAuthorizer(BaseUnixAuthorizer):
        """An authorizer compatible with Unix user account and password
        database.

        Users are no longer supposed to be explicitly added as when
        using DummyAuthorizer.

        All FTP users are the same defined on the UNIX system so
        if you access on your system by using "john" as username
        and "12345" as password those same credentials can be used
        for accessing the FTP server as well.

        The user home directory will be the one defined /etc/passwd
        (e.g. /home/username).

        Every time a filesystem operation occurs (e.g. a file is
        created or deleted) the id of the process is temporarily
        changed to the effective user id and whether the operation
        will succeed depends on user and file permissions.
        This is why full read and write permissions are granted by 
        default in the constructor.

        Note: in order to use this class super user (root) privileges
        are required.
        """

        # --- public API

        def __init__(self, global_perm="elradfmw",
                           allowed_users=[],
                           rejected_users=[],
                           anonymous_user=None,
                           msg_login="Login successful.",
                           msg_quit="Goodbye."):
            """Parameters:

             - (string) global_perm:
               a series of letters referencing the users permissions;
               defaults to "elradfmw" which means full read and write
               access for everybody (except anonymous).

             - (string) anonymous_user:
               specify it if you intend to provide anonymous access.
               The value expected is a string representing the system
               user to use for managing anonymous sessions.
               Defaults to None (anonymous access disabled).

             - (string) msg_login:
               the string sent when client logs in.

             - (string) msg_quit:
               the string sent when client quits.
            """

            BaseUnixAuthorizer.__init__(self, anonymous_user)
            self.global_perm = global_perm
            self.rejected_users = rejected_users
            self.allowed_users = allowed_users
            self.msg_login = msg_login
            self.msg_quit = msg_quit

            self._dummy_authorizer = DummyAuthorizer()
            self._dummy_authorizer._check_permissions('', global_perm)

            if self.rejected_users and self.allowed_users:
                raise AuthorizerError("rejected_users and allowed_users options "
                                      "are mutually exclusive")

        def override_user(self, username, password=None, homedir=None, perm=None, 
                          msg_login=None, msg_quit=None):
            """Overrides the options specified in the constructor for
            a specific user.
            """
            if self.allowed_users and username not in self.allowed_users:
                raise AuthorizerError('%s is not an allowed user' % username)
            if self.rejected_users and username in self.rejected_users:
                raise AuthorizerError('%s is not an allowed user' % username)
            if not self.has_user(username):
                raise AuthorizerError('no such user %s' % username)
            if not password and not homedir and not perm and not msg_login \
            and not msg_quit:
                raise AuthorizerError("at least one keyword argument must be " \
                                      "specified")
            if username == "anonymous" and password:
                raise AuthorizerError("can't assign password to anonymous user")

            if username in self._dummy_authorizer.user_table:
                del self._dummy_authorizer.user_table[username]
            self._dummy_authorizer.add_user(username, password or "", 
                                                      homedir or "/", 
                                                      perm or "",
                                                      msg_login or "", 
                                                      msg_quit or "")
            if homedir is None:
                self._dummy_authorizer.user_table[username]['home'] = ""

        # --- private API

        def validate_authentication(self, username, password):
            if username == "anonymous":
                if self.anonymous_user is not None:
                    return True
                return False

            if self.allowed_users and username not in self.allowed_users:
                return False
            if self.rejected_users and username in self.rejected_users:
                return False

            if self._dummy_authorizer.has_user(username):
                if self._dummy_authorizer.user_table[username]['pwd']:
                    return self._dummy_authorizer.validate_authentication(
                                                            username, password)

            return BaseUnixAuthorizer.validate_authentication(self, username,
                                                              password)

        def get_home_dir(self, username):
            if self._dummy_authorizer.has_user(username):
                if self._dummy_authorizer.user_table[username]['home']:
                    return self._dummy_authorizer.get_home_dir(username)
            return BaseUnixAuthorizer.get_home_dir(self, username)

        def get_msg_login(self, username):
            if self._dummy_authorizer.has_user(username):
                if self._dummy_authorizer.user_table[username]['msg_login']:
                    return self._dummy_authorizer.get_msg_login(username)
            return self.msg_login

        def get_msg_quit(self, username):
            if self._dummy_authorizer.has_user(username):
                if self._dummy_authorizer.user_table[username]['msg_quit']:
                    return self._dummy_authorizer.get_msg_quit(username)
            return self.msg_quit

        def get_perms(self, username):
            if self._dummy_authorizer.has_user(username):
                if self._dummy_authorizer.user_table[username]['perm']:
                    return self._dummy_authorizer.get_perms(username)
            if username == 'anonymous':
                return "elr"
            return self.global_perm

        def has_perm(self, username, perm, path=None):
            if self._dummy_authorizer.has_user(username):
                if self._dummy_authorizer.user_table[username]['perm']:
                    return self._dummy_authorizer.has_perm(username, perm)
            if username == 'anonymous':
                return perm in "elr"
            return perm in self.global_perm

    __all__.extend(['BaseUnixAuthorizer', 'UnixAuthorizer'])

