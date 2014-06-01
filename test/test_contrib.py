#!/usr/bin/env python

#  pyftpdlib is released under the MIT license, reproduced below:
#  ========================================================================
#  Copyright (C) 2007-2014 Giampaolo Rodola' <g.rodola@gmail.com>
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
import random
import string
import sys
import warnings

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

try:
    from pywintypes import error as Win32ExtError
except ImportError:
    pass

from pyftpdlib.authorizers import AuthenticationFailed, AuthorizerError
from pyftpdlib import authorizers
from pyftpdlib import handlers
from pyftpdlib import filesystems
from pyftpdlib import servers
from pyftpdlib._compat import b, getcwdu, unicode
from test_ftpd import *  # NOQA


FTPS_SUPPORT = (hasattr(ftplib, 'FTP_TLS') and
                hasattr(handlers, 'TLS_FTPHandler'))
if not FTPS_SUPPORT:
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
# --- Mixin tests
# =====================================================================

# What we're going to do here is repeat the original functional tests
# defined in test_ftpd.py but by using different FTP server
# configurations.
#
# In case of FTPS we secure both control and data connections before
# running any test.
# Same story for ThreadedFTPServer which will be used instead of
# base FTPServer class.
#
# This is useful as we reuse the existent functional tests which are
# supposed to work no matter if the underlying protocol is FTP or FTPS,
# or if the concurrency module used is asynchronous or based on
# multiple threads or processes (fork).

# =====================================================================
# --- FTPS mixin tests
# =====================================================================

if FTPS_SUPPORT:
    class FTPSClient(ftplib.FTP_TLS):
        """A modified version of ftplib.FTP_TLS class which implicitly
        secure the data connection after login().
        """

        def login(self, *args, **kwargs):
            ftplib.FTP_TLS.login(self, *args, **kwargs)
            self.prot_p()

    class FTPSServer(FTPd):
        """A threaded FTPS server used for functional testing."""
        handler = handlers.TLS_FTPHandler
        handler.certfile = CERTFILE

    class TLSTestMixin:
        server_class = FTPSServer
        client_class = FTPSClient
else:
    class TLSTestMixin:

        def setUp(self):
            self.skipTest(FTPS_UNSUPPORT_REASON)


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


class TestFtpRetrieveDataTLSMixin(TLSTestMixin, TestFtpRetrieveData):
    pass


class TestFtpListingCmdsTLSMixin(TLSTestMixin, TestFtpListingCmds):
    pass


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


class TestCallbacksTLSMixin(TLSTestMixin, TestCallbacks):

    def test_on_file_received(self):
        pass

    def test_on_file_sent(self):
        pass

    def test_on_incomplete_file_received(self):
        pass

    def test_on_incomplete_file_sent(self):
        pass

    def test_on_connect(self):
        pass

    def test_on_disconnect(self):
        pass

    def test_on_login(self):
        pass

    def test_on_login_failed(self):
        pass

    def test_on_logout_quit(self):
        pass

    def test_on_logout_rein(self):
        pass

    def test_on_logout_user_issued_twice(self):
        pass


class TestIPv4EnvironmentTLSMixin(TLSTestMixin, TestIPv4Environment):
    pass


class TestIPv6EnvironmentTLSMixin(TLSTestMixin, TestIPv6Environment):
    pass


class TestCornerCasesTLSMixin(TLSTestMixin, TestCornerCases):
    pass

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
    class MProcFTPTestMixin:

        def setUp(self):
            self.skipTest("multiprocessing module not installed")


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
# dedicated FTPs tests
# =====================================================================


