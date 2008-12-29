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

    def do_ssl_handshake(self):
        try:
            self.socket.do_handshake()
            self.ssl_accepting = False
        except ssl.SSLError, err:
            if err.args[0] in (ssl.SSL_ERROR_WANT_READ, ssl.SSL_ERROR_WANT_WRITE):
                return
            raise

    def handle_read_event(self):
        if self.ssl_accepting:
            self.do_ssl_handshake()
        else:
            asyncore.dispatcher.handle_read_event(self)

    def handle_write_event(self):
        if self.ssl_accepting:
            self.do_ssl_handshake()
        else:
            asyncore.dispatcher.handle_write_event(self)

    def send(self, data):
        try:
            return asyncore.dispatcher.send(self, data)
        except ssl.SSLError, err:
            if err.args[0] == ssl.SSL_ERROR_EOF:
                return 0
            raise

    def recv(self, buffer_size):
        try:
            return asyncore.dispatcher.recv(self, buffer_size)
        except ssl.SSLError, err:
            if err.args[0] == ssl.SSL_ERROR_EOF:
                self.handle_close()
                return ''
            raise


class TLS_DTPHandler(SSLConnection, DTPHandler):

    do_ssl_handshake = SSLConnection.do_ssl_handshake
    handle_read_event = SSLConnection.handle_read_event
    handle_write_event = SSLConnection.handle_write_event
    send = SSLConnection.send
    recv = SSLConnection.recv

    def __init__(self, sock_obj, cmd_channel):
        DTPHandler.__init__(self, sock_obj, cmd_channel)
        self.ssl_accepting = False
        if self.cmd_channel.secure_data_channel:
            self.socket = ssl.wrap_socket(self.socket, do_handshake_on_connect=0,
                                          certfile=CERTFILE, server_side=True,
                                          suppress_ragged_eofs=False)
            self.ssl_accepting = True


class TLS_FTPHandler(SSLConnection, FTPHandler):

    dtp_handler = TLS_DTPHandler

    do_ssl_handshake = SSLConnection.do_ssl_handshake
    handle_read_event = SSLConnection.handle_read_event
    handle_write_event = SSLConnection.handle_write_event
    send = SSLConnection.send
    recv = SSLConnection.recv

    def __init__(self, conn, server):
        FTPHandler.__init__(self, conn, server)
        self.ssl_accepting = False
        self.secure_data_channel = False


    def ftp_AUTH(self, line):
        self.respond('234 AUTH TLS successful')
        self.socket = ssl.wrap_socket(self.socket, suppress_ragged_eofs=False,
                                      certfile=CERTFILE, server_side=True,
                                      do_handshake_on_connect=False)
        self.ssl_accepting = True

    def ftp_PBSZ(self, line):
        self.respond('200 PBSZ=0 successful.')

    def ftp_PROT(self, line):
        self.respond('200 Protection set to Private')
        self.secure_data_channel = True


if __name__ == '__main__':
    authorizer = DummyAuthorizer()
    authorizer.add_user('user', '12345', os.getcwd(), perm='elradfmw')
    authorizer.add_anonymous(os.getcwd())
    ftp_handler = TLS_FTPHandler
    ftp_handler.authorizer = authorizer
    address = ('', 21)
    ftpd = FTPServer(address, ftp_handler)
    ftpd.serve_forever()
