#!/usr/bin/env python

# Copyright (C) 2007-2016 Giampaolo Rodola' <g.rodola@gmail.com>.
# Use of this source code is governed by MIT license that can be
# found in the LICENSE file.

import contextlib
import ftplib
import socket

from pyftpdlib import servers
from test_functional import TestCallbacks
from test_functional import TestCornerCases
from test_functional import TestFtpAbort
from test_functional import TestFtpAuthentication
from test_functional import TestFtpCmdsSemantic
from test_functional import TestFtpDummyCmds
from test_functional import TestFtpFsOperations
from test_functional import TestFtpListingCmds
from test_functional import TestFtpRetrieveData
from test_functional import TestFtpStoreData
from test_functional import TestIPv4Environment
from test_functional import TestIPv6Environment
from testutils import configure_logging
from testutils import FTPd
from testutils import HOST
from testutils import PASSWD
from testutils import remove_test_files
from testutils import TIMEOUT
from testutils import unittest
from testutils import USER
from testutils import VERBOSITY


MPROCESS_SUPPORT = hasattr(servers, 'MultiprocessFTPServer')


class TestFTPServer(unittest.TestCase):
    """Tests for *FTPServer classes."""
    server_class = FTPd
    client_class = ftplib.FTP

    def setUp(self):
        self.server = None
        self.client = None

    def tearDown(self):
        if self.client is not None:
            self.client.close()
        if self.server is not None:
            self.server.stop()

    def test_sock_instead_of_addr(self):
        # pass a socket object instead of an address tuple to FTPServer
        # constructor
        with contextlib.closing(socket.socket()) as sock:
            sock.bind((HOST, 0))
            sock.listen(5)
            ip, port = sock.getsockname()[:2]
            self.server = self.server_class(sock)
            self.server.start()
            self.client = self.client_class()
            self.client.connect(ip, port)
            self.client.sock.settimeout(TIMEOUT)
            self.client.login(USER, PASSWD)


# =====================================================================
# --- threaded FTP server mixin tests
# =====================================================================

# What we're going to do here is repeat the original functional tests
# defined in test_functinal.py but by using different concurrency
# modules (multi thread and multi process instead of async.
# This is useful as we reuse the existent functional tests which are
# supposed to work no matter what the concurrency model is.


class TFTPd(FTPd):
    server_class = servers.ThreadedFTPServer


class ThreadFTPTestMixin:
    server_class = TFTPd


class TestFtpAuthenticationThreadMixin(ThreadFTPTestMixin,
                                       TestFtpAuthentication):
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


class TestCallbacksThreadMixin(ThreadFTPTestMixin, TestCallbacks):
    pass


class TestIPv4EnvironmentThreadMixin(ThreadFTPTestMixin, TestIPv4Environment):
    pass


class TestIPv6EnvironmentThreadMixin(ThreadFTPTestMixin, TestIPv6Environment):
    pass


class TestCornerCasesThreadMixin(ThreadFTPTestMixin, TestCornerCases):
    pass


class TestFTPServerThreadMixin(ThreadFTPTestMixin, TestFTPServer):
    pass


# =====================================================================
# --- multiprocess FTP server mixin tests
# =====================================================================

if MPROCESS_SUPPORT:
    class MultiProcFTPd(FTPd):
        server_class = servers.MultiprocessFTPServer

    class MProcFTPTestMixin:
        server_class = MultiProcFTPd
else:
    @unittest.skipIf(True, "multiprocessing module not installed")
    class MProcFTPTestMixin:
        pass


class TestFtpAuthenticationMProcMixin(MProcFTPTestMixin,
                                      TestFtpAuthentication):
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


class TestFTPServerMProcMixin(MProcFTPTestMixin, TestFTPServer):
    pass


configure_logging()
remove_test_files()


if __name__ == '__main__':
    unittest.main(verbosity=VERBOSITY)
