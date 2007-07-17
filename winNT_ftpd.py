# winFTPserver.py
# Basic authorizer for Windows NT accounts (users must be created previously)

from pyftpdlib import FTPServer
import win32security, win32net, pywintypes
import os

class winNT_authorizer(FTPServer.dummy_authorizer):

    def __init__(self):
        FTPServer.dummy_authorizer.__init__(self)

    def add_user(self, username, home, perm=('r')):
        if username != 'anonymous':
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

    def add_anonymous(self, homedir, perm=('r')):
        if 'w' in perm:
            raise error, "Anonymous aims to be a read-only user."
        self.add_user('anonymous', homedir, perm)


if __name__ == "__main__":
    authorizer = winNT_authorizer()
    authorizer.add_user ('user', os.getcwd(),perm=('r', 'w'))
    authorizer.add_anonymous (os.getcwd())
    ftp_handler = FTPServer.ftp_handler
    ftp_handler.authorizer = authorizer
    address = ('', 21)
    ftpd = FTPServer.ftp_server(address, ftp_handler)
    ftpd.serve_forever()


