#!/usr/bin/env python

# Copyright (C) 2007 Giampaolo Rodola' <g.rodola@gmail.com>.
# Use of this source code is governed by MIT license that can be
# found in the LICENSE file.

import contextlib
import ftplib
import os
import socket
import sys
import ssl

import OpenSSL  # requires "pip install pyopenssl"

from pyftpdlib.handlers import TLS_FTPHandler
from pyftpdlib.test import close_client
from pyftpdlib.test import configure_logging
from pyftpdlib.test import MProcessTestFTPd
from pyftpdlib.test import OSX
from pyftpdlib.test import PASSWD
from pyftpdlib.test import remove_test_files
from pyftpdlib.test import TIMEOUT
from pyftpdlib.test import TRAVIS
from pyftpdlib.test import unittest
from pyftpdlib.test import USER
from pyftpdlib.test import VERBOSITY
from pyftpdlib.test.test_functional import TestConfigurableOptions
from pyftpdlib.test.test_functional import TestCornerCases
from pyftpdlib.test.test_functional import TestFtpAbort
from pyftpdlib.test.test_functional import TestFtpAuthentication
from pyftpdlib.test.test_functional import TestFtpCmdsSemantic
from pyftpdlib.test.test_functional import TestFtpDummyCmds
from pyftpdlib.test.test_functional import TestFtpFsOperations
from pyftpdlib.test.test_functional import TestFtpListingCmds
from pyftpdlib.test.test_functional import TestFtpRetrieveData
from pyftpdlib.test.test_functional import TestFtpStoreData
from pyftpdlib.test.test_functional import TestIPv4Environment
from pyftpdlib.test.test_functional import TestIPv6Environment
from pyftpdlib.test.test_functional import TestTimeouts


FTPS_SUPPORT = hasattr(ftplib, 'FTP_TLS')
if sys.version_info < (2, 7):
    FTPS_UNSUPPORT_REASON = "requires python 2.7+"
else:
    FTPS_UNSUPPORT_REASON = "FTPS test skipped"

CERTFILE = os.path.abspath(os.path.join(os.path.dirname(__file__),
                                        'keycert.pem'))

del OpenSSL

# =====================================================================
# --- FTPS mixin tests
# =====================================================================

# What we're going to do here is repeat the original functional tests
# defined in test_functinal.py but by using FTPS.
# we secure both control and data connections before running any test.
# This is useful as we reuse the existent functional tests which are
# supposed to work no matter if the underlying protocol is FTP or FTPS.


if FTPS_SUPPORT:
    class FTPSClient(ftplib.FTP_TLS):
        """A modified version of ftplib.FTP_TLS class which implicitly
        secure the data connection after login().
        """

        def login(self, *args, **kwargs):
            ftplib.FTP_TLS.login(self, *args, **kwargs)
            self.prot_p()

    class FTPSServer(MProcessTestFTPd):
        """A threaded FTPS server used for functional testing."""
        handler = TLS_FTPHandler
        handler.certfile = CERTFILE

    class TLSTestMixin:
        server_class = FTPSServer
        client_class = FTPSClient
else:
    @unittest.skipIf(True, FTPS_UNSUPPORT_REASON)
    class TLSTestMixin:
        pass


class TestFtpAuthenticationTLSMixin(TLSTestMixin, TestFtpAuthentication):
    pass


class TestTFtpDummyCmdsTLSMixin(TLSTestMixin, TestFtpDummyCmds):
    pass


class TestFtpCmdsSemanticTLSMixin(TLSTestMixin, TestFtpCmdsSemantic):
    pass


class TestFtpFsOperationsTLSMixin(TLSTestMixin, TestFtpFsOperations):
    pass


class TestFtpStoreDataTLSMixin(TLSTestMixin, TestFtpStoreData):

    @unittest.skipIf(1, "fails with SSL")
    def test_stou(self):
        pass


# class TestSendFileTLSMixin(TLSTestMixin, TestSendfile):

#     def test_fallback(self):
#         self.client.prot_c()
#         super(TestSendFileTLSMixin, self).test_fallback()


class TestFtpRetrieveDataTLSMixin(TLSTestMixin, TestFtpRetrieveData):

    @unittest.skipIf(os.name == 'nt', "may fail on windows")
    def test_restore_on_retr(self):
        super(TestFtpRetrieveDataTLSMixin, self).test_restore_on_retr()


