# Copyright (C) 2007 Giampaolo Rodola' <g.rodola@gmail.com>.
# Use of this source code is governed by MIT license that can be
# found in the LICENSE file.

import contextlib
import ftplib
import socket
import threading
import time

import pytest

from pyftpdlib import handlers
from pyftpdlib import servers

from . import GLOBAL_TIMEOUT
from . import HOST
from . import PASSWD
from . import SUPPORTS_MULTIPROCESSING
from . import USER
from . import WINDOWS
from . import FtpdThreadWrapper
from . import PyftpdlibTestCase
from . import close_client
from .test_functional import TestCornerCases
from .test_functional import TestFtpAbort
from .test_functional import TestFtpAuthentication
from .test_functional import TestFtpCmdsSemantic
from .test_functional import TestFtpDummyCmds
from .test_functional import TestFtpFsOperations
from .test_functional import TestFtpListingCmds
from .test_functional import TestFtpRetrieveData
from .test_functional import TestFtpStoreData
from .test_functional import TestIPv4Environment
from .test_functional import TestIPv6Environment


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


# =====================================================================
# --- threaded FTP server mixin tests
# =====================================================================

# What we're going to do here is repeat the original functional tests
# defined in test_functinal.py but by using different concurrency
# modules (multi thread and multi process instead of async.
# This is useful as we reuse the existent functional tests which are
# supposed to work no matter what the concurrency model is.


class _TFTPd(FtpdThreadWrapper):
    server_class = servers.ThreadedFTPServer


class _DelayedThreadedFTPServer(servers.ThreadedFTPServer):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.worker_started = threading.Event()
        self.worker_release = threading.Event()

    def _start_task(self, *args, **kwargs):
        target = kwargs["target"]
        task_args = kwargs["args"]

        def delayed_target():
            self.worker_started.set()
            self.worker_release.wait()
            target(*task_args)

        return threading.Thread(target=delayed_target, name=kwargs.get("name"))


class _DelayedTFTPd(FtpdThreadWrapper):
    server_class = _DelayedThreadedFTPServer


class ThreadFTPTestMixin:
    server_class = _TFTPd


class WorkerTimeoutTestMixin:
    def setUp(self):
        super().setUp()
        self.server = None
        self.client = None

    def tearDown(self):
        if self.client is not None:
            self.client.close()
        if self.server is not None:
            self.server.stop()
        super().tearDown()

    def _test_control_timeout(self, authenticate):
        self.server = self.server_class()
        self.server.server.handler.timeout = 0.1
        self.server.start()
        self.client = ftplib.FTP(timeout=GLOBAL_TIMEOUT)
        self.client.connect(self.server.host, self.server.port)
        if authenticate:
            self.client.login(USER, PASSWD)
        with pytest.raises(
            ftplib.error_temp, match=r"421 Control connection timed out\."
        ):
            self.client.getresp()

    def test_control_timeout_before_data_channel(self):
        self._test_control_timeout(authenticate=False)

    def test_authenticated_control_timeout_before_data_channel(self):
        self._test_control_timeout(authenticate=True)

    def test_disabled_control_timeout(self):
        self.server = self.server_class()
        self.server.server.handler.timeout = 0
        self.server.start()
        self.client = ftplib.FTP(timeout=GLOBAL_TIMEOUT)
        self.client.connect(self.server.host, self.server.port)
        time.sleep(0.2)
        assert (
            self.client.sendcmd("NOOP") == "200 I successfully did nothing'."
        )

    def test_control_timeout_resets_after_command(self):
        self.server = self.server_class()
        self.server.server.handler.timeout = 2.0
        self.server.start()
        self.client = ftplib.FTP(timeout=GLOBAL_TIMEOUT)
        self.client.connect(self.server.host, self.server.port)
        time.sleep(1.0)
        assert (
            self.client.sendcmd("NOOP") == "200 I successfully did nothing'."
        )
        time.sleep(1.25)
        assert (
            self.client.sendcmd("NOOP") == "200 I successfully did nothing'."
        )
        time.sleep(1.0)
        with pytest.raises(
            ftplib.error_temp, match=r"421 Control connection timed out\."
        ):
            self.client.getresp()


class TestWorkerTimeoutThread(WorkerTimeoutTestMixin, PyftpdlibTestCase):
    server_class = _TFTPd


