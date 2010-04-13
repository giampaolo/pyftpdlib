#!/usr/bin/env python
# handlers.py
#
#  ======================================================================
#  Copyright (C) 2007-2010 Giampaolo Rodola' <g.rodola@gmail.com>
#
#                         All Rights Reserved
#
# Permission is hereby granted, free of charge, to any person
# obtaining a copy of this software and associated documentation
# files (the "Software"), to deal in the Software without
# restriction, including without limitation the rights to use,
# copy, modify, merge, publish, distribute, sublicense, and/or sell
# copies of the Software, and to permit persons to whom the
# Software is furnished to do so, subject to the following
# conditions:
#
# The above copyright notice and this permission notice shall be
# included in all copies or substantial portions of the Software.
#
# THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND,
# EXPRESS OR IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES
# OF MERCHANTABILITY, FITNESS FOR A PARTICULAR PURPOSE AND
# NONINFRINGEMENT. IN NO EVENT SHALL THE AUTHORS OR COPYRIGHT
# HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER LIABILITY,
# WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING
# FROM, OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR
# OTHER DEALINGS IN THE SOFTWARE.
#
#  ======================================================================


"""This module is supposed to contain a series of classes which extend
base pyftpdlib.ftpserver's FTPHandler and DTPHandler classes.

As for now only one class is provided: TLS_FTPHandler.
It is supposed to provide basic support for FTPS (FTP over SSL/TLS) as
described in RFC-4217.

Requires ssl module (integrated with Python 2.6 and higher).
For Python versions prior to 2.6 ssl module must be installed separately,
see: http://pypi.python.org/pypi/ssl/

Development status: experimental.
"""


import os
import asyncore
import socket
from pyftpdlib.ftpserver import *

__all__ = []

try:
    import ssl
except ImportError:
    pass
else:
    extended_proto_cmds = proto_cmds.copy()
    new_proto_cmds = {
        # cmd : (perm, auth,  arg,  path,  help)
        'AUTH': (None, False, True, False, 'Syntax: AUTH <SP> TLS|SSL (set up secure control connection).'),
        'PBSZ': (None, True,  True, False, 'Syntax: PBSZ <SP> 0 (negotiate size of buffer for secure data transfer).'),
        'PROT': (None, True,  True, False, 'Syntax: PROT <SP> [C|P] (set up un/secure data channel).'),
        }

    from pyftpdlib.ftpserver import _CommandProperty
    for cmd, properties in new_proto_cmds.iteritems():
        extended_proto_cmds[cmd] = _CommandProperty(*properties)
    del cmd, properties, new_proto_cmds, _CommandProperty


    class SSLConnection(object, asyncore.dispatcher):
        """An asyncore.dispatcher subclass supporting TLS/SSL."""

        _ssl_accepting = False
        _ssl_closing = False

        def secure_connection(self, certfile, ssl_version):
            """Setup encrypted connection."""
            self.socket = ssl.wrap_socket(self.socket, suppress_ragged_eofs=False,
                                          certfile=certfile, server_side=True,
                                          do_handshake_on_connect=False,
                                          ssl_version=ssl_version)
            self._ssl_accepting = True

        def _do_ssl_handshake(self):
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

        def _do_ssl_shutdown(self):
            self._ssl_closing = True
            try:
                self.socket = self.socket.unwrap()
            except ssl.SSLError, err:
                if err.args[0] in (ssl.SSL_ERROR_WANT_READ,
                                   ssl.SSL_ERROR_WANT_WRITE):
                    return
                elif err.args[0] == ssl.SSL_ERROR_SSL:
                    pass
                else:
                    raise
            except socket.error, err:
                # Any "socket error" corresponds to a SSL_ERROR_SYSCALL
                # return from OpenSSL's SSL_shutdown(), corresponding to
                # a closed socket condition. See also:
                # http://www.mail-archive.com/openssl-users@openssl.org/msg60710.html
                pass
            self._ssl_closing = False
            super(SSLConnection, self).close()

        def handle_read_event(self):
            if self._ssl_accepting:
                self._do_ssl_handshake()
            elif self._ssl_closing:
                self._do_ssl_shutdown()
            else:
                super(SSLConnection, self).handle_read_event()

        def handle_write_event(self):
            if self._ssl_accepting:
                self._do_ssl_handshake()
            elif self._ssl_closing:
                self._do_ssl_shutdown()
            else:
                super(SSLConnection, self).handle_write_event()

        def send(self, data):
            try:
                return super(SSLConnection, self).send(data)
            except ssl.SSLError, err:
                if err.args[0] in (ssl.SSL_ERROR_EOF, ssl.SSL_ERROR_ZERO_RETURN):
                    return 0
                raise

        def recv(self, buffer_size):
            try:
                return super(SSLConnection, self).recv(buffer_size)
            except ssl.SSLError, err:
                if err.args[0] in (ssl.SSL_ERROR_EOF, ssl.SSL_ERROR_ZERO_RETURN):
                    self.handle_close()
                    return ''
                if err.args[0] in (ssl.SSL_ERROR_WANT_READ,
                                   ssl.SSL_ERROR_WANT_WRITE):
                    return ''
                raise


    class TLS_DTPHandler(SSLConnection, DTPHandler):
        """A ftpserver.DTPHandler subclass supporting TLS/SSL."""

        def __init__(self, sock_obj, cmd_channel):
            DTPHandler.__init__(self, sock_obj, cmd_channel)
            if self.cmd_channel._prot:
                self.secure_connection(self.cmd_channel.certfile,
                                       self.cmd_channel.ssl_version)

