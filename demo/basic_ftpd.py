#!/usr/bin/env python

from pyftpdlib import FTPServer
import os

if __name__ == "__main__":
    authorizer = FTPServer.dummy_authorizer()
    authorizer.add_user ('user', '12345', os.getcwd(), perm=('r', 'w'))
    authorizer.add_anonymous (os.getcwd())
    ftp_handler = FTPServer.ftp_handler    
    ftp_handler.authorizer = authorizer   
    address = ('', 21)    
    ftpd = FTPServer.ftp_server (address, ftp_handler)
    ftpd.serve_forever()