class TestFtpListingCmdsTLSMixin(TLSTestMixin, TestFtpListingCmds):

    # TODO: see https://travis-ci.org/giampaolo/pyftpdlib/jobs/87318445
    # Fails with:
    # File "/opt/python/2.7.9/lib/python2.7/ftplib.py", line 735, in retrlines
    #    conn.unwrap()
    # File "/opt/python/2.7.9/lib/python2.7/ssl.py", line 771, in unwrap
    #    s = self._sslobj.shutdown()
    # error: [Errno 0] Error
    @unittest.skipIf(TRAVIS or os.name == 'nt', "may fail on travis/windows")
    def test_nlst(self):
        super(TestFtpListingCmdsTLSMixin, self).test_nlst()


class TestFtpAbortTLSMixin(TLSTestMixin, TestFtpAbort):

    @unittest.skipIf(1, "fails with SSL")
    def test_oob_abor(self):
        pass


class TestTimeoutsTLSMixin(TLSTestMixin, TestTimeouts):

    @unittest.skipIf(1, "fails with SSL")
    def test_data_timeout_not_reached(self):
        pass


class TestConfigurableOptionsTLSMixin(TLSTestMixin, TestConfigurableOptions):
    pass


class TestIPv4EnvironmentTLSMixin(TLSTestMixin, TestIPv4Environment):
    pass


class TestIPv6EnvironmentTLSMixin(TLSTestMixin, TestIPv6Environment):
    pass


class TestCornerCasesTLSMixin(TLSTestMixin, TestCornerCases):
    pass


# =====================================================================
# dedicated FTPS tests
# =====================================================================