##        def handle_error(self):
##            try:
##                raise
##            except ssl.SSLError, err:
##                if self._ssl_accepting and err.args[0] == ssl.SSL_ERROR_SSL:
##                    # TLS/SSL handshake failure, probably client's fault.
##                    # RFC-4217, chapter 10.2 expects us to return 522.
##                    proto = ssl.get_protocol_name(self.socket.ssl_version)
##                    self.cmd_channel.respond("522 %s handshake failed." %proto)
##                else:
##                    # We don't want to provide any confidential message
##                    self.cmd_channel.respond("426 Internal SSL error. Transfer aborted")
##                    logerror(str(err))
##                self.close()
##            except:
##                DTPHandler.handle_error(self)

        def close(self):
            if isinstance(self.socket, ssl.SSLSocket):
                if self.socket._sslobj is not None:
                    return self._do_ssl_shutdown()
            DTPHandler.close(self)


    class TLS_FTPHandler(SSLConnection, FTPHandler):
        """A ftpserver.FTPHandler subclass supporting TLS/SSL.

        Implements AUTH, PBSZ and PROT commands (RFC-2228 and RFC-4217).
        """

        # configurable attributes
        certfile = 'keycert.pem'
        ssl_version = ssl.PROTOCOL_SSLv23

        # overridden attributes
        proto_cmds = extended_proto_cmds
        dtp_handler = TLS_DTPHandler

        def __init__(self, conn, server):
            FTPHandler.__init__(self, conn, server)
            self._extra_feats = ['AUTH TLS', 'AUTH SSL', 'PBSZ', 'PROT']
            self._pbsz = False
            self._prot = False

        def ftp_AUTH(self, line):
            """Set up secure control channel."""
            arg = line.upper()
            if isinstance(self.socket, ssl.SSLSocket):
                self.respond("503 Already using TLS.")
            elif arg in ('TLS', 'TLS-C', 'SSL', 'TLS-P'):
                # From RFC-4217: "As the SSL/TLS protocols self-negotiate
                # their levels, there is no need to distinguish between SSL
                # and TLS in the application layer".
                self.respond('234 AUTH %s successful.' %arg)
                self.secure_connection(self.certfile, self.ssl_version)
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

##        def handle_error(self):
##            try:
##                raise
##            except ssl.SSLError, err:
##                # TLS/SSL handshake failure, probably client's fault.
##                if self._ssl_accepting and err.args[0] == ssl.SSL_ERROR_SSL:
##                    proto = ssl.get_protocol_name(self.socket.ssl_version)
##                    log("%s handshake failed. Disconnecting. %s" %(proto, str(err)))
##                else:
##                    logerror(str(err))
##                # We can't rely on the control channel anymore so we just
##                # disconnect the client without sending any response.
##                self.close()
##            except:
##                FTPHandler.handle_error(self)

    __all__.extend(['SSLConnection', 'TLS_DTPHandler', 'TLS_DTPHandler'])


if __name__ == '__main__':
    authorizer = DummyAuthorizer()
    authorizer.add_user('user', '12345', os.getcwd(), perm='elradfmw')
    authorizer.add_anonymous(os.getcwd())
    ftp_handler = TLS_FTPHandler
    ftp_handler.authorizer = authorizer
    address = ('', 21)
    ftpd = FTPServer(address, ftp_handler)
    ftpd.serve_forever()