class TestFTPS(unittest.TestCase):
    """Specific tests fot TSL_FTPHandler class."""

    def setUp(self):
        if not FTPS_SUPPORT:
            self.skipTest(FTPS_UNSUPPORT_REASON)
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
        except excClass:
            why = sys.exc_info()[1]
            if str(why) == msg:
                return
            raise self.failureException("%s != %s" % (str(why), msg))
        else:
            if hasattr(excClass, '__name__'):
                excName = excClass.__name__
            else:
                excName = str(excClass)
            raise self.failureException("%s not raised" % excName)

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
        try:
            sock.settimeout(TIMEOUT)
            while 1:
                if not sock.recv(1024):
                    self.client.voidresp()
                    break
            self.assertTrue(isinstance(sock, ssl.SSLSocket))
            # unsecured
            self.client.prot_c()
        finally:
            sock.close()
        sock = self.client.transfercmd('list')
        try:
            sock.settimeout(TIMEOUT)
            while 1:
                if not sock.recv(1024):
                    self.client.voidresp()
                    break
            self.assertFalse(isinstance(sock, ssl.SSLSocket))
        finally:
            sock.close()

    def test_feat(self):
        feat = self.client.sendcmd('feat')
        cmds = ['AUTH TLS', 'AUTH SSL', 'PBSZ', 'PROT']
        for cmd in cmds:
            self.assertTrue(cmd in feat)

    def test_unforseen_ssl_shutdown(self):
        self.client.login()
        try:
            sock = self.client.sock.unwrap()
        except socket.error:
            err = sys.exc_info()[1]
            if err.errno == 0:
                return
            raise
        sock.settimeout(TIMEOUT)
        sock.sendall(b('noop'))
        try:
            chunk = sock.recv(1024)
        except socket.error:
            pass
        else:
            self.assertEqual(chunk, b(""))

    def test_tls_control_required(self):
        self.server.handler.tls_control_required = True
        msg = "550 SSL/TLS required on the control channel."
        self.assertRaisesWithMsg(ftplib.error_perm, msg,
                                 self.client.sendcmd, "user " + USER)
        self.assertRaisesWithMsg(ftplib.error_perm, msg,
                                 self.client.sendcmd, "pass " + PASSWD)
        self.client.login(secure=True)

    def test_tls_data_required(self):
        self.server.handler.tls_data_required = True
        self.client.login(secure=True)
        msg = "550 SSL/TLS required on the data channel."
        self.assertRaisesWithMsg(ftplib.error_perm, msg,
                                 self.client.retrlines, 'list', lambda x: x)
        self.client.prot_p()
        self.client.retrlines('list', lambda x: x)

    def try_protocol_combo(self, server_protocol, client_protocol):
        self.server.handler.ssl_version = server_protocol
        self.client.ssl_version = client_protocol
        self.client.close()
        self.client.connect(self.server.host, self.server.port)
        try:
            self.client.login()
        except (ssl.SSLError, socket.error):
            self.client.close()
        else:
            self.client.quit()

    def test_ssl_version(self):
        protos = [ssl.PROTOCOL_SSLv3, ssl.PROTOCOL_SSLv23, ssl.PROTOCOL_TLSv1]
        if hasattr(ssl, "PROTOCOL_SSLv2"):
            protos.append(ssl.PROTOCOL_SSLv2)
            for proto in protos:
                self.try_protocol_combo(ssl.PROTOCOL_SSLv2, proto)
        for proto in protos:
            self.try_protocol_combo(ssl.PROTOCOL_SSLv3, proto)
        for proto in protos:
            self.try_protocol_combo(ssl.PROTOCOL_SSLv23, proto)
        for proto in protos:
            self.try_protocol_combo(ssl.PROTOCOL_TLSv1, proto)

    if hasattr(ssl, "PROTOCOL_SSLv2"):
        def test_sslv2(self):
            self.client.ssl_version = ssl.PROTOCOL_SSLv2
            self.client.close()
            self.client.connect(self.server.host, self.server.port)
            self.assertRaises(socket.error, self.client.login)
            self.client.ssl_version = ssl.PROTOCOL_SSLv2


# =====================================================================
# --- authorizer
# =====================================================================


