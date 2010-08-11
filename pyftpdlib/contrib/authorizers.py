#!/usr/bin/env python
# $Id$

"""An "authorizer" is a class handling authentications and permissions
of the FTP server. It is used by pyftpdlib.ftpserver.FTPHandler
class for:

- verifying user password
- getting user home directory
- checking user permissions when a filesystem read/write event occurs
- changing user when accessing the filesystem

This module contains two classes which implements such functionalities 
in a system-specific way for both Unix and Windows.
Both implementations share the same API and functionalities.
"""

__all__ = []


import os

from pyftpdlib.ftpserver import DummyAuthorizer, AuthorizerError


def replace_anonymous(callable):
    """Decorator to replace anonymous user string passed to authorizer
    methods as first arugument with the actual user used to handle
    anonymous sessions.
    """
    def wrapper(self, username, *args, **kwargs):
        if username == 'anonymous':
            username = self.anonymous_user or username
        return callable(self, username, *args, **kwargs)
    return wrapper


class _CommonMethods:
    """Methods common to both Unix and Windows authorizers."""

    def override_user(self, username, password=None, homedir=None, perm=None, 
                      msg_login=None, msg_quit=None):
        if not password and not homedir and not perm and not msg_login \
        and not msg_quit:
            raise ValueError("at least one keyword argument must be specified")
        if self.allowed_users and username not in self.allowed_users:
            raise AuthorizerError('%s is not an allowed user' % username)
        if self.rejected_users and username in self.rejected_users:
            raise AuthorizerError('%s is not an allowed user' % username)
        if username == "anonymous" and password:
            raise AuthorizerError("can't assign password to anonymous user")
        if not self.has_user(username):
            raise AuthorizerError('no such user %s' % username)

        if username in self._dummy_authorizer.user_table:
            del self._dummy_authorizer.user_table[username]
        self._dummy_authorizer.add_user(username, password or "", 
                                                  homedir or "/", 
                                                  perm or "",
                                                  msg_login or "", 
                                                  msg_quit or "")
        if homedir is None:
            self._dummy_authorizer.user_table[username]['home'] = ""

    def get_msg_login(self, username):
        return self._get_key(username, 'msg_login') or self.msg_login

    def get_msg_quit(self, username):
        return self._get_key(username, 'msg_quit') or self.msg_quit

    def get_perms(self, username):
        overridden_perms = self._get_key(username, 'perm')
        if overridden_perms is not None:
            return overridden_perms
        if username == 'anonymous':
            return 'elr'
        return self.global_perm

    def has_perm(self, username, perm, path=None):
        return perm in self.get_perms(username)

    def _get_key(self, username, key):
        if self._dummy_authorizer.has_user(username):
            return self._dummy_authorizer.user_table[username][key]


# Note: requires python >= 2.5
try:
    import pwd, spwd, crypt
except ImportError:
    pass
