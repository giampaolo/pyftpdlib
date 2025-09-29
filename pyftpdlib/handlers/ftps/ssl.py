# Copyright (C) 2007 Giampaolo Rodola' <g.rodola@gmail.com>.
# Use of this source code is governed by MIT license that can be
# found in the LICENSE file.

import contextlib
import errno
import os
import traceback

from OpenSSL import SSL

from pyftpdlib.exceptions import _RetryError
from pyftpdlib.ioloop import _ERRNOS_DISCONNECTED
from pyftpdlib.log import debug
from pyftpdlib.log import logger

__all__ = ["SSLConnectionMixin"]


class SSLConnectionMixin:
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
        return self._ssl_accepting or self._ssl_want_read or super().readable()

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
                debug("ValueError and fd == -1 on secure_connection()", self)
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
            debug("call: _do_ssl_handshake, err: ssl-want-write", inst=self)
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
            debug("call: send() -> shutdown(), err: zero-return", inst=self)
            super().handle_close()
            return 0
        except SSL.SysCallError as err:
            debug(f"call: send(), err: {err!r}", inst=self)
            errnum, errstr = err.args
            if errnum == errno.EWOULDBLOCK:
                return 0
            elif errnum in _ERRNOS_DISCONNECTED or errstr == "Unexpected EOF":
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
            raise _RetryError from err
        except SSL.WantWriteError as err:
            debug("call: recv(), err: ssl-want-write", inst=self)
            self._ssl_want_write = True
            raise _RetryError from err
        except SSL.ZeroReturnError:
            debug("call: recv() -> shutdown(), err: zero-return", inst=self)
            super().handle_close()
            return b""
        except SSL.SysCallError as err:
            debug(f"call: recv(), err: {err!r}", inst=self)
            errnum, errstr = err.args
            if errnum in _ERRNOS_DISCONNECTED or errstr == "Unexpected EOF":
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
            if errnum in _ERRNOS_DISCONNECTED or errstr == "Unexpected EOF":
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
