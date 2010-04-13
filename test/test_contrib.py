#!/usr/bin/env python
# test_contrib.py

import ftplib
import unittest

from test_ftpd import *


# --- FTPS tests

if not hasattr(ftplib, 'FTP_TLS'):  # Added in Python 2.7
    TEST_FTPS = False
else:
    TEST_FTPS = True

    import ssl
    from pyftpdlib.contrib.handlers import TLS_FTPHandler

    class FTPSClient(ftplib.FTP_TLS):
        """A modified version of ftplib.FTP_TLS class which implicitly
        secure the data connection after login().
        """
        def login(self, *args, **kwargs):
            ftplib.FTP_TLS.login(self, *args, **kwargs)
            self.prot_p()

    class FTPSServer(FTPd):
        """A threaded FTPS server used for functional testing."""
        handler = TLS_FTPHandler

    # --- FTPS mixin tests
    # What we're going to do here is repeating the original tests
    # defined in test_ftpd.py but securing both control and data
    # connections first.
    # The tests are exactly the same, the only difference is that
    # different classes are used (TLS_FPTHandler for the server
    # and ftplib.FTP_TLS for the client) and everything goes through
    # FTPS instead of clear-text FTP.
    # This is very useful as we entirely reuse the existent test code
    # base which is very large (more than 100 tests) and covers a lot
    # of cases which are supposed to work no matter if the protocol
    # is FTP or FTPS.

    class TLSTestMixin:
        server_class = FTPSServer
        client_class = FTPSClient

    class TestFtpAuthenticationTLSMixin(TLSTestMixin, TestFtpAuthentication): pass
    class TestTFtpDummyCmdsTLSMixin(TLSTestMixin, TestFtpDummyCmds): pass
    class TestFtpCmdsSemanticTLSMixin(TLSTestMixin, TestFtpCmdsSemantic): pass
    class TestFtpFsOperationsTLSMixin(TLSTestMixin, TestFtpFsOperations): pass
    class TestFtpStoreDataTLSMixin(TLSTestMixin, TestFtpStoreData):
        def test_stou(self): pass

    class TestFtpRetrieveDataTLSMixin(TLSTestMixin, TestFtpRetrieveData): pass
    class TestFtpListingCmdsTLSMixin(TLSTestMixin, TestFtpListingCmds): pass
    class TestFtpAbortTLSMixin(TLSTestMixin, TestFtpAbort):
        def test_oob_abor(self): pass

    class TestThrottleBandwidthTLSMixin(TLSTestMixin, ThrottleBandwidth):
        def test_throttle_recv(self): pass
        def test_throttle_send(self): pass

    class TestTimeoutsTLSMixin(TLSTestMixin, TestTimeouts):
        def test_data_timeout_not_reached(self): pass

    class TestConfigurableOptionsTLSMixin(TLSTestMixin, TestConfigurableOptions): pass
    class TestCallbacksTLSMixin(TLSTestMixin, TestCallbacks):
        def test_on_file_received(self): pass
        def test_on_file_sent(self): pass

    class TestIPv4EnvironmentTLSMixin(TLSTestMixin, TestIPv4Environment): pass
    class TestIPv6EnvironmentTLSMixin(TLSTestMixin, TestIPv6Environment): pass
    class TestCornerCasesTLSMixin(TLSTestMixin, TestCornerCases): pass

    # --- Specific FTPS tests

    class TestFTPS(unittest.TestCase):

        def setUp(self):
            self.server = FTPSServer()
            self.server.start()
            self.client = ftplib.FTP_TLS()
            self.client.connect(self.server.host, self.server.port)
            self.client.sock.settimeout(2)

        def tearDown(self):
            self.client.ssl_version = ssl.PROTOCOL_SSLv23
            self.server.handler.ssl_version = ssl.PROTOCOL_SSLv23
            self.server.handler.tls_control_required = False
            self.server.handler.tls_data_required = False
            self.client.close()
            self.server.stop()

        def assertRaisesWithMsg(self, excClass, msg, callableObj, *args, **kwargs):
            try:
                callableObj(*args, **kwargs)
            except excClass, why:
                if str(why) == msg:
                    return
                raise self.failureException("%s != %s" %(str(why), msg))
            else:
                if hasattr(excClass,'__name__'):
                    excName = excClass.__name__
                else:
                    excName = str(excClass)
                raise self.failureException, "%s not raised" % excName

        def test_auth(self):
            # unsecured
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
            self.client.login(secure=False)
            msg = "503 PBSZ not allowed on insecure control connection."
            self.assertRaisesWithMsg(ftplib.error_perm, msg,
                                     self.client.sendcmd, 'pbsz 0')
            # secured
            self.client.login(secure=True)
            resp = self.client.sendcmd('pbsz 0')
            self.assertEqual(resp, "200 PBSZ=0 successful.")

        def test_prot(self):
            self.client.login(secure=False)
            msg = "503 PROT not allowed on insecure control connection."
            self.assertRaisesWithMsg(ftplib.error_perm, msg,
                                     self.client.sendcmd, 'prot p')
            self.client.login(secure=True)
            # secured
            self.client.prot_p()
            sock = self.client.transfercmd('list')
            while 1:
                if not sock.recv(1024):
                    self.client.voidresp()
                    break
            self.assertTrue(isinstance(sock, ssl.SSLSocket))
            # unsecured
            self.client.prot_c()
            sock = self.client.transfercmd('list')
            while 1:
                if not sock.recv(1024):
                    self.client.voidresp()
                    break
            self.assertFalse(isinstance(sock, ssl.SSLSocket))

        def test_feat(self):
            feat = self.client.sendcmd('feat')
            cmds = ['AUTH TLS', 'AUTH SSL', 'PBSZ', 'PROT']
            for cmd in cmds:
                self.assertTrue(cmd in feat)

        def test_unforseen_ssl_shutdown(self):
            self.client.login()
            sock = self.client.sock.unwrap()
            sock.sendall('noop')
            self.assertRaises(socket.error, sock.recv, 1024)

        def test_tls_control_required(self):
            self.server.handler.tls_control_required = True
            msg = "550 SSL/TLS required on the control channel."
            self.assertRaisesWithMsg(ftplib.error_perm, msg,
                                     self.client.sendcmd, "user " + USER)
            self.assertRaisesWithMsg(ftplib.error_perm, msg,
                                     self.client.sendcmd, "pass " + PASSWD)
            self.client.login(secure=True)