class _SharedAuthorizerTests(object):
    """Tests valid for both UnixAuthorizer and WindowsAuthorizer for
    those parts which share the same API.
    """
    authorizer_class = None
    # --- utils

    def get_users(self):
        return self.authorizer_class._get_system_users()

    def get_current_user(self):
        if os.name == 'posix':
            return pwd.getpwuid(os.getuid()).pw_name
        else:
            return os.environ['USERNAME']

    def get_current_user_homedir(self):
        if os.name == 'posix':
            return pwd.getpwuid(os.getuid()).pw_dir
        else:
            return os.environ['USERPROFILE']

    def get_nonexistent_user(self):
        # return a user which does not exist on the system
        users = self.get_users()
        letters = string.ascii_lowercase
        while 1:
            user = ''.join([random.choice(letters) for i in range(10)])
            if user not in users:
                return user

    def assertRaisesWithMsg(self, excClass, msg, callableObj, *args, **kwargs):
        try:
            callableObj(*args, **kwargs)
        except excClass:
            why = sys.exc_info()[1]
            if str(why) == msg:
                return
            raise self.failureException("%s != %s" % (str(why), msg))
        else:
            if hasattr(excClass, '__name__'):
                excName = excClass.__name__
            else:
                excName = str(excClass)
            raise self.failureException("%s not raised" % excName)
    # --- /utils

    def test_get_home_dir(self):
        auth = self.authorizer_class()
        home = auth.get_home_dir(self.get_current_user())
        self.assertTrue(isinstance(home, unicode))
        nonexistent_user = self.get_nonexistent_user()
        self.assertTrue(os.path.isdir(home))
        if auth.has_user('nobody'):
            home = auth.get_home_dir('nobody')
        self.assertRaises(AuthorizerError,
                          auth.get_home_dir, nonexistent_user)

    def test_has_user(self):
        auth = self.authorizer_class()
        current_user = self.get_current_user()
        nonexistent_user = self.get_nonexistent_user()
        self.assertTrue(auth.has_user(current_user))
        self.assertFalse(auth.has_user(nonexistent_user))
        auth = self.authorizer_class(rejected_users=[current_user])
        self.assertFalse(auth.has_user(current_user))

    def test_validate_authentication(self):
        # can't test for actual success in case of valid authentication
        # here as we don't have the user password
        if self.authorizer_class.__name__ == 'UnixAuthorizer':
            auth = self.authorizer_class(require_valid_shell=False)
        else:
            auth = self.authorizer_class()
        current_user = self.get_current_user()
        nonexistent_user = self.get_nonexistent_user()
        self.assertRaises(
            AuthenticationFailed,
            auth.validate_authentication, current_user, 'wrongpasswd', None)
        self.assertRaises(
            AuthenticationFailed,
            auth.validate_authentication, nonexistent_user, 'bar', None)

    def test_impersonate_user(self):
        auth = self.authorizer_class()
        nonexistent_user = self.get_nonexistent_user()
        try:
            if self.authorizer_class.__name__ == 'UnixAuthorizer':
                auth.impersonate_user(self.get_current_user(), '')
                self.assertRaises(
                    AuthorizerError,
                    auth.impersonate_user, nonexistent_user, 'pwd')
            else:
                self.assertRaises(
                    Win32ExtError,
                    auth.impersonate_user, nonexistent_user, 'pwd')
                self.assertRaises(
                    Win32ExtError,
                    auth.impersonate_user, self.get_current_user(), '')
        finally:
            auth.terminate_impersonation('')

    def test_terminate_impersonation(self):
        auth = self.authorizer_class()
        auth.terminate_impersonation('')
        auth.terminate_impersonation('')

    def test_get_perms(self):
        auth = self.authorizer_class(global_perm='elr')
        self.assertTrue('r' in auth.get_perms(self.get_current_user()))
        self.assertFalse('w' in auth.get_perms(self.get_current_user()))

    def test_has_perm(self):
        auth = self.authorizer_class(global_perm='elr')
        self.assertTrue(auth.has_perm(self.get_current_user(), 'r'))
        self.assertFalse(auth.has_perm(self.get_current_user(), 'w'))

    def test_messages(self):
        auth = self.authorizer_class(msg_login="login", msg_quit="quit")
        self.assertTrue(auth.get_msg_login, "login")
        self.assertTrue(auth.get_msg_quit, "quit")

    def test_error_options(self):
        wrong_user = self.get_nonexistent_user()
        self.assertRaisesWithMsg(
            AuthorizerError,
            "rejected_users and allowed_users options are mutually exclusive",
            self.authorizer_class, allowed_users=['foo'],
            rejected_users=['bar'])
        self.assertRaisesWithMsg(
            AuthorizerError,
            'invalid username "anonymous"',
            self.authorizer_class, allowed_users=['anonymous'])
        self.assertRaisesWithMsg(
            AuthorizerError,
            'invalid username "anonymous"',
            self.authorizer_class, rejected_users=['anonymous'])
        self.assertRaisesWithMsg(
            AuthorizerError,
            'unknown user %s' % wrong_user,
            self.authorizer_class, allowed_users=[wrong_user])
        self.assertRaisesWithMsg(AuthorizerError,
                                 'unknown user %s' % wrong_user,
                                 self.authorizer_class,
                                 rejected_users=[wrong_user])

    def test_override_user_password(self):
        auth = self.authorizer_class()
        user = self.get_current_user()
        auth.override_user(user, password='foo')
        auth.validate_authentication(user, 'foo', None)
        self.assertRaises(AuthenticationFailed(auth.validate_authentication,
                                               user, 'bar', None))
        # make sure other settings keep using default values
        self.assertEqual(auth.get_home_dir(user),
                         self.get_current_user_homedir())
        self.assertEqual(auth.get_perms(user), "elradfmw")
        self.assertEqual(auth.get_msg_login(user), "Login successful.")
        self.assertEqual(auth.get_msg_quit(user), "Goodbye.")

    def test_override_user_homedir(self):
        auth = self.authorizer_class()
        user = self.get_current_user()
        dir = os.path.dirname(getcwdu())
        auth.override_user(user, homedir=dir)
        self.assertEqual(auth.get_home_dir(user), dir)
        # make sure other settings keep using default values
        # self.assertEqual(auth.get_home_dir(user),
        #                  self.get_current_user_homedir())
        self.assertEqual(auth.get_perms(user), "elradfmw")
        self.assertEqual(auth.get_msg_login(user), "Login successful.")
        self.assertEqual(auth.get_msg_quit(user), "Goodbye.")

    def test_override_user_perm(self):
        auth = self.authorizer_class()
        user = self.get_current_user()
        auth.override_user(user, perm="elr")
        self.assertEqual(auth.get_perms(user), "elr")
        # make sure other settings keep using default values
        self.assertEqual(auth.get_home_dir(user),
                         self.get_current_user_homedir())
        # self.assertEqual(auth.get_perms(user), "elradfmw")
        self.assertEqual(auth.get_msg_login(user), "Login successful.")
        self.assertEqual(auth.get_msg_quit(user), "Goodbye.")

    def test_override_user_msg_login_quit(self):
        auth = self.authorizer_class()
        user = self.get_current_user()
        auth.override_user(user, msg_login="foo", msg_quit="bar")
        self.assertEqual(auth.get_msg_login(user), "foo")
        self.assertEqual(auth.get_msg_quit(user), "bar")
        # make sure other settings keep using default values
        self.assertEqual(auth.get_home_dir(user),
                         self.get_current_user_homedir())
        self.assertEqual(auth.get_perms(user), "elradfmw")
        # self.assertEqual(auth.get_msg_login(user), "Login successful.")
        # self.assertEqual(auth.get_msg_quit(user), "Goodbye.")

    def test_override_user_errors(self):
        if self.authorizer_class.__name__ == 'UnixAuthorizer':
            auth = self.authorizer_class(require_valid_shell=False)
        else:
            auth = self.authorizer_class()
        this_user = self.get_current_user()
        for x in self.get_users():
            if x != this_user:
                another_user = x
                break
        nonexistent_user = self.get_nonexistent_user()
        self.assertRaisesWithMsg(
            AuthorizerError,
            "at least one keyword argument must be specified",
            auth.override_user, this_user)
        self.assertRaisesWithMsg(AuthorizerError,
                                 'no such user %s' % nonexistent_user,
                                 auth.override_user, nonexistent_user,
                                 perm='r')
        if self.authorizer_class.__name__ == 'UnixAuthorizer':
            auth = self.authorizer_class(allowed_users=[this_user],
                                         require_valid_shell=False)
        else:
            auth = self.authorizer_class(allowed_users=[this_user])
        auth.override_user(this_user, perm='r')
        self.assertRaisesWithMsg(AuthorizerError,
                                 '%s is not an allowed user' % another_user,
                                 auth.override_user, another_user, perm='r')
        if self.authorizer_class.__name__ == 'UnixAuthorizer':
            auth = self.authorizer_class(rejected_users=[this_user],
                                         require_valid_shell=False)
        else:
            auth = self.authorizer_class(rejected_users=[this_user])
        auth.override_user(another_user, perm='r')
        self.assertRaisesWithMsg(AuthorizerError,
                                 '%s is not an allowed user' % this_user,
                                 auth.override_user, this_user, perm='r')
        self.assertRaisesWithMsg(AuthorizerError,
                                 "can't assign password to anonymous user",
                                 auth.override_user, "anonymous",
                                 password='foo')


