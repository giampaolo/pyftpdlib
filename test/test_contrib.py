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

    class TestTls(unittest.TestCase):

        def setUp(self):
            self.server = FTPSServer()
            self.server.start()
            self.client = ftplib.FTP_TLS()
            self.client.connect(self.server.host, self.server.port)
            self.client.sock.settimeout(2)

        def tearDown(self):
            self.client.close()
            self.server.stop()


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
                      TestTls,
                 ]
        if SUPPORTS_IPV4:
            ftps_tests.append(TestIPv4EnvironmentTLSMixin)
        if SUPPORTS_IPV6:
            ftps_tests.append(TestIPv6EnvironmentTLSMixin)
        tests += ftps_tests

    for test in tests:
        test_suite.addTest(unittest.makeSuite(test))
    safe_remove(TESTFN)
    unittest.TextTestRunner(verbosity=2).run(test_suite)
    safe_remove(TESTFN)


if __name__ == '__main__':
    test_main()
