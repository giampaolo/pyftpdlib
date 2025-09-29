# Copyright (C) 2007 Giampaolo Rodola' <g.rodola@gmail.com>.
# Use of this source code is governed by MIT license that can be
# found in the LICENSE file.

import contextlib
import errno
import os
import traceback

from .handlers2.ftp.control import FTPHandler
from .handlers2.ftp.data import DTPHandler

try:
    import grp
    import pwd
except ImportError:
    pwd = grp = None

try:
    from OpenSSL import SSL  # requires "pip install pyopenssl"
except ImportError:
    SSL = None

from .exceptions import RetryError
from .ioloop import _ERRNOS_DISCONNECTED
from .log import debug
from .log import logger

# --- FTP


# ===================================================================
# --- FTP over SSL
# ===================================================================


if SSL is not None:

    class SSLConnection:
        """An AsyncChat subclass supporting TLS/SSL."""

        _ssl_accepting = False
        _ssl_established = False
        _ssl_closing = False
        _ssl_requested = False

        def __init__(self, *args, **kwargs):
            super().__init__(*args, **kwargs)
            self._error = False
            self._ssl_want_read = False
            self._ssl_want_write = False

        def readable(self):
            return (
                self._ssl_accepting
                or self._ssl_want_read
                or super().readable()
            )

        def writable(self):
            return self._ssl_want_write or super().writable()

        def secure_connection(self, ssl_context):
            """Secure the connection switching from plain-text to
            SSL/TLS.
            """
            debug("securing SSL connection", self)
            self._ssl_requested = True
            try:
                self.socket = SSL.Connection(ssl_context, self.socket)
            except OSError as err:
                # may happen in case the client connects/disconnects
                # very quickly
                debug(
                    "call: secure_connection(); can't secure SSL connection "
                    f"{err!r}; closing",
                    self,
                )
                self.close()
            except ValueError:
                # may happen in case the client connects/disconnects
                # very quickly
                if self.socket.fileno() == -1:
                    debug(
                        "ValueError and fd == -1 on secure_connection()", self
                    )
                    return
                raise
            else:
                self.socket.set_accept_state()
                self._ssl_accepting = True

        @contextlib.contextmanager
        def _handle_ssl_want_rw(self):
            prev_row_pending = self._ssl_want_read or self._ssl_want_write
            try:
                yield
            except SSL.WantReadError:
                # we should never get here; it's just for extra safety
                self._ssl_want_read = True
            except SSL.WantWriteError:
                # we should never get here; it's just for extra safety
                self._ssl_want_write = True

            if self._ssl_want_read:
                self.modify_ioloop_events(
                    self._wanted_io_events | self.ioloop.READ, logdebug=True
                )
            elif self._ssl_want_write:
                self.modify_ioloop_events(
                    self._wanted_io_events | self.ioloop.WRITE, logdebug=True
                )
            elif prev_row_pending:
                self.modify_ioloop_events(self._wanted_io_events)

        def _do_ssl_handshake(self):
            self._ssl_accepting = True
            self._ssl_want_read = False
            self._ssl_want_write = False
            try:
                self.socket.do_handshake()
            except SSL.WantReadError:
                self._ssl_want_read = True
                debug("call: _do_ssl_handshake, err: ssl-want-read", inst=self)
            except SSL.WantWriteError:
                self._ssl_want_write = True
                debug(
                    "call: _do_ssl_handshake, err: ssl-want-write", inst=self
                )
            except SSL.SysCallError as err:
                debug(f"call: _do_ssl_handshake, err: {err!r}", inst=self)
                retval, desc = err.args
                if (retval == -1 and desc == "Unexpected EOF") or retval > 0:
                    # Happens when the other side closes the socket before
                    # completing the SSL handshake, e.g.:
                    # client.sock.sendall(b"PORT ...\r\n")
                    # client.getresp()
                    # sock, _ = sock.accept()
                    # sock.close()
                    self.log("Unexpected SSL EOF.")
                    self.close()
                else:
                    raise
            except SSL.Error as err:
                debug(f"call: _do_ssl_handshake, err: {err!r}", inst=self)
                self.handle_failed_ssl_handshake()
            else:
                debug("SSL connection established", self)
                self._ssl_accepting = False
                self._ssl_established = True
                self.handle_ssl_established()

        def handle_ssl_established(self):
            """Called when SSL handshake has completed."""

        def handle_ssl_shutdown(self):
            """Called when SSL shutdown() has completed."""
            super().close()

        def handle_failed_ssl_handshake(self):
            raise NotImplementedError("must be implemented in subclass")

        def handle_read_event(self):
            if not self._ssl_requested:
                super().handle_read_event()
            else:
                with self._handle_ssl_want_rw():
                    self._ssl_want_read = False
                    if self._ssl_accepting:
                        self._do_ssl_handshake()
                    elif self._ssl_closing:
                        self._do_ssl_shutdown()
                    else:
                        super().handle_read_event()

        def handle_write_event(self):
            if not self._ssl_requested:
                super().handle_write_event()
            else:
                with self._handle_ssl_want_rw():
                    self._ssl_want_write = False
                    if self._ssl_accepting:
                        self._do_ssl_handshake()
                    elif self._ssl_closing:
                        self._do_ssl_shutdown()
                    else:
                        super().handle_write_event()

        def handle_error(self):
            self._error = True
            try:
                raise  # noqa: PLE0704
            except Exception:
                self.log_exception(self)
            # when facing an unhandled exception in here it's better
            # to rely on base class (FTPHandler or DTPHandler)
            # close() method as it does not imply SSL shutdown logic
            try:
                super().close()
            except Exception:
                logger.critical(traceback.format_exc())

        def send(self, data):
            if not isinstance(data, bytes):
                data = bytes(data)
            try:
                return super().send(data)
            except SSL.WantReadError:
                debug("call: send(), err: ssl-want-read", inst=self)
                self._ssl_want_read = True
                return 0
            except SSL.WantWriteError:
                debug("call: send(), err: ssl-want-write", inst=self)
                self._ssl_want_write = True
                return 0
            except SSL.ZeroReturnError:
                debug(
                    "call: send() -> shutdown(), err: zero-return", inst=self
                )
                super().handle_close()
                return 0
            except SSL.SysCallError as err:
                debug(f"call: send(), err: {err!r}", inst=self)
                errnum, errstr = err.args
                if errnum == errno.EWOULDBLOCK:
                    return 0
                elif (
                    errnum in _ERRNOS_DISCONNECTED
                    or errstr == "Unexpected EOF"
                ):
                    super().handle_close()
                    return 0
                else:
                    raise

        def recv(self, buffer_size):
            try:
                return super().recv(buffer_size)
            except SSL.WantReadError as err:
                debug("call: recv(), err: ssl-want-read", inst=self)
                self._ssl_want_read = True
                raise RetryError from err
            except SSL.WantWriteError as err:
                debug("call: recv(), err: ssl-want-write", inst=self)
                self._ssl_want_write = True
                raise RetryError from err
            except SSL.ZeroReturnError:
                debug(
                    "call: recv() -> shutdown(), err: zero-return", inst=self
                )
                super().handle_close()
                return b""
            except SSL.SysCallError as err:
                debug(f"call: recv(), err: {err!r}", inst=self)
                errnum, errstr = err.args
                if (
                    errnum in _ERRNOS_DISCONNECTED
                    or errstr == "Unexpected EOF"
                ):
                    super().handle_close()
                    return b""
                else:
                    raise

        def _do_ssl_shutdown(self):
            """Executes a SSL_shutdown() call to revert the connection
            back to clear-text.
            twisted/internet/tcp.py code has been used as an example.
            """
            self._ssl_closing = True
            if os.name == "posix":
                # since SSL_shutdown() doesn't report errors, an empty
                # write call is done first, to try to detect if the
                # connection has gone away
                try:
                    os.write(self.socket.fileno(), b"")
                except OSError as err:
                    debug(
                        f"call: _do_ssl_shutdown() -> os.write, err: {err!r}",
                        inst=self,
                    )
                    if err.errno in {
                        errno.EINTR,
                        errno.EWOULDBLOCK,
                        errno.ENOBUFS,
                    }:
                        return
                    elif err.errno in _ERRNOS_DISCONNECTED:
                        return super().close()
                    else:
                        raise
            # Ok, this a mess, but the underlying OpenSSL API simply
            # *SUCKS* and I really couldn't do any better.
            #
            # Here we just want to shutdown() the SSL layer and then
            # close() the connection so we're not interested in a
            # complete SSL shutdown() handshake, so let's pretend
            # we already received a "RECEIVED" shutdown notification
            # from the client.
            # Once the client received our "SENT" shutdown notification
            # then we close() the connection.
            #
            # Since it is not clear what errors to expect during the
            # entire procedure we catch them all and assume the
            # following:
            # - WantReadError and WantWriteError means "retry"
            # - ZeroReturnError, SysCallError[EOF], Error[] are all
            #   aliases for disconnection
            try:
                laststate = self.socket.get_shutdown()
                self.socket.set_shutdown(laststate | SSL.RECEIVED_SHUTDOWN)
                done = self.socket.shutdown()
                if not laststate & SSL.RECEIVED_SHUTDOWN:
                    self.socket.set_shutdown(SSL.SENT_SHUTDOWN)
            except SSL.WantReadError:
                self._ssl_want_read = True
                debug("call: _do_ssl_shutdown, err: ssl-want-read", inst=self)
            except SSL.WantWriteError:
                self._ssl_want_write = True
                debug("call: _do_ssl_shutdown, err: ssl-want-write", inst=self)
            except SSL.ZeroReturnError:
                debug(
                    "call: _do_ssl_shutdown() -> shutdown(), err: zero-return",
                    inst=self,
                )
                super().close()
            except SSL.SysCallError as err:
                debug(
                    f"call: _do_ssl_shutdown() -> shutdown(), err: {err!r}",
                    inst=self,
                )
                errnum, errstr = err.args
                if (
                    errnum in _ERRNOS_DISCONNECTED
                    or errstr == "Unexpected EOF"
                ):
                    super().close()
                else:
                    raise
            except SSL.Error as err:
                debug(
                    f"call: _do_ssl_shutdown() -> shutdown(), err: {err!r}",
                    inst=self,
                )
                # see:
                # https://github.com/giampaolo/pyftpdlib/issues/171
                # https://bugs.launchpad.net/pyopenssl/+bug/785985
                if err.args and not getattr(err, "errno", None):
                    pass
                else:
                    raise
            except OSError as err:
                debug(
                    f"call: _do_ssl_shutdown() -> shutdown(), err: {err!r}",
                    inst=self,
                )
                if err.errno in _ERRNOS_DISCONNECTED:
                    super().close()
                else:
                    raise
            else:
                if done:
                    debug(
                        "call: _do_ssl_shutdown(), shutdown completed",
                        inst=self,
                    )
                    self._ssl_established = False
                    self._ssl_closing = False
                    self.handle_ssl_shutdown()
                else:
                    debug(
                        "call: _do_ssl_shutdown(), shutdown not completed yet",
                        inst=self,
                    )

        def close(self):
            if self._ssl_established and not self._error:
                self._do_ssl_shutdown()
            else:
                self._ssl_accepting = False
                self._ssl_established = False
                self._ssl_closing = False
                super().close()

    class TLS_DTPHandler(SSLConnection, DTPHandler):
        """A DTPHandler subclass supporting TLS/SSL."""

        def __init__(self, sock, cmd_channel):
            super().__init__(sock, cmd_channel)
            if self.cmd_channel._prot:
                self.secure_connection(self.cmd_channel.ssl_context)

        def __repr__(self):
            return DTPHandler.__repr__(self)

        def use_sendfile(self):
            if isinstance(self.socket, SSL.Connection):
                return False
            else:
                return super().use_sendfile()

        def handle_failed_ssl_handshake(self):
            # TLS/SSL handshake failure, probably client's fault which
            # used a SSL version different from server's.
            # RFC-4217, chapter 10.2 expects us to return 522 over the
            # command channel.
            self.cmd_channel.respond("522 SSL handshake failed.")
            self.cmd_channel.log_cmd("PROT", "P", 522, "SSL handshake failed.")
            self.close()

    class TLS_FTPHandler(SSLConnection, FTPHandler):
        """A FTPHandler subclass supporting TLS/SSL.
        Implements AUTH, PBSZ and PROT commands (RFC-2228 and RFC-4217).

        Configurable attributes:

         - (bool) tls_control_required:
            When True requires SSL/TLS to be established on the control
            channel, before logging in.  This means the user will have
            to issue AUTH before USER/PASS (default False).

         - (bool) tls_data_required:
            When True requires SSL/TLS to be established on the data
            channel.  This means the user will have to issue PROT
            before PASV or PORT (default False).

        SSL-specific options:

         - (string) certfile:
            the path to the file which contains a certificate to be
            used to identify the local side of the connection.
            This  must always be specified, unless context is provided
            instead.

         - (string) keyfile:
            the path to the file containing the private RSA key;
            can be omitted if certfile already contains the private
            key (defaults: None).

         - (int) ssl_protocol:
            the desired SSL protocol version to use. This defaults to
            TLS_SERVER_METHOD, which includes TLSv1, TLSv1.1, TLSv1.2
            and TLSv1.3. The actual protocol version used will be
            negotiated to the highest version mutually supported by the
            client and the server.

         - (int) ssl_options:
            specific OpenSSL options. These default to:
            SSL.OP_NO_SSLv2 | SSL.OP_NO_SSLv3 | SSL.OP_NO_COMPRESSION
            ...which are all considered insecure features.
            Can be set to None in order to improve compatibility with
            older (insecure) FTP clients.

          - (instance) ssl_context:
            a SSL Context object previously configured; if specified
            all other parameters will be ignored.
            (default None).
        """

        # configurable attributes
        tls_control_required = False
        tls_data_required = False
        certfile = None
        keyfile = None
        # Includes: SSLv3, TLSv1, TLSv1.1, TLSv1.2, TLSv1.3
        ssl_protocol = SSL.TLS_SERVER_METHOD
        # - SSLv2 is easily broken and is considered harmful and dangerous
        # - SSLv3 has several problems and is now dangerous
        # - Disable compression to prevent CRIME attacks for OpenSSL 1.0+
        #   (see https://github.com/shazow/urllib3/pull/309)
        ssl_options = SSL.OP_NO_SSLv2 | SSL.OP_NO_SSLv3
        if hasattr(SSL, "OP_NO_COMPRESSION"):
            ssl_options |= SSL.OP_NO_COMPRESSION
        ssl_context = None

        # overridden attributes
        dtp_handler = TLS_DTPHandler
        proto_cmds = FTPHandler.proto_cmds.copy()
        proto_cmds.update({
            "AUTH": dict(
                perm=None,
                auth=False,
                arg=True,
                help=(
                    "Syntax: AUTH <SP> TLS|SSL (set up secure control "
                    "channel)."
                ),
            ),
            "PBSZ": dict(
                perm=None,
                auth=False,
                arg=True,
                help="Syntax: PBSZ <SP> 0 (negotiate TLS buffer).",
            ),
            "PROT": dict(
                perm=None,
                auth=False,
                arg=True,
                help=(
                    "Syntax: PROT <SP> [C|P] (set up un/secure data channel)."
                ),
            ),
        })

        def __init__(self, conn, server, ioloop=None):
            super().__init__(conn, server, ioloop)
            if not self.connected:
                return
            self._extra_feats = ["AUTH TLS", "AUTH SSL", "PBSZ", "PROT"]
            self._pbsz = False
            self._prot = False
            self.ssl_context = self.get_ssl_context()

        def __repr__(self):
            return FTPHandler.__repr__(self)

        @classmethod
        def get_ssl_context(cls):
            if cls.ssl_context is None:
                if cls.certfile is None:
                    raise ValueError("at least certfile must be specified")

                cls.ssl_context = SSL.Context(cls.ssl_protocol)

                if not cls.keyfile:
                    cls.keyfile = cls.certfile
                for file in (cls.certfile, cls.keyfile):
                    if not os.path.isfile(cls.certfile):
                        msg = f"{file!r} does not exist"
                        raise FileNotFoundError(msg)

                cls.ssl_context.use_certificate_chain_file(cls.certfile)
                cls.ssl_context.use_privatekey_file(cls.keyfile)

                if cls.ssl_options:
                    cls.ssl_context.set_options(cls.ssl_options)

            return cls.ssl_context

        # --- overridden methods

        def flush_account(self):
            FTPHandler.flush_account(self)
            self._pbsz = False
            self._prot = False

        def process_command(self, cmd, *args, **kwargs):
            if cmd in ("USER", "PASS"):
                if self.tls_control_required and not self._ssl_established:
                    msg = "SSL/TLS required on the control channel."
                    self.respond("550 " + msg)
                    self.log_cmd(cmd, args[0], 550, msg)
                    return
            elif cmd in ("PASV", "EPSV", "PORT", "EPRT"):
                if self.tls_data_required and not self._prot:
                    msg = "SSL/TLS required on the data channel."
                    self.respond("550 " + msg)
                    self.log_cmd(cmd, args[0], 550, msg)
                    return
            FTPHandler.process_command(self, cmd, *args, **kwargs)

        def close(self):
            SSLConnection.close(self)
            FTPHandler.close(self)

        # --- new methods

        def handle_failed_ssl_handshake(self):
            # TLS/SSL handshake failure, probably client's fault which
            # used a SSL version different from server's.
            # We can't rely on the control connection anymore so we just
            # disconnect the client without sending any response.
            self.log("SSL handshake failed.")
            self.close()

        def ftp_AUTH(self, line):
            """Set up secure control channel."""
            arg = line.upper()
            if isinstance(self.socket, SSL.Connection):
                self.respond("503 Already using TLS.")
            elif arg in ("TLS", "TLS-C", "SSL", "TLS-P"):
                # From RFC-4217: "As the SSL/TLS protocols self-negotiate
                # their levels, there is no need to distinguish between SSL
                # and TLS in the application layer".
                self.respond(f"234 AUTH {arg} successful.")
                self.secure_connection(self.ssl_context)
            else:
                self.respond(
                    "502 Unrecognized encryption type (use TLS or SSL)."
                )

        def ftp_PBSZ(self, line):
            """Negotiate size of buffer for secure data transfer.
            For TLS/SSL the only valid value for the parameter is '0'.
            Any other value is accepted but ignored.
            """
            if not isinstance(self.socket, SSL.Connection):
                self.respond(
                    "503 PBSZ not allowed on insecure control connection."
                )
            else:
                self.respond("200 PBSZ=0 successful.")
                self._pbsz = True

        def ftp_PROT(self, line):
            """Setup un/secure data channel."""
            arg = line.upper()
            if not isinstance(self.socket, SSL.Connection):
                self.respond(
                    "503 PROT not allowed on insecure control connection."
                )
            elif not self._pbsz:
                self.respond(
                    "503 You must issue the PBSZ command prior to PROT."
                )
            elif arg == "C":
                self.respond("200 Protection set to Clear")
                self._prot = False
            elif arg == "P":
                self.respond("200 Protection set to Private")
                self._prot = True
            elif arg in ("S", "E"):
                self.respond(f"521 PROT {arg} unsupported (use C or P).")
            else:
                self.respond("502 Unrecognized PROT type (use C or P).")