@unittest.skipUnless(FTPS_SUPPORT, FTPS_UNSUPPORT_REASON)
class TestFTPS(unittest.TestCase):
    """Specific tests fot TSL_FTPHandler class."""

    def _setup(self,
               tls_control_required=False,
               tls_data_required=False,
               ssl_protocol=ssl.PROTOCOL_SSLv23,
               ):
        self.server = FTPSServer()
        self.server.handler.tls_control_required = tls_control_required
        self.server.handler.tls_data_required = tls_data_required
        self.server.handler.ssl_protocol = ssl_protocol
        self.server.start()
        self.client = ftplib.FTP_TLS(timeout=TIMEOUT)
        self.client.connect(self.server.host, self.server.port)

    def setUp(self):
        self.client = None
        self.server = None

    def tearDown(self):
        if self.client is not None:
            self.client.ssl_version = ssl.PROTOCOL_SSLv23
            close_client(self.client)
        if self.server is not None:
            self.server.handler.ssl_protocol = ssl.PROTOCOL_SSLv23
            self.server.handler.tls_control_required = False
            self.server.handler.tls_data_required = False
            self.server.stop()

    def assertRaisesWithMsg(self, excClass, msg, callableObj, *args, **kwargs):
        try:
            callableObj(*args, **kwargs)
        except excClass as err:
            if str(err) == msg:
                return
            raise self.failureException("%s != %s" % (str(err), msg))
        else:
            if hasattr(excClass, '__name__'):
                excName = excClass.__name__
            else:
                excName = str(excClass)
            raise self.failureException("%s not raised" % excName)

    def test_auth(self):
        # unsecured
        self._setup()
        self.client.login(secure=False)
        self.assertFalse(isinstance(self.client.sock, ssl.SSLSocket))
        # secured
        self.client.login()
        self.assertTrue(isinstance(self.client.sock, ssl.SSLSocket))
        # AUTH issued twice
        msg = '503 Already using TLS.'
        self.assertRaisesWithMsg(ftplib.error_perm, msg,
                                 self.client.sendcmd, 'auth tls')

    def test_pbsz(self):
        # unsecured
        self._setup()
        self.client.login(secure=False)
        msg = "503 PBSZ not allowed on insecure control connection."
        self.assertRaisesWithMsg(ftplib.error_perm, msg,
                                 self.client.sendcmd, 'pbsz 0')
        # secured
        self.client.login(secure=True)
        resp = self.client.sendcmd('pbsz 0')
        self.assertEqual(resp, "200 PBSZ=0 successful.")

    def test_prot(self):
        self._setup()
        self.client.login(secure=False)
        msg = "503 PROT not allowed on insecure control connection."
        self.assertRaisesWithMsg(ftplib.error_perm, msg,
                                 self.client.sendcmd, 'prot p')
        self.client.login(secure=True)
        # secured
        self.client.prot_p()
        sock = self.client.transfercmd('list')
        with contextlib.closing(sock):
            while True:
                if not sock.recv(1024):
                    self.client.voidresp()
                    break
            self.assertTrue(isinstance(sock, ssl.SSLSocket))
            # unsecured
            self.client.prot_c()
        sock = self.client.transfercmd('list')
        with contextlib.closing(sock):
            while True:
                if not sock.recv(1024):
                    self.client.voidresp()
                    break
            self.assertFalse(isinstance(sock, ssl.SSLSocket))

    def test_feat(self):
        self._setup()
        feat = self.client.sendcmd('feat')
        cmds = ['AUTH TLS', 'AUTH SSL', 'PBSZ', 'PROT']
        for cmd in cmds:
            self.assertTrue(cmd in feat)

    def test_unforseen_ssl_shutdown(self):
        self._setup()
        self.client.login()
        try:
            sock = self.client.sock.unwrap()
        except socket.error as err:
            if err.errno == 0:
                return
            raise
        sock.settimeout(TIMEOUT)
        sock.sendall(b'noop')
        try:
            chunk = sock.recv(1024)
        except socket.error:
            pass
        else:
            self.assertEqual(chunk, b"")

    def test_tls_control_required(self):
        self._setup(tls_control_required=True)
        msg = "550 SSL/TLS required on the control channel."
        self.assertRaisesWithMsg(ftplib.error_perm, msg,
                                 self.client.sendcmd, "user " + USER)
        self.assertRaisesWithMsg(ftplib.error_perm, msg,
                                 self.client.sendcmd, "pass " + PASSWD)
        self.client.login(secure=True)

    def test_tls_data_required(self):
        self._setup(tls_data_required=True)
        self.client.login(secure=True)
        msg = "550 SSL/TLS required on the data channel."
        self.assertRaisesWithMsg(ftplib.error_perm, msg,
                                 self.client.retrlines, 'list', lambda x: x)
        self.client.prot_p()
        self.client.retrlines('list', lambda x: x)

    def try_protocol_combo(self, server_protocol, client_protocol):
        self._setup(ssl_protocol=server_protocol)
        self.client.ssl_version = client_protocol
        close_client(self.client)
        self.client.connect(self.server.host, self.server.port)
        try:
            self.client.login()
        except (ssl.SSLError, socket.error):
            self.client.close()
        else:
            self.client.quit()

    # def test_ssl_version(self):
    #     protos = [ssl.PROTOCOL_SSLv3, ssl.PROTOCOL_SSLv23,
    #               ssl.PROTOCOL_TLSv1]
    #     if hasattr(ssl, "PROTOCOL_SSLv2"):
    #         protos.append(ssl.PROTOCOL_SSLv2)
    #         for proto in protos:
    #             self.try_protocol_combo(ssl.PROTOCOL_SSLv2, proto)
    #     for proto in protos:
    #         self.try_protocol_combo(ssl.PROTOCOL_SSLv3, proto)
    #     for proto in protos:
    #         self.try_protocol_combo(ssl.PROTOCOL_SSLv23, proto)
    #     for proto in protos:
    #         self.try_protocol_combo(ssl.PROTOCOL_TLSv1, proto)

    if hasattr(ssl, "PROTOCOL_SSLv2"):
        def test_sslv2(self):
            self.client.ssl_version = ssl.PROTOCOL_SSLv2
            close_client(self.client)
            if not OSX:
                with self.server.lock:
                    self.client.connect(self.server.host, self.server.port)
                self.assertRaises(socket.error, self.client.login)
            else:
                with self.server.lock:
                    with self.assertRaises(socket.error):
                        self.client.connect(self.server.host, self.server.port,
                                            timeout=0.1)
            self.client.ssl_version = ssl.PROTOCOL_SSLv2


configure_logging()
remove_test_files()


if __name__ == '__main__':
    unittest.main(verbosity=VERBOSITY)