else:
    # the uid/gid the server runs under
    PROCESS_UID = os.getuid()
    PROCESS_GID = os.getgid()

    class UnixAuthorizer(_CommonMethods):
        """An authorizer compatible with Unix user account and password
        database.

        Users are no longer supposed to be explicitly added as when
        using DummyAuthorizer.

        All FTP users are the same defined on the UNIX system so if 
        you access on your system by using "john" as username and 
        "12345" as password those same credentials can be used for 
        accessing the FTP server as well.

        The user home directory will be the one defined /etc/passwd
        (e.g. /home/username).

        Every time a filesystem operation occurs (e.g. a file is
        created or deleted) the id of the process is temporarily
        changed to the effective user id and whether the operation will
        succeed depends on user and file permissions.
        This is why full read and write permissions are granted by 
        default in the constructor.

        Note: in order to use this class super user (root) privileges
        are required.

        Parameters:

         - (string) global_perm:
            a series of letters referencing the users permissions;
            defaults to "elradfmw" which means full read and write
            access for everybody (except anonymous).

         - (list) allowed_users:
            a list of users which are accepted for authenticating 
            against the FTP server

         - (list) rejected_users:
            a list of users which are not accepted for authenticating 
            against the FTP server

         - (string) anonymous_user:
            specify it if you intend to provide anonymous access.
            The value expected is a string representing the system user
            to use for managing anonymous sessions.
            Defaults to None (anonymous access disabled).

         - (string) msg_login:
            the string sent when client logs in.

         - (string) msg_quit:
            the string sent when client quits.
        """

        # --- public API

        def __init__(self, global_perm="elradfmw",
                           allowed_users=[],
                           rejected_users=[],
                           anonymous_user=None,
                           msg_login="Login successful.",
                           msg_quit="Goodbye."):
            if os.geteuid() != 0 or not spwd.getspall():
                raise AuthorizerError("super user privileges are required")

            self.global_perm = global_perm
            self.allowed_users = allowed_users
            self.rejected_users = rejected_users
            self.anonymous_user = anonymous_user
            self.msg_login = msg_login
            self.msg_quit = msg_quit
            self._dummy_authorizer = DummyAuthorizer()
            self._dummy_authorizer._check_permissions('', global_perm)

            if self.rejected_users and self.allowed_users:
                raise AuthorizerError("rejected_users and allowed_users options "
                                      "are mutually exclusive")

            if anonymous_user is not None:
                if not self.has_user(anonymous_user):
                    raise AuthorizerError('no such user %s' % anonymous_user)
                home = self.get_home_dir(anonymous_user)
                if not os.path.isdir(home):
                    raise AuthorizerError('no valid home set for user %s'
                                          % anonymous_user)

        def override_user(self, username, password=None, homedir=None, perm=None, 
                          msg_login=None, msg_quit=None):
            """Overrides the options specified in the class constructor 
            for a specific user.
            """
            _CommonMethods.override_user(self, username, password, homedir, 
                                         perm, msg_login, msg_quit)

        # --- overridden / private API

        def validate_authentication(self, username, password):
            """Authenticates against shadow password db; return
            True on success.
            """
            if username == "anonymous":
                return self.anonymous_user is not None
            if self.allowed_users and username not in self.allowed_users:
                return False
            if self.rejected_users and username in self.rejected_users:
                return False
            overridden_password = self._get_key(username, 'pwd')
            if overridden_password is not None:
                return overridden_password == password
            else:
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
                pwdstruct = pwd.getpwnam(username)
            except KeyError:
                raise AuthorizerError('no such user %s' % username)
            else:
                os.setegid(pwdstruct.pw_gid)
                os.seteuid(pwdstruct.pw_uid)
        
        def terminate_impersonation(self):
            """Revert process effective user/group IDs."""
            os.setegid(PROCESS_GID)
            os.seteuid(PROCESS_UID)

        @replace_anonymous
        def has_user(self, username):
            """Return True if user exists on the Unix system."""
            return username in [entry.pw_name for entry in pwd.getpwall()]

        @replace_anonymous
        def get_home_dir(self, username):
            """Return user home directory."""
            overridden_home = self._get_key(username, 'home')
            if overridden_home is not None:
                return overridden_home
            try:
                return pwd.getpwnam(username).pw_dir
            except KeyError:
                raise AuthorizerError('no such user %s' % username)

    __all__.append('UnixAuthorizer')


# Note: requires pywin32 extension
try:
    import _winreg
    import win32security, win32net, pywintypes, win32con, win32api
except ImportError:
    pass
