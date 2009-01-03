#!/usr/bin/env python
# tls_ftpd.py

"""RFC-2228 asynchronous FTPS server."""

import ssl
import os
import asyncore

from pyftpdlib.ftpserver import *


CERTFILE = 'keycert.pem'

new_proto_cmds = {
    # cmd : (perm, auth,  arg,  path,  help)
    'AUTH': (None, False, True, False, 'Syntax: AUTH <SP> TLS|SSL (set up secure control connection).'),
    'PBSZ': (None, True,  True, False, 'Syntax: PBSZ <SP> 0 (negotiate size of buffer for secure data transfer).'),
    'PROT': (None, True,  True, False, 'Syntax: PROT <SP> [C|P] (set up un/secure data channel).'),
    }

from pyftpdlib.ftpserver import _CommandProperty
for cmd, properties in new_proto_cmds.iteritems():
    proto_cmds[cmd] = _CommandProperty(*properties)
del cmd, properties, new_proto_cmds, _CommandProperty


class SSLConnection(object, asyncore.dispatcher):
    _ssl_accepting = False

    def secure_connection(self, ssl_version):
        self.socket = ssl.wrap_socket(self.socket, suppress_ragged_eofs=False,
                                      certfile=CERTFILE, server_side=True,
                                      do_handshake_on_connect=False,
                                      ssl_version=ssl_version)
        self._ssl_accepting = True

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

    def close(self):
        try:
            if isinstance(self.socket, ssl.SSLSocket):
                self.socket.unwrap()
        finally:
            super(SSLConnection, self).close()


class TLS_DTPHandler(SSLConnection, DTPHandler):

    def __init__(self, sock_obj, cmd_channel):
        DTPHandler.__init__(self, sock_obj, cmd_channel)
        if self.cmd_channel._prot:
            self.secure_connection(self.cmd_channel.socket.ssl_version)

    def handle_error(self):
        try:
            raise
        except ssl.SSLError, err:
            if self._ssl_accepting and err.args[0] == ssl.SSL_ERROR_SSL:
                # TLS/SSL handshake failure, probably client's fault.
                # RFC-4217, chapter 10.2 expects us to return 522.
                proto = ssl.get_protocol_name(self.socket.ssl_version)
                self.cmd_channel.respond("522 %s handshake failed." %proto)
            else:
                # We don't want to provide any confidential message
                self.cmd_channel.respond("426 Internal SSL error. Transfer aborted")
                logerror(str(err))
            self.close()
        except:
            DTPHandler.handle_error(self)


class TLS_FTPHandler(SSLConnection, FTPHandler):

    dtp_handler = TLS_DTPHandler

    def __init__(self, conn, server):
        FTPHandler.__init__(self, conn, server)
        self._pbsz = False
        self._prot = False

    def ftp_AUTH(self, line):
        """Set up secure control channel."""
        arg = line.upper()
        if isinstance(self.socket, ssl.SSLSocket):
            self.respond("503 Already using TLS.")
        elif arg in ('TLS', 'TLS-C'):
            self.respond('234 AUTH TLS successful.')
            self.secure_connection(ssl.PROTOCOL_TLSv1)
        elif arg in ('SSL', 'TLS-P'):
            self.respond('234 AUTH SSL successful.')
            self.secure_connection(ssl.PROTOCOL_SSLv23)
        else:
            self.respond("502 Unrecognized encryption type (use TLS or SSL).")

    def ftp_PBSZ(self, line):
        """Negotiate size of buffer for secure data transfer.
        For TLS/SSL the only valid value for the parameter is '0'.
        Any other value is accepted but ignored.
        """
        if not isinstance(self.socket, ssl.SSLSocket):
            self.respond("503 PROT not allowed on insecure control connection")
        else:
            self.respond('200 PBSZ=0 successful.')
            self._pbsz = True

    def ftp_PROT(self, line):
        """Setup un/secure data channel."""
        arg = line.upper()
        if not isinstance(self.socket, ssl.SSLSocket):
            self.respond("503 PROT not allowed on insecure control connection")
        elif not self._pbsz:
            self.respond("503 You must issue the PBSZ command prior to PROT.")
        elif arg == 'C':
            self.respond('200 Protection set to Clear')
            self._prot = False
        elif arg == 'P':
            self.respond('200 Protection set to Private')
            self._prot = True
        elif arg in ('S', 'E'):
            self.respond('521 PROT %s unsupported (use C or P).' %arg)
        else:
            self.respond("502 Unrecognized PROT type (use C or P).")

    def handle_error(self):
        try:
            raise
        except ssl.SSLError, err:
            # TLS/SSL handshake failure, probably client's fault.
            if self._ssl_accepting and err.args[0] == ssl.SSL_ERROR_SSL:
                proto = ssl.get_protocol_name(self.socket.ssl_version)
                log("%s handshake failed. Disconnecting. %s" %(proto, str(err)))
            else:
                logerror(str(err))
            # We can't rely on the control channel anymore so we just
            # disconnect the client without sending any response.
            self.close()
        except:
            FTPHandler.handle_error(self)


if __name__ == '__main__':
    authorizer = DummyAuthorizer()
    authorizer.add_user('user', '12345', os.getcwd(), perm='elradfmw')
    authorizer.add_anonymous(os.getcwd())
    ftp_handler = TLS_FTPHandler
    ftp_handler.authorizer = authorizer
    address = ('', 21)
    ftpd = FTPServer(address, ftp_handler)
    ftpd.serve_forever()