##        def test_tls_data_required(self):
##            self.server.handler.tls_data_required = True
##            self.client.login(secure=True)
##            msg = "550 SSL/TLS required on the data channel."
##            self.assertRaisesWithMsg(ftplib.error_perm, msg,
##                                    self.client.retrlines, 'list', lambda x: x)
##            print self.client.prot_p()
##            self.client.retrlines('list', lambda x: x)


def test_main():
    test_suite = unittest.TestSuite()
    tests = []
    # FTPS tests
    if TEST_FTPS:
        ftps_tests = [TestFtpAuthenticationTLSMixin,
                      TestTFtpDummyCmdsTLSMixin,
                      TestFtpCmdsSemanticTLSMixin,
                      TestFtpFsOperationsTLSMixin,
                      TestFtpStoreDataTLSMixin,
                      TestFtpRetrieveDataTLSMixin,
                      TestFtpListingCmdsTLSMixin,
                      TestFtpAbortTLSMixin,
                      TestThrottleBandwidthTLSMixin,
                      TestTimeoutsTLSMixin,
                      TestConfigurableOptionsTLSMixin,
                      TestCallbacksTLSMixin,
                      TestCornerCasesTLSMixin,
                      TestFTPS,
                 ]
        if SUPPORTS_IPV4:
            ftps_tests.append(TestIPv4EnvironmentTLSMixin)
        if SUPPORTS_IPV6:
            ftps_tests.append(TestIPv6EnvironmentTLSMixin)
        tests += ftps_tests

##    tests = [TestFTPS]

    for test in tests:
        test_suite.addTest(unittest.makeSuite(test))
    safe_remove(TESTFN)
    unittest.TextTestRunner(verbosity=2).run(test_suite)
    safe_remove(TESTFN)


if __name__ == '__main__':
    test_main()
