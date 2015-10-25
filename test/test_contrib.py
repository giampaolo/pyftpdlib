#!/usr/bin/env python

#  pyftpdlib is released under the MIT license, reproduced below:
#  ========================================================================
#  Copyright (C) 2007-2016 Giampaolo Rodola' <g.rodola@gmail.com>
#
#                         All Rights Reserved
#
# Permission is hereby granted, free of charge, to any person
# obtaining a copy of this software and associated documentation
# files (the "Software"), to deal in the Software without
# restriction, including without limitation the rights to use,
# copy, modify, merge, publish, distribute, sublicense, and/or sell
# copies of the Software, and to permit persons to whom the
# Software is furnished to do so, subject to the following
# conditions:
#
# The above copyright notice and this permission notice shall be
# included in all copies or substantial portions of the Software.
#
# THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND,
# EXPRESS OR IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES
# OF MERCHANTABILITY, FITNESS FOR A PARTICULAR PURPOSE AND
# NONINFRINGEMENT. IN NO EVENT SHALL THE AUTHORS OR COPYRIGHT
# HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER LIABILITY,
# WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING
# FROM, OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR
# OTHER DEALINGS IN THE SOFTWARE.
#
#  ========================================================================

"""
Tests for pyftpdlib.contrib namespace: handlers.py, authorizers.py,
filesystems.py and servers.py modules.
"""

import ftplib
import os
import sys

from pyftpdlib import handlers
from pyftpdlib import servers

from test_ftpd import *  # NOQA

if sys.version_info < (2, 7):
    import unittest2 as unittest  # pip install unittest2
else:
    import unittest

try:
    import pwd
except ImportError:
    pwd = None

try:
    import ssl
except ImportError:
    ssl = None


FTPS_SUPPORT = (hasattr(ftplib, 'FTP_TLS') and
                hasattr(handlers, 'TLS_FTPHandler'))
if sys.version_info < (2, 7):
    FTPS_UNSUPPORT_REASON = "requires python 2.7+"
elif ssl is None:
    FTPS_UNSUPPORT_REASON = "requires ssl module"
elif not hasattr(handlers, 'TLS_FTPHandler'):
    FTPS_UNSUPPORT_REASON = "requires PyOpenSSL module"
else:
    FTPS_UNSUPPORT_REASON = "FTPS test skipped"

CERTFILE = os.path.abspath(os.path.join(os.path.dirname(__file__),
                                        'keycert.pem'))
MPROCESS_SUPPORT = hasattr(servers, 'MultiprocessFTPServer')


# =====================================================================
# --- threaded FTP server mixin tests
# =====================================================================


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


# =====================================================================
# --- main
# =====================================================================


def test_main():
    verbosity = os.getenv('SILENT') and 1 or 2
    try:
        unittest.main(verbosity=verbosity)
    finally:
        cleanup()
        # force interpreter exit in case the FTP server thread is hanging
        # os._exit(0)

if __name__ == '__main__':
    test_main()
