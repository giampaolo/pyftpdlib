# Copyright (C) 2007 Giampaolo Rodola' <g.rodola@gmail.com>.
# Use of this source code is governed by MIT license that can be
# found in the LICENSE file.

import contextlib
import ftplib
import socket
import ssl
import time
from unittest import mock

import OpenSSL  # requires "pip install pyopenssl"
import pytest
from OpenSSL import SSL

from pyftpdlib.handlers import TLS_FTPHandler

from . import CERTFILE
from . import GLOBAL_TIMEOUT
from . import PASSWD
from . import USER
from . import FtpdThreadWrapper
from . import PyftpdlibTestCase
from . import close_client
from . import get_server_handler
from . import test_functional as tf

del OpenSSL

# =====================================================================
# --- FTPS mixin tests
# =====================================================================

# What we're going to do here is repeat the original functional tests
# defined in test_functinal.py but by using FTPS.
# we secure both control and data connections before running any test.
# This is useful as we reuse the existent functional tests which are
# supposed to work no matter if the underlying protocol is FTP or FTPS.


class FTPSClient(ftplib.FTP_TLS):
    """A modified version of ftplib.FTP_TLS class which implicitly
    secure the data connection after login().
    """

    def login(self, *args, **kwargs):
        ftplib.FTP_TLS.login(self, *args, **kwargs)
        self.prot_p()


class FTPSServer(FtpdThreadWrapper):
    """A threaded FTPS server used for functional testing."""

    handler = TLS_FTPHandler
    handler.certfile = CERTFILE


class TLSTestMixin:
    server_class = FTPSServer
    client_class = FTPSClient


class TestFtpAuthenticationTLSMixin(TLSTestMixin, tf.TestFtpAuthentication):
    pass


class TestTFtpDummyCmdsTLSMixin(TLSTestMixin, tf.TestFtpDummyCmds):
    pass


class TestFtpCmdsSemanticTLSMixin(TLSTestMixin, tf.TestFtpCmdsSemantic):
    pass


class TestFtpFsOperationsTLSMixin(TLSTestMixin, tf.TestFtpFsOperations):
    pass


class TestFtpStoreDataTLSMixin(TLSTestMixin, tf.TestFtpStoreData):
    pass


class TestFtpRetrieveDataTLSMixin(TLSTestMixin, tf.TestFtpRetrieveData):
    pass


class TestFtpListingCmdsTLSMixin(TLSTestMixin, tf.TestFtpListingCmds):
    pass


class TestFtpAbortTLSMixin(TLSTestMixin, tf.TestFtpAbort):

    @pytest.mark.skip(reason="SSL sockets can't send OOB data")
    def test_oob_abor(self):
        pass


