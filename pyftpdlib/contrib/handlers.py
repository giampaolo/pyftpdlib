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
        _ssl_established = False
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
                elif err.args[0] == ssl.SSL_ERROR_SSL:
                    self.handle_failed_ssl_handshake()
                else:
                    raise
            else:
                self._ssl_accepting = False
                self._ssl_established = True

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

        def handle_failed_ssl_handshake(self):
            raise NotImplementedError("must be implemented in subclass")

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

        def handle_failed_ssl_handshake(self):
            # TLS/SSL handshake failure, probably client's fault which
            # used a SSL version different from server's.
            # RFC-4217, chapter 10.2 expects us to return 522 over the
            # command channel.
            proto = ssl.get_protocol_name(self.socket.ssl_version)
            self.cmd_channel.respond("522 %s handshake failed." %proto)
            self.close()

        def close(self):
            if isinstance(self.socket, ssl.SSLSocket):
                if self.socket._sslobj is not None:
                    return self._do_ssl_shutdown()
            DTPHandler.close(self)


    class TLS_FTPHandler(SSLConnection, FTPHandler):
        """A ftpserver.FTPHandler subclass supporting TLS/SSL.
        Implements AUTH, PBSZ and PROT commands (RFC-2228 and RFC-4217).

        Configurable attributes:

         - (string) certfile:
            the path of the file which contain a certificate to be used
            to identify the local side of the connection.
            This must always be set before starting the server.

         - (int) ssl_version:
            specifies which version of the SSL protocol to use when
            establishing SSL/TLS sessions. Clients can then only connect
            using the configured protocol (defaults to SSLv23 for best
            compatibility).

            Possible values:

            * ssl.PROTOCOL_SSLv2: allow only SSLv2
            * ssl.PROTOCOL_SSLv3: allow only SSLv3
            * ssl.PROTOCOL_SSLv23: allow both SSLv3 and TLSv1
            * ssl.PROTOCOL_TLSv1: allow only TLSv1

         - (bool) tls_control_required:
            When True requires SSL/TLS to be established on the control
            channel, before logging in.  This means the user will have
            to issue AUTH before USER/PASS (default False).

         - (bool) tls_data_required:
            When True requires SSL/TLS to be established on the data
            channel.  This means the user will have to issue PROT
            before PASV or PORT (default False).
        """

        # configurable attributes
        certfile = None
        ssl_version = ssl.PROTOCOL_SSLv23
        tls_control_required = False
        tls_data_required = False

        # overridden attributes
        proto_cmds = extended_proto_cmds
        dtp_handler = TLS_DTPHandler

        def __init__(self, conn, server):
            FTPHandler.__init__(self, conn, server)
            self._extra_feats = ['AUTH TLS', 'AUTH SSL', 'PBSZ', 'PROT']
            self._pbsz = False
            self._prot = False

        # --- overridden methods

        def flush_account(self):
            FTPHandler.flush_account(self)
            self._pbsz = False
            self._prot = False

        def process_command(self, cmd, *args, **kwargs):
            if cmd in ('USER', 'PASS'):
                if self.tls_control_required and not self._ssl_established:
                    self.respond("550 SSL/TLS required on the control channel.")
                    return
            elif cmd in ('PASV', 'EPSV', 'PORT', 'EPRT'):
                if self.tls_data_required and not self._prot:
                    self.respond("550 SSL/TLS required on the data channel.")
                    return
            FTPHandler.process_command(self, cmd, *args, **kwargs)

        # --- new methods

        def handle_failed_ssl_handshake(self):
            # TLS/SSL handshake failure, probably client's fault which
            # used a SSL version different from server's.
            # We can't rely on the control connection anymore so we just
            # disconnect the client without sending any response.
            ssl_version = ssl.get_protocol_name(self.socket.ssl_version)
            self.log("%s handshake failed." %ssl_version)
            self.close()

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
                self.respond("503 PBSZ not allowed on insecure control connection.")
            else:
                self.respond('200 PBSZ=0 successful.')
                self._pbsz = True

        def ftp_PROT(self, line):
            """Setup un/secure data channel."""
            arg = line.upper()
            if not isinstance(self.socket, ssl.SSLSocket):
                self.respond("503 PROT not allowed on insecure control connection.")
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