else:
    class WindowsAuthorizer(_CommonMethods):
        """An authorizer compatible with Windows user account and 
        password database.

        Users are no longer supposed to be explicitly added as when
        using DummyAuthorizer.

        All FTP users are the same defined on the Windows system so 
        if  you access on your system by using "john" as username and 
        "12345" as password those same credentials can be used for 
        accessing the FTP server as well.

        The user profile directory (which is tipically
        C:\Documents and settings\<username>) will be used as user home.

        Every time a filesystem operation occurs (e.g. a file is
        created or deleted) the security context is temporarily changed
        to reflect the logged in user and whether the operation will
        succeed depends on user and file permissions.
        This is why full read and write permissions are granted by 
        default in the constructor.

        Parameters:

         - (string) global_perm:
            a series of letters referencing the users permissions;
            defaults to "elradfmw" which means full read and write
            access for everybody (except anonymous).

         - (list) allowed_users:
            a list of users which are accepted for authenticating 
            against the FTP server

         - (list) rejected_users:
            a list of users which are not accepted for authenticating 
            against the FTP server

         - (string) anonymous_user:
            specify it if you intend to provide anonymous access.
            The value expected is a string representing the system user
            to use for managing anonymous sessions.
            As for IIS, it is recommended to use Guest account. 
            The common practice is to first enable the Guest user, which 
            is disabled by default and then assign an empty password.
            Defaults to None (anonymous access disabled).

         - (string) anonymous_password:
            the password of the user who has been chosen to manage the
            anonymous sessions.  Defaults to None (empty password).

         - (string) msg_login:
            the string sent when client logs in.

         - (string) msg_quit:
            the string sent when client quits.
        """

        # --- public API

        def __init__(self, global_perm="elradfmw",
                           allowed_users=[],
                           rejected_users=[],
                           anonymous_user=None,
                           anonymous_password=None,
                           msg_login="Login successful.",
                           msg_quit="Goodbye."):
            self.global_perm = global_perm
            self.allowed_users = allowed_users
            self.rejected_users = rejected_users
            self.anonymous_user = anonymous_user
            self.anonymous_password = anonymous_password
            self.msg_login = msg_login
            self.msg_quit = msg_quit
            self._dummy_authorizer = DummyAuthorizer()
            self._dummy_authorizer._check_permissions('', global_perm)

            if self.rejected_users and self.allowed_users:
                raise AuthorizerError("rejected_users and allowed_users options "
                                      "are mutually exclusive")

            if anonymous_user is not None:
                if not self.has_user(anonymous_user):
                    raise AuthorizerError('no such user %s' % anonymous_user)
                if not self.validate_authentication(anonymous_user,
                                                    anonymous_password):
                    raise AuthorizerError('invalid credentials provided for '
                           'anonymous user (username:%s, password:%s)' 
                            % (anonymous_user, anonymous_password or '<empty>'))
                    # actually try to impersonate the user
                    self.impersonate_user(anonymous_user, anonymous_password)
                    self.terminate_impersonation()
                home = self.get_home_dir(anonymous_user)
                if not os.path.isdir(home):
                    raise AuthorizerError('no valid home set for user %s'
                                          % anonymous_user)

        def override_user(self, username, password=None, homedir=None, perm=None, 
                          msg_login=None, msg_quit=None):
            """Overrides the options specified in the class constructor 
            for a specific user.
            """
            _CommonMethods.override_user(self, username, password, homedir, 
                                         perm, msg_login, msg_quit)

        # --- overridden / private API

        def validate_authentication(self, username, password):
            """Authenticates against Windows user database; return
            True on success.
            """
            if username == "anonymous":
                return self.anonymous_user is not None
            if self.allowed_users and username not in self.allowed_users:
                return False
            if self.rejected_users and username in self.rejected_users:
                return False
            overridden_password = self._get_key(username, 'pwd')
            if overridden_password is not None:
                return overridden_password == password
            else:
                try:
                    win32security.LogonUser(username, None, password,
                                            win32con.LOGON32_LOGON_INTERACTIVE,
                                            win32con.LOGON32_PROVIDER_DEFAULT)                
                except pywintypes.error:
                    return False
                else:
                    return True

        def impersonate_user(self, username, password):
            """Impersonate the security context of another user."""
            if username == "anonymous":
                username = self.anonymous_user or ""
                password = self.anonymous_password or ""
            handler = win32security.LogonUser(username, None, password,
                          win32con.LOGON32_LOGON_INTERACTIVE,
                          win32con.LOGON32_PROVIDER_DEFAULT)
            win32security.ImpersonateLoggedOnUser(handler)
            handler.Close()

        def terminate_impersonation(self):
            """Terminate the imporsonation of another user."""
            win32security.RevertToSelf()

        @replace_anonymous
        def has_user(self, username):
            """Return True if user exists on the Windows system."""
            users = [entry['name'] for entry in win32net.NetUserEnum(None, 0)[0]]
            return username in users

        @replace_anonymous
        def get_home_dir(self, username):
            """Return the user's profile directory, the closest thing
            to a user home directory we have on Windows."""
            overridden_home = self._get_key(username, 'home')
            if overridden_home is not None:
                return overridden_home
            try:
                sid = win32security.ConvertSidToStringSid(
                        win32security.LookupAccountName(None, username)[0])
            except pywintypes.error, err:
                raise AuthorizerError(err)
            path = r"SOFTWARE\Microsoft\Windows NT\CurrentVersion\ProfileList" + \
                   "\\" + sid
            try:
                key = _winreg.OpenKey(_winreg.HKEY_LOCAL_MACHINE, path)
            except WindowsError:
                raise AuthorizerError("No profile directory defined for user %s"
                                      % username)
            value = _winreg.QueryValueEx(key, "ProfileImagePath")[0]
            return win32api.ExpandEnvironmentStrings(value)

    __all__.append('WindowsAuthorizer')