class TestWorkerTimeoutHandoff(PyftpdlibTestCase):
    def setUp(self):
        super().setUp()
        self.server = None
        self.client = None

    def tearDown(self):
        if self.client is not None:
            self.client.close()
        if self.server is not None:
            self.server.server.worker_release.set()
            self.server.stop()
        super().tearDown()

    def test_parent_timer_detached_before_worker_start(self):
        self.server = _DelayedTFTPd()
        self.server.server.handler.timeout = 2.0
        self.server.start()
        self.client = ftplib.FTP(timeout=GLOBAL_TIMEOUT)
        self.client.connect(self.server.host, self.server.port)
        assert self.server.server.worker_started.wait(GLOBAL_TIMEOUT)

        time.sleep(2.25)
        self.client.sock.settimeout(0.75)
        with pytest.raises(socket.timeout):
            self.client.sock.recv(1024)

        self.client.sock.settimeout(1.0)
        self.server.server.worker_release.set()
        with pytest.raises(
            ftplib.error_temp, match=r"421 Control connection timed out\."
        ):
            self.client.getresp()


class TestFtpAuthenticationThreadMixin(
    ThreadFTPTestMixin, TestFtpAuthentication
):
    pass


class TestTFtpDummyCmdsThreadMixin(ThreadFTPTestMixin, TestFtpDummyCmds):
    pass


class TestFtpCmdsSemanticThreadMixin(ThreadFTPTestMixin, TestFtpCmdsSemantic):
    pass


class TestFtpFsOperationsThreadMixin(ThreadFTPTestMixin, TestFtpFsOperations):
    pass


class TestFtpStoreDataThreadMixin(ThreadFTPTestMixin, TestFtpStoreData):
    pass


class TestFtpRetrieveDataThreadMixin(ThreadFTPTestMixin, TestFtpRetrieveData):
    pass


class TestFtpListingCmdsThreadMixin(ThreadFTPTestMixin, TestFtpListingCmds):
    pass


class TestFtpAbortThreadMixin(ThreadFTPTestMixin, TestFtpAbort):
    pass


# class TestTimeoutsThreadMixin(ThreadFTPTestMixin, TestTimeouts):
#     def test_data_timeout_not_reached(self): pass
# class TestConfOptsThreadMixin(ThreadFTPTestMixin, TestConfigurableOptions):
#     pass


# class TestCallbacksThreadMixin(ThreadFTPTestMixin, TestCallbacks):
#     pass


class TestIPv4EnvironmentThreadMixin(ThreadFTPTestMixin, TestIPv4Environment):
    pass


class TestIPv6EnvironmentThreadMixin(ThreadFTPTestMixin, TestIPv6Environment):
    pass


class TestCornerCasesThreadMixin(ThreadFTPTestMixin, TestCornerCases):
    pass


# class TestFTPServerThreadMixin(ThreadFTPTestMixin, TestFTPServer):
#     pass


# =====================================================================
# --- multiprocess FTP server mixin tests
# =====================================================================

if SUPPORTS_MULTIPROCESSING:

    class MultiProcFTPd(FtpdThreadWrapper):
        server_class = servers.MultiprocessFTPServer

    class MProcFTPTestMixin:
        server_class = MultiProcFTPd

else:

    @pytest.mark.skip(reason="multiprocessing module not installed")
    class MProcFTPTestMixin:
        pass


if SUPPORTS_MULTIPROCESSING:

    class TestWorkerTimeoutMProc(WorkerTimeoutTestMixin, PyftpdlibTestCase):
        server_class = MultiProcFTPd


class TestFtpAuthenticationMProcMixin(
    MProcFTPTestMixin, TestFtpAuthentication
):
    pass


class TestTFtpDummyCmdsMProcMixin(MProcFTPTestMixin, TestFtpDummyCmds):
    pass


class TestFtpCmdsSemanticMProcMixin(MProcFTPTestMixin, TestFtpCmdsSemantic):
    pass


class TestFtpFsOperationsMProcMixin(MProcFTPTestMixin, TestFtpFsOperations):

    def test_unforeseen_mdtm_event(self):
        pass


class TestFtpStoreDataMProcMixin(MProcFTPTestMixin, TestFtpStoreData):
    pass


class TestFtpRetrieveDataMProcMixin(MProcFTPTestMixin, TestFtpRetrieveData):
    pass


class TestFtpListingCmdsMProcMixin(MProcFTPTestMixin, TestFtpListingCmds):
    pass


class TestFtpAbortMProcMixin(MProcFTPTestMixin, TestFtpAbort):
    pass


# class TestTimeoutsMProcMixin(MProcFTPTestMixin, TestTimeouts):
#     def test_data_timeout_not_reached(self): pass
# class TestConfiOptsMProcMixin(MProcFTPTestMixin, TestConfigurableOptions):
#     pass
# class TestCallbacksMProcMixin(MProcFTPTestMixin, TestCallbacks): pass


class TestIPv4EnvironmentMProcMixin(MProcFTPTestMixin, TestIPv4Environment):
    pass


class TestIPv6EnvironmentMProcMixin(MProcFTPTestMixin, TestIPv6Environment):
    pass


class TestCornerCasesMProcMixin(MProcFTPTestMixin, TestCornerCases):
    pass


# class TestFTPServerMProcMixin(MProcFTPTestMixin, TestFTPServer):
#     pass
