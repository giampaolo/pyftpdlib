# Copyright (C) 2007 Giampaolo Rodola' <g.rodola@gmail.com>.
# Use of this source code is governed by MIT license that can be
# found in the LICENSE file.

import contextlib
import ftplib
import os
import signal
import socket
import subprocess
import sys
import textwrap
import time
from unittest import mock

import psutil
import pytest

from pyftpdlib import handlers
from pyftpdlib import servers

from . import GLOBAL_TIMEOUT
from . import HOME
from . import HOST
from . import OSX
from . import PASSWD
from . import SUPPORTS_MULTIPROCESSING
from . import USER
from . import WINDOWS
from . import FtpdThreadWrapper
from . import PyftpdlibTestCase
from . import close_client
from . import disable_log_warning
from . import test_functional as tf


class TestFTPServer(PyftpdlibTestCase):
    """Tests for *FTPServer classes."""

    server_class = FtpdThreadWrapper
    client_class = ftplib.FTP

    def setUp(self):
        super().setUp()
        self.server = None
        self.client = None

    def tearDown(self):
        if self.client is not None:
            close_client(self.client)
        if self.server is not None:
            self.server.stop()
        super().tearDown()

    @pytest.mark.skipif(WINDOWS, reason="POSIX only")
    def test_sock_instead_of_addr(self):
        # pass a socket object instead of an address tuple to FTPServer
        # constructor
        with contextlib.closing(socket.socket()) as sock:
            sock.bind((HOST, 0))
            sock.listen(5)
            ip, port = sock.getsockname()[:2]
            self.server = self.server_class(sock)
            self.server.start()
            self.client = self.client_class(timeout=GLOBAL_TIMEOUT)
            self.client.connect(ip, port)
            self.client.login(USER, PASSWD)
            self.client.quit()

    def test_ctx_mgr(self):
        with servers.FTPServer((HOST, 0), handlers.FTPHandler) as server:
            assert server is not None

    def test_serve_forever_non_blocking_no_log(self):
        # With blocking=False serve_forever() is called in a loop, so it
        # shouldn't log the server start every time.
        with servers.FTPServer((HOST, 0), handlers.FTPHandler) as server:
            with mock.patch("pyftpdlib.servers.logger.info") as m:
                server.serve_forever(timeout=0, blocking=False)
            assert not m.called

    def test_serve_forever_logs_listen_address(self):
        klass = self.server_class.server_class
        with klass((HOST, 0), handlers.FTPHandler) as server:
            server.ioloop.call_later(0, server.close_all)
            with mock.patch("pyftpdlib.servers.logger.info") as m:
                server.serve_forever(timeout=0.01)
            msgs = [str(call.args[0]) for call in m.call_args_list]
            assert any(">>> starting FTP server on" in x for x in msgs)

    @pytest.mark.skipif(WINDOWS, reason="POSIX only")
    def test_worker_processes_non_blocking(self):
        with servers.FTPServer((HOST, 0), handlers.FTPHandler) as server:
            with pytest.raises(ValueError, match="mutually exclusive"):
                server.serve_forever(worker_processes=2, blocking=False)

    @pytest.mark.skipif(WINDOWS, reason="POSIX only")
    @pytest.mark.skipif(
        OSX, reason="broken on macOS (kqueue is not inherited on fork)"
    )
    def test_worker_processes(self):
        code = textwrap.dedent(f"""
            from pyftpdlib.authorizers import DummyAuthorizer
            from pyftpdlib.handlers import FTPHandler
            from pyftpdlib.servers import FTPServer

            FTPHandler.authorizer = DummyAuthorizer()
            FTPHandler.authorizer.add_user({USER!r}, {PASSWD!r}, {HOME!r})
            server = FTPServer(({HOST!r}, 0), FTPHandler)
            print(server.address[1], flush=True)
            server.serve_forever(worker_processes=2)
        """)
        proc = subprocess.Popen(
            [sys.executable, "-c", code],
            stdout=subprocess.PIPE,
            text=True,
            start_new_session=True,
        )
        try:
            port = int(proc.stdout.readline())
            stop_at = time.monotonic() + GLOBAL_TIMEOUT
            while len(psutil.Process(proc.pid).children()) != 2:
                assert time.monotonic() < stop_at
                time.sleep(0.01)
            for _ in range(4):
                self.client = self.client_class(timeout=GLOBAL_TIMEOUT)
                self.client.connect(HOST, port)
                self.client.login(USER, PASSWD)
                self.client.quit()
                self.client = None
        finally:
            # Kill the parent and the workers at once, else the parent
            # restarts the workers.
            os.killpg(proc.pid, signal.SIGKILL)
            proc.wait()
            proc.stdout.close()


# =====================================================================
# --- threaded FTP server mixin tests
# =====================================================================

# What we're going to do here is repeat the original functional tests
# defined in test_functinal.py but by using different concurrency
# modules (multi thread and multi process instead of async.
# This is useful as we reuse the existent functional tests which are
# supposed to work no matter what the concurrency model is.


