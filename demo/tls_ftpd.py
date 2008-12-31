#!/usr/bin/env python
# tls_ftpd.py

"""RFC-2228 asynchronous FTPS server."""

import ssl
import os
import asyncore

from pyftpdlib.ftpserver import *


CERTFILE = 'keycert.pem'

new_proto_cmds = {
    # cmd : (perm, auth,  arg,   path,  help)
    'AUTH': (None, False, True,  False, 'Syntax: AUTH <SP> TLS|SSL (set up secure control connection).'),
    'PBSZ': (None, False, True,  False, 'Syntax: PBSZ <SP> 0 (negotiate size of buffer for secure data transfer).'),
    'PROT': (None, False, True,  False, 'Syntax: PROT <SP> [C|P] (set up un/secure data channel).'),
    }

from pyftpdlib.ftpserver import _CommandProperty
for cmd, properties in new_proto_cmds.iteritems():
    proto_cmds[cmd] = _CommandProperty(*properties)
del cmd, properties, new_proto_cmds, _CommandProperty


class SSLConnection(object, asyncore.dispatcher):
    _ssl_accepting = False

    def secure_connection(self):
        self.socket = ssl.wrap_socket(self.socket, suppress_ragged_eofs=False,
                                      certfile=CERTFILE, server_side=True,
                                      do_handshake_on_connect=False)
        self._ssl_accepting = True
        self.do_ssl_handshake()

    def do_ssl_handshake(self):
        try:
            self.socket.do_handshake()
        except ssl.SSLError, err:
            if err.args[0] in (ssl.SSL_ERROR_WANT_READ, ssl.SSL_ERROR_WANT_WRITE):
                return
            elif err.args[0] == ssl.SSL_ERROR_EOF:
                return self.handle_close()
            raise
        else:
            self._ssl_accepting = False

    def handle_read_event(self):
        if self._ssl_accepting:
            self.do_ssl_handshake()
        else:
            super(SSLConnection, self).handle_read_event()

    def handle_write_event(self):
        if self._ssl_accepting:
            self.do_ssl_handshake()
        else:
            super(SSLConnection, self).handle_write_event()

    def send(self, data):
        try:
            return super(SSLConnection, self).send(data)
        except ssl.SSLError, err:
            if err.args[0] == ssl.SSL_ERROR_EOF:
                return 0
            raise

    def recv(self, buffer_size):
        try:
            return super(SSLConnection, self).recv(buffer_size)
        except ssl.SSLError, err:
            if err.args[0] == ssl.SSL_ERROR_EOF:
                self.handle_close()
                return ''
            raise


class TLS_DTPHandler(SSLConnection, DTPHandler):

    def __init__(self, sock_obj, cmd_channel):
        DTPHandler.__init__(self, sock_obj, cmd_channel)
        if self.cmd_channel._prot_p:
            self.secure_connection()


class TLS_FTPHandler(SSLConnection, FTPHandler):

    dtp_handler = TLS_DTPHandler

    def __init__(self, conn, server):
        FTPHandler.__init__(self, conn, server)
        self._prot_p = False

    def ftp_AUTH(self, line):
        """Set up secure control channel."""
        arg = line.upper()
        if arg not in ('SSL', 'TLS'):
            self.respond("502 Unrecognized encryption type (use TLS/SSL).")
        elif isinstance(self.socket, ssl.SSLSocket):
            self.respond("503 Already using TLS.")
        else:
            # XXX - depending on the provided argument (TLS/SSL)
            # should we specify wrap_socket()'s ssl_version
            # parameter?
            self.respond('234 AUTH TLS/SSL successful.')
            self.secure_connection()

    def ftp_PBSZ(self, line):
        self.respond('200 PBSZ=0 successful.')

    def ftp_PROT(self, line):
        self.respond('200 Protection set to Private')
        self._prot_p = True


if __name__ == '__main__':
    authorizer = DummyAuthorizer()
    authorizer.add_user('user', '12345', os.getcwd(), perm='elradfmw')
    authorizer.add_anonymous(os.getcwd())
    ftp_handler = TLS_FTPHandler
    ftp_handler.authorizer = authorizer
    address = ('', 21)
    ftpd = FTPServer(address, ftp_handler)
    ftpd.serve_forever()
