#!/usr/bin/env python
# $Id$

"""An RFC-4217 asynchronous FTPS server supporting both SSL and TLS.

Requires PyOpenSSL module (http://pypi.python.org/pypi/pyOpenSSL).
"""

from pyftpdlib import ftpserver
from pyftpdlib.contrib.handlers import TLS_FTPHandler


def main():
    authorizer = ftpserver.DummyAuthorizer()
    authorizer.add_user('user', '12345', '.', perm='elradfmw')
    authorizer.add_anonymous('.')
    ftp_handler = TLS_FTPHandler
    ftp_handler.certfile = 'demo/keycert.pem'
    ftp_handler.authorizer = authorizer
    # requires SSL for both control and data channel
    #ftp_handler.tls_control_required = True
    #ftp_handler.tls_data_required = True
    ftpd = ftpserver.FTPServer(('', 8021), ftp_handler)
    ftpd.serve_forever()

if __name__ == '__main__':
    main()
