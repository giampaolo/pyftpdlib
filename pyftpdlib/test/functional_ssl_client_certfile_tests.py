#!/usr/bin/env python

# Copyright (C) 2007-2016 Giampaolo Rodola' <g.rodola@gmail.com>.
# Use of this source code is governed by MIT license that can be
# found in the LICENSE file.
#
#
# Does not follow naming convention of other tests because this
# CANNOT be run in the same test suite with test_functional_ssl.
# The test parallelism causes SSL errors when there should be none
# Please run these tests separately

import ftplib
import os
import sys

import OpenSSL  # requires "pip install pyopenssl"

from pyftpdlib.handlers import TLS_FTPHandler
from pyftpdlib.test import configure_logging
from pyftpdlib.test import remove_test_files
from pyftpdlib.test import ThreadedTestFTPd
from pyftpdlib.test import TIMEOUT
from pyftpdlib.test import unittest
from pyftpdlib.test import VERBOSITY
from _ssl import SSLError


FTPS_SUPPORT = hasattr(ftplib, 'FTP_TLS')
if sys.version_info < (2, 7):
    FTPS_UNSUPPORT_REASON = "requires python 2.7+"
else:
    FTPS_UNSUPPORT_REASON = "FTPS test skipped"

CERTFILE = os.path.abspath(os.path.join(os.path.dirname(__file__),
                                        'keycert.pem'))
CLIENT_CERTFILE = os.path.abspath(os.path.join(os.path.dirname(__file__),
                                               'clientcert.pem'))

del OpenSSL


if FTPS_SUPPORT:
    class FTPSClient(ftplib.FTP_TLS):
        """A modified version of ftplib.FTP_TLS class which implicitly
        secure the data connection after login().
        """

        def login(self, *args, **kwargs):
            ftplib.FTP_TLS.login(self, *args, **kwargs)
            self.prot_p()

    class FTPSServerAuth(ThreadedTestFTPd):
        """A threaded FTPS server that forces client certificate
        authentication used for functional testing.
        """
        handler = TLS_FTPHandler
        handler.certfile = CERTFILE
        handler.client_certfile = CLIENT_CERTFILE


# =====================================================================
# dedicated FTPS tests with client authentication
# =====================================================================


@unittest.skipUnless(FTPS_SUPPORT, FTPS_UNSUPPORT_REASON)
class TestFTPS(unittest.TestCase):
    """Specific tests for TLS_FTPHandler class."""

    def setUp(self):
        self.server = FTPSServerAuth()
        self.server.start()

    def tearDown(self):
        self.client.close()
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

    def test_auth_client_cert(self):
        self.client = ftplib.FTP_TLS(timeout=TIMEOUT, certfile=CLIENT_CERTFILE)
        self.client.connect(self.server.host, self.server.port)
        # secured
        try:
            self.client.login()
        except Exception:
            self.fail("login with certificate should work")

    def test_auth_client_nocert(self):
        self.client = ftplib.FTP_TLS(timeout=TIMEOUT)
        self.client.connect(self.server.host, self.server.port)
        try:
            self.client.login()
        except SSLError as e:
            # client should not be able to log in
            if "SSLV3_ALERT_HANDSHAKE_FAILURE" in e.reason:
                pass
            else:
                self.fail("Incorrect SSL error with" +
                          " missing client certificate")
        else:
            self.fail("Client able to log in with no certificate")

    def test_auth_client_badcert(self):
        self.client = ftplib.FTP_TLS(timeout=TIMEOUT, certfile=CERTFILE)
        self.client.connect(self.server.host, self.server.port)
        try:
            self.client.login()
        except Exception as e:
            # client should not be able to log in
            if "TLSV1_ALERT_UNKNOWN_CA" in e.reason:
                pass
            else:
                self.fail("Incorrect SSL error with bad client certificate")
        else:
            self.fail("Client able to log in with bad certificate")


configure_logging()
remove_test_files()


if __name__ == '__main__':
    unittest.main(verbosity=VERBOSITY)