class SpawnerConfOptsMixin:

    @disable_log_warning
    def test_max_connections(self):
        self.server = self.server_class()
        self.server.server.max_cons = 2
        self.server.start()

        c1 = self.client_class(timeout=GLOBAL_TIMEOUT)
        c2 = self.client_class(timeout=GLOBAL_TIMEOUT)
        c3 = self.client_class(timeout=GLOBAL_TIMEOUT)
        try:
            c1.connect(self.server.host, self.server.port)
            c2.connect(self.server.host, self.server.port)
            with pytest.raises(
                ftplib.error_temp, match="Too many connections"
            ):
                c3.connect(self.server.host, self.server.port)
            c1.login(USER, PASSWD)
            c1.makepasv()
        finally:
            for c in (c1, c2, c3):
                close_client(c)

    def test_closed_handler_not_spawned(self):
        # Simulate a client which disconnected before the 220 banner:
        # the handler is closed before the server spawns a worker.
        class Handler(handlers.FTPHandler):
            def on_connect(self):
                self.close()

        self.server = self.server_class()
        self.server.server.handler = Handler
        self.server.start()
        c = self.client_class(timeout=GLOBAL_TIMEOUT)
        try:
            with pytest.raises(EOFError):
                c.connect(self.server.host, self.server.port)
            with self.server.lock:
                assert self.server.server._active_tasks == []
        finally:
            close_client(c)


class _TFTPd(FtpdThreadWrapper):
    server_class = servers.ThreadedFTPServer


class ThreadFTPTestMixin:
    server_class = _TFTPd


class TestFtpAuthenticationThreadMixin(
    ThreadFTPTestMixin, tf.TestFtpAuthentication
):
    pass


class TestTFtpDummyCmdsThreadMixin(ThreadFTPTestMixin, tf.TestFtpDummyCmds):
    pass


class TestFtpCmdsSemanticThreadMixin(
    ThreadFTPTestMixin, tf.TestFtpCmdsSemantic
):
    pass


class TestFtpFsOperationsThreadMixin(
    ThreadFTPTestMixin, tf.TestFtpFsOperations
):
    pass


class TestFtpStoreDataThreadMixin(ThreadFTPTestMixin, tf.TestFtpStoreData):
    pass


class TestFtpRetrieveDataThreadMixin(
    ThreadFTPTestMixin, tf.TestFtpRetrieveData
):
    pass


class TestFtpListingCmdsThreadMixin(ThreadFTPTestMixin, tf.TestFtpListingCmds):
    pass


class TestFtpAbortThreadMixin(ThreadFTPTestMixin, tf.TestFtpAbort):
    pass


class TestTimeoutsThreadMixin(ThreadFTPTestMixin, tf.TestTimeouts):
    pass


class TestConfOptsThreadMixin(
    ThreadFTPTestMixin, SpawnerConfOptsMixin, tf.TestConfigurableOptions
):
    pass


class TestCallbacksThreadMixin(ThreadFTPTestMixin, tf.TestCallbacks):
    pass


class TestIPv4EnvironmentThreadMixin(
    ThreadFTPTestMixin, tf.TestIPv4Environment
):
    pass


class TestIPv6EnvironmentThreadMixin(
    ThreadFTPTestMixin, tf.TestIPv6Environment
):
    pass


class TestCornerCasesThreadMixin(ThreadFTPTestMixin, tf.TestCornerCases):
    pass


class TestFTPServerThreadMixin(ThreadFTPTestMixin, TestFTPServer):
    pass


# =====================================================================
# --- multiprocess FTP server mixin tests
# =====================================================================

if SUPPORTS_MULTIPROCESSING:

    class MultiProcFTPd(FtpdThreadWrapper):
        server_class = servers.MultiprocessFTPServer

    class MProcFTPTestMixin:
        server_class = MultiProcFTPd

else:

    @pytest.mark.skip(
        reason="MultiprocessFTPServer not available or broken on this platform"
    )
    class MProcFTPTestMixin:
        pass


class TestFtpAuthenticationMProcMixin(
    MProcFTPTestMixin, tf.TestFtpAuthentication
):
    pass


class TestTFtpDummyCmdsMProcMixin(MProcFTPTestMixin, tf.TestFtpDummyCmds):
    pass


class TestFtpCmdsSemanticMProcMixin(MProcFTPTestMixin, tf.TestFtpCmdsSemantic):
    pass


class TestFtpFsOperationsMProcMixin(MProcFTPTestMixin, tf.TestFtpFsOperations):
    pass


class TestFtpStoreDataMProcMixin(MProcFTPTestMixin, tf.TestFtpStoreData):
    pass


class TestFtpRetrieveDataMProcMixin(MProcFTPTestMixin, tf.TestFtpRetrieveData):
    pass


class TestFtpListingCmdsMProcMixin(MProcFTPTestMixin, tf.TestFtpListingCmds):
    pass


class TestFtpAbortMProcMixin(MProcFTPTestMixin, tf.TestFtpAbort):
    pass


class TestTimeoutsMProcMixin(MProcFTPTestMixin, tf.TestTimeouts):
    pass


class TestConfOptsMProcMixin(
    MProcFTPTestMixin, SpawnerConfOptsMixin, tf.TestConfigurableOptions
):
    pass


class TestCallbacksMProcMixin(MProcFTPTestMixin, tf.TestCallbacks):
    pass


class TestIPv4EnvironmentMProcMixin(MProcFTPTestMixin, tf.TestIPv4Environment):
    pass


class TestIPv6EnvironmentMProcMixin(MProcFTPTestMixin, tf.TestIPv6Environment):
    pass


class TestCornerCasesMProcMixin(MProcFTPTestMixin, tf.TestCornerCases):
    pass


class TestFTPServerMProcMixin(MProcFTPTestMixin, TestFTPServer):
    pass