class TestTimeoutsTLSMixin(TLSTestMixin, tf.TestTimeouts):

    # XXX: temporary, to debug a failure on macOS CI.
    def test_data_timeout_not_reached(self):
        import logging  # noqa: PLC0415
        import select  # noqa: PLC0415
        import subprocess  # noqa: PLC0415
        import sys  # noqa: PLC0415

        import psutil  # noqa: PLC0415

        from pyftpdlib.handlers import TLS_DTPHandler  # noqa: PLC0415

        t0 = time.monotonic()

        def dbg(msg):
            sys.stderr.write(f"DBG {time.monotonic() - t0:.3f} {msg}\n")

        def tcp_states(laddr):
            return [
                (c.laddr, c.raddr, c.status)
                for c in psutil.Process().net_connections("tcp")
                if c.laddr and tuple(c.laddr)[:2] == tuple(laddr)[:2]
            ]

        def kq_probe(fd):
            if not hasattr(select, "kqueue"):
                return None
            kq = select.kqueue()
            try:
                kev = select.kevent(
                    fd, filter=select.KQ_FILTER_READ, flags=select.KQ_EV_ADD
                )
                evs = kq.control([kev], 1, 0)
                return [(e.flags, e.fflags, e.data) for e in evs]
            except OSError as err:
                return repr(err)
            finally:
                kq.close()

        def netstat(port):
            if not hasattr(select, "kqueue"):
                return None
            out = subprocess.run(
                ["netstat", "-an", "-p", "tcp"],
                capture_output=True,
                text=True,
                check=False,
            ).stdout
            return [
                " ".join(x.split())
                for x in out.splitlines()
                if f".{port} " in x
            ]

        reads = {"n": 0, "last": None}
        orig_read = TLS_DTPHandler.handle_read_event

        def handle_read_event(dtp):
            reads["n"] += 1
            reads["last"] = time.monotonic() - t0
            return orig_read(dtp)

        orig_timeout = TLS_DTPHandler.handle_timeout

        def handle_timeout(dtp):
            fd = dtp._fileno
            dbg(
                f"tick reads={reads['n']} last_read={reads['last']}"
                f" select_r={bool(select.select([fd], [], [], 0)[0])}"
                f" pending={dtp.socket.pending()}"
                f" kq_active={getattr(dtp.ioloop, '_active', {}).get(fd)}"
                f" kq_probe={kq_probe(fd)}"
                f" tcp={tcp_states(dtp.socket.getsockname())}"
            )
            dbg(f"netstat {netstat(dtp.socket.getsockname()[1])}")
            dbg(
                f"tick bytes={dtp.get_transmitted_bytes()}"
                f" lastdata={dtp._lastdata} accepting={dtp._ssl_accepting}"
                f" established={dtp._ssl_established}"
                f" closing={dtp._ssl_closing}"
                f" want_r={dtp._ssl_want_read} want_w={dtp._ssl_want_write}"
                f" receive={dtp.receive} closed={dtp._closed}"
                f" events={dtp._wanted_io_events}"
                f" ioloop={type(dtp.ioloop).__name__}"
            )
            return orig_timeout(dtp)

        logger = logging.getLogger("pyftpdlib")
        handler = logging.StreamHandler(sys.stderr)
        handler.setFormatter(
            logging.Formatter("DBG %(relativeCreated)d %(message)s")
        )
        old_level = logger.level
        logger.addHandler(handler)
        logger.setLevel(logging.DEBUG)
        try:
            with mock.patch.object(
                TLS_DTPHandler, "handle_timeout", handle_timeout
            ), mock.patch.object(
                TLS_DTPHandler, "handle_read_event", handle_read_event
            ):
                self._setUp(data_timeout=0.5 if tf.CI_TESTING else 0.1)
                dbg("transfercmd")
                with contextlib.closing(
                    self.client.transfercmd("stor " + self.testfn)
                ) as sock:
                    dbg("connected")
                    sent = 0
                    stop_at = time.time() + 0.2
                    while time.time() < stop_at:
                        sent += sock.send(b"x" * 1024)
                    dbg(f"sent {sent} bytes")
                    caddr = sock.getsockname()
                    dbg(f"client before close {tcp_states(caddr)}")
                    sock.close()
                    dbg("closed")
                    dbg(f"resp {self.client.voidresp()}")
        finally:
            logger.removeHandler(handler)
            logger.setLevel(old_level)


class TestConfigurableOptionsTLSMixin(
    TLSTestMixin, tf.TestConfigurableOptions
):
    pass


class TestIPv4EnvironmentTLSMixin(TLSTestMixin, tf.TestIPv4Environment):
    pass


class TestIPv6EnvironmentTLSMixin(TLSTestMixin, tf.TestIPv6Environment):
    pass


class TestCornerCasesTLSMixin(TLSTestMixin, tf.TestCornerCases):
    pass


# =====================================================================
# dedicated FTPS tests
# =====================================================================


