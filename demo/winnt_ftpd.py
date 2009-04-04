#!/usr/bin/env python
# $Id$

"""A ftpd using local Windows NT account database to authenticate users
(users must already exist).

It also provides a mechanism to (temporarily) impersonate the system
users every time they are going to perform filesystem operations.
"""

import os
import win32security, win32net, pywintypes, win32con

from pyftpdlib import ftpserver


def get_profile_dir(username):
    """Return the user's profile directory."""
    import _winreg, win32api
    sid = win32security.ConvertSidToStringSid(
            win32security.LookupAccountName(None, username)[0])
    try:
        key = _winreg.OpenKey(_winreg.HKEY_LOCAL_MACHINE,
          r"SOFTWARE\Microsoft\Windows NT\CurrentVersion\ProfileList"+"\\"+sid)
    except WindowsError:
        raise ftpserver.AuthorizerError("No profile directory defined for %s "
                                        "user" %username)
    value = _winreg.QueryValueEx(key, "ProfileImagePath")[0]
    return win32api.ExpandEnvironmentStrings(value)


class WinNtAuthorizer(ftpserver.DummyAuthorizer):

    def add_user(self, username, homedir=None, **kwargs):
        """Add a "real" system user to the virtual users table.

        If no homedir argument is specified the user's profile
        directory will possibly be determined and used.

        The keyword arguments in kwargs are the same expected by the
        original add_user method: "perm", "msg_login" and "msg_quit".
        """
        # get the list of all available users on the system and check
        # if provided username exists
        users = [entry['name'] for entry in win32net.NetUserEnum(None, 0)[0]]
        if not username in users:
            raise ftpserver.AuthorizerError('No such user "%s".' %username)
        if not homedir:
            homedir = get_profile_dir(username)
        ftpserver.DummyAuthorizer.add_user(self, username, '', homedir,
                                           **kwargs)

    def add_anonymous(self, homedir=None, realuser="Guest",
                      password="", **kwargs):
        """Add an anonymous user to the virtual users table.

        If no homedir argument is specified the realuser's profile
        directory will possibly be determined and used.

        realuser and password arguments are the credentials to use for
        managing anonymous sessions.
        The same behaviour is followed in IIS where the Guest account
        is used to do so (note: it must be enabled first).
        """
        users = [entry['name'] for entry in win32net.NetUserEnum(None, 0)[0]]
        if not realuser in users:
            raise ftpserver.AuthorizerError('No such user "%s".' %realuser)
        if not homedir:
            homedir = get_profile_dir(realuser)
        # make sure provided credentials are valid, otherwise an exception
        # will be thrown; to do so we actually impersonate the user
        self.impersonate_user(realuser, password)
        self.terminate_impersonation()
        ftpserver.DummyAuthorizer.add_anonymous(self, homedir, **kwargs)
        self.anon_user = realuser
        self.anon_pwd = password

    def validate_authentication(self, username, password):
        if (username == "anonymous") and self.has_user('anonymous'):
            username = self.anon_user
            password = self.anon_pwd
        try:
            win32security.LogonUser(username, None, password,
                win32con.LOGON32_LOGON_INTERACTIVE,
                win32con.LOGON32_PROVIDER_DEFAULT)
            return True
        except pywintypes.error:
            return False

    def impersonate_user(self, username, password):
        if (username == "anonymous") and self.has_user('anonymous'):
            username = self.anon_user
            password = self.anon_pwd
        handler = win32security.LogonUser(username, None, password,
                      win32con.LOGON32_LOGON_INTERACTIVE,
                      win32con.LOGON32_PROVIDER_DEFAULT)
        win32security.ImpersonateLoggedOnUser(handler)
        handler.Close()

    def terminate_impersonation(self):
        win32security.RevertToSelf()


if __name__ == "__main__":
    authorizer = WinNtAuthorizer()
    # add a user (note: user must already exists)
    authorizer.add_user('user', perm='elradfmw')
    # add an anonymous user using Guest account to handle the anonymous
    # sessions (note: Guest must be enabled first)
    authorizer.add_anonymous(os.getcwd())
    ftp_handler = ftpserver.FTPHandler
    ftp_handler.authorizer = authorizer
    address = ('', 21)
    ftpd = ftpserver.FTPServer(address, ftp_handler)
    ftpd.serve_forever()