# =====================================================================
# --- UNIX authorizer
# =====================================================================


class TestUnixAuthorizer(_SharedAuthorizerTests, unittest.TestCase):
    """Unix authorizer specific tests."""

    authorizer_class = getattr(authorizers, "UnixAuthorizer", None)

    def setUp(self):
        if os.name != 'posix':
            self.skipTest("UNIX only")
        if sys.version_info < (2, 5):
            self.skipTest("python >= 2.5 only")
        try:
            import spwd  # NOQA
        except ImportError:
            self.skipTest("spwd module not available")
        try:
            authorizers.UnixAuthorizer()
        except AuthorizerError:  # not root
            self.skipTest("need root access")

    def test_get_perms_anonymous(self):
        auth = authorizers.UnixAuthorizer(
            global_perm='elr', anonymous_user=self.get_current_user())
        self.assertTrue('e' in auth.get_perms('anonymous'))
        self.assertFalse('w' in auth.get_perms('anonymous'))
        warnings.filterwarnings("ignore")
        auth.override_user('anonymous', perm='w')
        warnings.resetwarnings()
        self.assertTrue('w' in auth.get_perms('anonymous'))

    def test_has_perm_anonymous(self):
        auth = authorizers.UnixAuthorizer(
            global_perm='elr', anonymous_user=self.get_current_user())
        self.assertTrue(auth.has_perm(self.get_current_user(), 'r'))
        self.assertFalse(auth.has_perm(self.get_current_user(), 'w'))
        self.assertTrue(auth.has_perm('anonymous', 'e'))
        self.assertFalse(auth.has_perm('anonymous', 'w'))
        warnings.filterwarnings("ignore")
        auth.override_user('anonymous', perm='w')
        warnings.resetwarnings()
        self.assertTrue(auth.has_perm('anonymous', 'w'))

    def test_validate_authentication(self):
        # we can only test for invalid credentials
        auth = authorizers.UnixAuthorizer(require_valid_shell=False)
        self.assertRaises(AuthenticationFailed,
                          auth.validate_authentication, '?!foo', '?!foo', None)
        auth = authorizers.UnixAuthorizer(require_valid_shell=True)
        self.assertRaises(AuthenticationFailed,
                          auth.validate_authentication, '?!foo', '?!foo', None)

    def test_validate_authentication_anonymous(self):
        current_user = self.get_current_user()
        auth = authorizers.UnixAuthorizer(anonymous_user=current_user,
                                          require_valid_shell=False)
        self.assertRaises(AuthenticationFailed,
                          auth.validate_authentication, 'foo', 'passwd', None)
        self.assertRaises(
            AuthenticationFailed,
            auth.validate_authentication, current_user, 'passwd', None)
        auth.validate_authentication('anonymous', 'passwd', None)

    def test_require_valid_shell(self):

        def get_fake_shell_user():
            for user in self.get_users():
                shell = pwd.getpwnam(user).pw_shell
                # On linux fake shell is usually /bin/false, on
                # freebsd /usr/sbin/nologin;  in case of other
                # UNIX variants test needs to be adjusted.
                if '/false' in shell or '/nologin' in shell:
                    return user
            self.fail("no user found")

        user = get_fake_shell_user()
        self.assertRaisesWithMsg(
            AuthorizerError,
            "user %s has not a valid shell" % user,
            authorizers.UnixAuthorizer, allowed_users=[user])
        # commented as it first fails for invalid home
        # self.assertRaisesWithMsg(
        #     ValueError,
        #     "user %s has not a valid shell" % user,
        #     authorizers.UnixAuthorizer, anonymous_user=user)
        auth = authorizers.UnixAuthorizer()
        self.assertTrue(auth._has_valid_shell(self.get_current_user()))
        self.assertFalse(auth._has_valid_shell(user))
        self.assertRaisesWithMsg(AuthorizerError,
                                 "User %s doesn't have a valid shell." % user,
                                 auth.override_user, user, perm='r')

    def test_not_root(self):
        # UnixAuthorizer is supposed to work only as super user
        auth = self.authorizer_class()
        try:
            auth.impersonate_user('nobody', '')
            self.assertRaisesWithMsg(AuthorizerError,
                                     "super user privileges are required",
                                     authorizers.UnixAuthorizer)
        finally:
            auth.terminate_impersonation('nobody')