class TestFTPS(PyftpdlibTestCase):
    """Specific tests fot TSL_FTPHandler class."""

    def _setup(
        self,
        tls_control_required=False,
        tls_data_required=False,
        ssl_protocol=ssl.PROTOCOL_SSLv23,
    ):
        self.server = FTPSServer()
        self.server.handler.tls_control_required = tls_control_required
        self.server.handler.tls_data_required = tls_data_required
        self.server.handler.ssl_protocol = ssl_protocol
        self.server.start()
        self.client = ftplib.FTP_TLS(timeout=GLOBAL_TIMEOUT)
        self.client.connect(self.server.host, self.server.port)

    def setUp(self):
        super().setUp()
        self.client = None
        self.server = None

    def tearDown(self):
        if self.client is not None:
            close_client(self.client)
        if self.server is not None:
            self.server.handler.ssl_protocol = ssl.PROTOCOL_SSLv23
            self.server.handler.tls_control_required = False
            self.server.handler.tls_data_required = False
            self.server.stop()
        super().tearDown()

    def test_auth(self):
        # unsecured
        self._setup()
        self.client.login(secure=False)
        assert not isinstance(self.client.sock, ssl.SSLSocket)
        # secured
        self.client.login()
        assert isinstance(self.client.sock, ssl.SSLSocket)
        # AUTH issued twice
        msg = "503 Already using TLS."
        with pytest.raises(ftplib.error_perm, match=msg):
            self.client.sendcmd("auth tls")

    def test_pbsz(self):
        # unsecured
        self._setup()
        self.client.login(secure=False)
        msg = "503 PBSZ not allowed on insecure control connection."
        with pytest.raises(ftplib.error_perm, match=msg):
            self.client.sendcmd("pbsz 0")
        # secured
        self.client.login(secure=True)
        resp = self.client.sendcmd("pbsz 0")
        assert resp == "200 PBSZ=0 successful."

    def test_prot(self):
        self._setup()
        self.client.login(secure=False)
        msg = "503 PROT not allowed on insecure control connection."
        with pytest.raises(ftplib.error_perm, match=msg):
            self.client.sendcmd("prot p")
        self.client.login(secure=True)
        # secured
        self.client.prot_p()
        sock = self.client.transfercmd("list")
        with contextlib.closing(sock):
            while True:
                if not sock.recv(1024):
                    self.client.voidresp()
                    break
            assert isinstance(sock, ssl.SSLSocket)
            # unsecured
            self.client.prot_c()
        sock = self.client.transfercmd("list")
        with contextlib.closing(sock):
            while True:
                if not sock.recv(1024):
                    self.client.voidresp()
                    break
            assert not isinstance(sock, ssl.SSLSocket)

    def test_feat(self):
        self._setup()
        feat = self.client.sendcmd("feat")
        cmds = ["AUTH TLS", "AUTH SSL", "PBSZ", "PROT"]
        for cmd in cmds:
            assert cmd in feat

    def test_unforseen_ssl_shutdown(self):
        self._setup()
        self.client.login()
        try:
            sock = self.client.sock.unwrap()
        except OSError as err:
            if err.errno == 0:
                return
            raise
        sock.settimeout(GLOBAL_TIMEOUT)
        sock.sendall(b"noop")
        try:
            chunk = sock.recv(1024)
        except OSError:
            pass
        else:
            assert chunk == b""

    def test_send_empty_data(self):
        # SSL_write() with no data raises a bogus "Unexpected EOF" once
        # the handshake is done, and the server closed the connection.
        self._setup()
        self.client.login()
        self.client.prot_p()
        host, port = self.client.makepasv()
        sock = socket.create_connection((host, port), GLOBAL_TIMEOUT)
        conn = self.client.context.wrap_socket(
            sock, server_hostname=self.client.host
        )
        with contextlib.closing(conn):
            stop_at = time.monotonic() + GLOBAL_TIMEOUT
            while True:
                with self.server.lock:
                    handler = get_server_handler(self.server.server)
                    dtp = handler.data_channel
                    if dtp is not None and dtp._ssl_established:
                        assert dtp.send(b"") == 0
                        assert not dtp._closed
                        break
                assert time.monotonic() < stop_at
                time.sleep(0.001)

    def test_ssl_shutdown_error(self):
        # On Windows SSL_shutdown() fails with SSL.Error if the client
        # reset the connection. The data channel was never closed, and
        # the client got no response.
        self._setup()
        self.client.login()
        self.client.prot_p()
        host, port = self.client.makepasv()
        sock = socket.create_connection((host, port), GLOBAL_TIMEOUT)
        conn = self.client.context.wrap_socket(
            sock, server_hostname=self.client.host
        )
        with contextlib.closing(conn):
            stop_at = time.monotonic() + GLOBAL_TIMEOUT
            while True:
                with self.server.lock:
                    handler = get_server_handler(self.server.server)
                    dtp = handler.data_channel
                    if dtp is not None and dtp._ssl_established:
                        err = SSL.Error([("SSL routines", "", "")])
                        with mock.patch.object(
                            dtp.socket, "shutdown", side_effect=err
                        ):
                            dtp.close()
                        assert dtp._closed
                        break
                assert time.monotonic() < stop_at
                time.sleep(0.001)

    def test_data_conn_closed_during_handshake(self):
        # The server closed the data channel without replying, and the
        # client waited forever.
        self._setup()
        self.client.login(USER, PASSWD)
        self.client.prot_p()
        host, port = self.client.makepasv()
        sock = socket.create_connection((host, port), GLOBAL_TIMEOUT)
        with contextlib.closing(sock):
            self.client.sendcmd("stor " + self.get_testfn())
        with pytest.raises(ftplib.error_perm, match="522"):
            self.client.voidresp()

    def test_tls_control_required(self):
        self._setup(tls_control_required=True)
        msg = "550 SSL/TLS required on the control channel."
        with pytest.raises(ftplib.error_perm, match=msg):
            self.client.sendcmd("user " + USER)
        with pytest.raises(ftplib.error_perm, match=msg):
            self.client.sendcmd("pass " + PASSWD)
        self.client.login(secure=True)

    def test_tls_data_required(self):
        self._setup(tls_data_required=True)
        self.client.login(secure=True)
        msg = "550 SSL/TLS required on the data channel."
        with pytest.raises(ftplib.error_perm, match=msg):
            self.client.retrlines("list", lambda x: x)
        self.client.prot_p()
        self.client.retrlines("list", lambda x: x)
