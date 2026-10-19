# Copyright (C) 2007 Giampaolo Rodola' <g.rodola@gmail.com>.
# Use of this source code is governed by MIT license that can be
# found in the LICENSE file.

import contextlib
import ftplib
import socket

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


# class TestTimeoutsThreadMixin(ThreadFTPTestMixin, TestTimeouts):
#     def test_data_timeout_not_reached(self): pass
# class TestConfOptsThreadMixin(ThreadFTPTestMixin, TestConfigurableOptions):
#     pass


# class TestCallbacksThreadMixin(ThreadFTPTestMixin, TestCallbacks):
#     pass


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


class TestFtpAuthenticationMProcMixin(
    MProcFTPTestMixin, tf.TestFtpAuthentication
):
    pass


class TestTFtpDummyCmdsMProcMixin(MProcFTPTestMixin, tf.TestFtpDummyCmds):
    pass


class TestFtpCmdsSemanticMProcMixin(MProcFTPTestMixin, tf.TestFtpCmdsSemantic):
    pass


class TestFtpFsOperationsMProcMixin(MProcFTPTestMixin, tf.TestFtpFsOperations):

    def test_unforeseen_mdtm_event(self):
        pass


class TestFtpStoreDataMProcMixin(MProcFTPTestMixin, tf.TestFtpStoreData):
    pass


class TestFtpRetrieveDataMProcMixin(MProcFTPTestMixin, tf.TestFtpRetrieveData):
    pass


class TestFtpListingCmdsMProcMixin(MProcFTPTestMixin, tf.TestFtpListingCmds):
    pass


class TestFtpAbortMProcMixin(MProcFTPTestMixin, tf.TestFtpAbort):
    pass


# class TestTimeoutsMProcMixin(MProcFTPTestMixin, TestTimeouts):
#     def test_data_timeout_not_reached(self): pass
# class TestConfiOptsMProcMixin(MProcFTPTestMixin, TestConfigurableOptions):
#     pass
# class TestCallbacksMProcMixin(MProcFTPTestMixin, TestCallbacks): pass


class TestIPv4EnvironmentMProcMixin(MProcFTPTestMixin, tf.TestIPv4Environment):
    pass


class TestIPv6EnvironmentMProcMixin(MProcFTPTestMixin, tf.TestIPv6Environment):
    pass


class TestCornerCasesMProcMixin(MProcFTPTestMixin, tf.TestCornerCases):
    pass


# class TestFTPServerMProcMixin(MProcFTPTestMixin, TestFTPServer):
#     pass