# =====================================================================
# --- Windows authorizer
# =====================================================================


class TestWindowsAuthorizer(_SharedAuthorizerTests, unittest.TestCase):
    """Windows authorizer specific tests."""

    authorizer_class = getattr(authorizers, "WindowsAuthorizer", None)

    def setUp(self):
        if os.name != 'nt':
            self.skipTest("Windows only")
        try:
            import win32api  # NOQA
        except ImportError:
            self.skipTest("pywin32 not installed")

    def test_wrong_anonymous_credentials(self):
        user = self.get_current_user()
        self.assertRaises(Win32ExtError, self.authorizer_class,
                          anonymous_user=user,
                          anonymous_password='$|1wrongpasswd')


# =====================================================================
# --- UNIX filesystem
# =====================================================================

if os.name == 'posix':
    class TestUnixFilesystem(unittest.TestCase):

        def setUp(self):
            if os.name != 'posix':
                self.skipTest("UNIX only")

        def test_case(self):
            root = getcwdu()
            fs = filesystems.UnixFilesystem(root, None)
            self.assertEqual(fs.root, root)
            self.assertEqual(fs.cwd, root)
            cdup = os.path.dirname(root)
            self.assertEqual(fs.ftp2fs(u('..')), cdup)
            self.assertEqual(fs.fs2ftp(root), root)


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
        os._exit(0)

if __name__ == '__main__':
    test_main()
