"""An RFC-4217 asynchronous FTPS server supporting both SSL and TLS.

Requires ssl module (integrated with Python 2.6 and higher).
For Python versions prior to 2.6 ssl module must be installed separately,
see: http://pypi.python.org/pypi/ssl/
"""

from pyftpdlib import ftpserver
from pyftpdlib.contrib.handlers import TLS_FTPHandler

if __name__ == '__main__':
    authorizer = ftpserver.DummyAuthorizer()
    authorizer.add_user('user', '12345', '.', perm='elradfmw')
    authorizer.add_anonymous('.')
    ftp_handler = TLS_FTPHandler
    # speicify the certificate file to use
    ftp_handler.certfile = 'keycert.pem'
    ftp_handler.authorizer = authorizer
    address = ('0.0.0.0', 21)
    ftpd = ftpserver.FTPServer(address, ftp_handler)
    ftpd.serve_forever()
