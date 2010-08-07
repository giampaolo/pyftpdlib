#!/usr/bin/env python
# $Id$

"""Tests for pyftpdlib.contrib namespace: handlers.py and
authorizers.py modules.
"""

import ftplib
import unittest
import os
import random
import string
import warnings

try:
    import pwd, spwd, crypt
except ImportError:
    pwd = spwd = crypt = None

try:
    import ssl
except ImportError:
    ssl = None

from pyftpdlib import ftpserver
from pyftpdlib.contrib import authorizers
from pyftpdlib.contrib import handlers
from test_ftpd import *


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
    handler.certfile = os.path.abspath(os.path.join(os.path.dirname(__file__),
                                       'keycert.pem'))


# --- FTPS mixin tests
#
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
    def test_on_incomplete_file_received(self): pass
    def test_on_incomplete_file_sent(self): pass
    def test_on_login(self): pass


class TestIPv4EnvironmentTLSMixin(TLSTestMixin, TestIPv4Environment): pass
class TestIPv6EnvironmentTLSMixin(TLSTestMixin, TestIPv6Environment): pass
class TestCornerCasesTLSMixin(TLSTestMixin, TestCornerCases): pass


class TestFTPS(unittest.TestCase):
    """Specific tests fot TSL_FTPHandler class."""

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
        try:
            sock = self.client.sock.unwrap()
        except socket.error, err:
            if err.errno == 0:
                return
            raise
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
        protos = (ssl.PROTOCOL_SSLv2, ssl.PROTOCOL_SSLv3,
                  ssl.PROTOCOL_SSLv23, ssl.PROTOCOL_TLSv1)
        for proto in protos:
            self.try_protocol_combo(ssl.PROTOCOL_SSLv2, proto)
        for proto in protos:
            self.try_protocol_combo(ssl.PROTOCOL_SSLv3, proto)
        for proto in protos:
            self.try_protocol_combo(ssl.PROTOCOL_SSLv23, proto)
        for proto in protos:
            self.try_protocol_combo(ssl.PROTOCOL_TLSv1, proto)


# --- System dependant authorizers tests

class CommonAuthorizersTest(unittest.TestCase):
    """Tests valid for both UnixAuthorizer and WindowsAuthorizer which
    are supposed to share the same API.
    """

    def assertRaisesWithMsg(self, excClass, msg, callableObj, *args, **kwargs):
        try:
            callableObj(*args, **kwargs)
        except excClass, why:
            if str(why) == msg:
                return
            raise self.failureException("%s != %s" %(str(why), msg))
        else:
            if hasattr(excClass,'__name__'): excName = excClass.__name__
            else: excName = str(excClass)
            raise self.failureException, "%s not raised" % excName

    def test_get_home_dir(self):
        auth = authorizers.UnixAuthorizer()
        home = auth.get_home_dir(self.get_current_user())
        nonexistent_user = self.get_nonexistent_user()
        self.assertTrue(os.path.isdir(home))
        if auth.has_user('nobody'):
            home = auth.get_home_dir('nobody')
            self.assertFalse(os.path.isdir(home))
        self.assertRaisesWithMsg(ftpserver.AuthorizerError,
                                 "no such user %s" % nonexistent_user,
                                 auth.get_home_dir, nonexistent_user)

    def test_has_user(self):
        auth = authorizers.UnixAuthorizer()
        self.assertTrue(auth.has_user(self.get_current_user()))
        self.assertFalse(auth.has_user(self.get_nonexistent_user()))

    def test_validate_authentication(self):
        # can't test for actual success in case of valid authentication
        # here as we don't have the user password
        current_user = self.get_current_user()
        auth = authorizers.UnixAuthorizer(anonymous_user=current_user)
        self.assertFalse(auth.validate_authentication('foo', 'passwd'))
        self.assertFalse(auth.validate_authentication(current_user, 'passwd'))
        self.assertTrue(auth.validate_authentication('anonymous', 'passwd'))

    def test_impersonate_user(self):
        auth = authorizers.UnixAuthorizer()
        nonexistent_user = self.get_nonexistent_user()
        self.assertRaisesWithMsg(ftpserver.AuthorizerError, 
                                 "no such user %s" % nonexistent_user,
                                 auth.impersonate_user, nonexistent_user, 'pwd')
        auth.impersonate_user(self.get_current_user(), '')
        auth.terminate_impersonation()

    def test_terminate_impersonation(self):
        user = self.get_nonexistent_user()
        auth = authorizers.UnixAuthorizer()
        auth.terminate_impersonation()

    def test_get_perms(self):
        auth = authorizers.UnixAuthorizer(global_perm='elr', 
                                        anonymous_user=self.get_current_user())
        self.assertTrue('r' in auth.get_perms(self.get_current_user()))
        self.assertFalse('w' in auth.get_perms(self.get_current_user()))
        self.assertTrue('e' in auth.get_perms('anonymous'))
        self.assertFalse('w' in auth.get_perms('anonymous'))
        warnings.filterwarnings("ignore")
        auth.override_user('anonymous', perm='w')
        warnings.resetwarnings()        
        self.assertTrue('w' in auth.get_perms('anonymous'))

    def test_has_perm(self):
        auth = authorizers.UnixAuthorizer(global_perm='elr', 
                                        anonymous_user=self.get_current_user())
        self.assertTrue(auth.has_perm(self.get_current_user(), 'r'))
        self.assertFalse(auth.has_perm(self.get_current_user(), 'w'))
        self.assertTrue(auth.has_perm('anonymous', 'e'))
        self.assertFalse(auth.has_perm('anonymous', 'w'))
        warnings.filterwarnings("ignore")
        auth.override_user('anonymous', perm='w')
        warnings.resetwarnings()
        self.assertTrue(auth.has_perm('anonymous', 'w'))

    def test_messages(self):
        auth = authorizers.UnixAuthorizer(msg_login="login", msg_quit="quit")
        self.assertTrue(auth.get_msg_login, "login")
        self.assertTrue(auth.get_msg_quit, "quit")

    def test_access_options(self):
        self.assertRaisesWithMsg(authorizers.AuthorizerError,
             "rejected_users and allowed_users options are mutually exclusive",
             authorizers.UnixAuthorizer, allowed_users=['foo'], 
                                         rejected_users=['bar'])

    def test_override_user(self):
        auth = authorizers.UnixAuthorizer()
        user = self.get_current_user()
        auth.override_user(user, password='foo')
        self.assertTrue(auth.validate_authentication(user, 'foo'))
        self.assertFalse(auth.validate_authentication(user, 'bar'))
        auth.override_user(user, homedir=os.getcwd())
        self.assertEqual(auth.get_home_dir(user), os.getcwd())
        auth.override_user(user, perm="r")
        self.assertEqual(auth.get_perms(user), "r")
        auth.override_user(user, msg_login="foo")
        self.assertEqual(auth.get_msg_login(user), "foo")
        auth.override_user(user, msg_quit="bar")
        self.assertEqual(auth.get_msg_quit(user), "bar")

    def test_override_user_errors(self):
        auth = authorizers.UnixAuthorizer()
        this_user = self.get_current_user()
        another_user = self.get_users()[-1]
        nonexistent_user = self.get_nonexistent_user()
        self.assertRaisesWithMsg(ftpserver.AuthorizerError, 
                                "at least one keyword argument must be specified",
                                auth.override_user, this_user)
        self.assertRaisesWithMsg(ftpserver.AuthorizerError, 
                                 'no such user %s' % nonexistent_user,
                                 auth.override_user, nonexistent_user, perm='r')
        auth = authorizers.UnixAuthorizer(allowed_users=[this_user])
        auth.override_user(this_user, perm='r')
        self.assertRaisesWithMsg(ftpserver.AuthorizerError, 
                                 '%s is not an allowed user' % another_user,
                                 auth.override_user, another_user, perm='r')
        auth = authorizers.UnixAuthorizer(rejected_users=[this_user])
        auth.override_user(another_user, perm='r')
        self.assertRaisesWithMsg(ftpserver.AuthorizerError, 
                                 '%s is not an allowed user' % this_user,
                                 auth.override_user, this_user, perm='r')
        auth = authorizers.UnixAuthorizer(anonymous_user=this_user)
        self.assertRaisesWithMsg(ftpserver.AuthorizerError, 
                                 "can't assign password to anonymous user",
                                 auth.override_user, "anonymous", password='foo')


class TestUnixAuthorizer(CommonAuthorizersTest):
    """UnixAuthorizer specific tests."""

    def get_users(self):
        return [entry.pw_name for entry in pwd.getpwall()]

    def get_current_user(self):
        return pwd.getpwuid(os.getuid()).pw_name

    def get_current_user_homedir(self):
        return pwd.getpwuid(os.getuid()).pw_dir

    def get_nonexistent_user(self):
        # return a user which does not exist on the system
        users = self.get_users()
        letters = string.ascii_lowercase
        while 1:
            user = ''.join([random.choice(letters) for i in range(10)])
            if user not in users:
                return user

    def test_not_root(self):
        # UnixAuthorizer is supposed to work only as super user
        auth = authorizers.UnixAuthorizer()
        try:
            auth.impersonate_user('nobody', '')
            self.assertRaisesWithMsg(ftpserver.AuthorizerError, 
                                     "super user privileges are required",
                                     authorizers.UnixAuthorizer)
        finally:
            auth.terminate_impersonation()


def test_main():
    test_suite = unittest.TestSuite()
    tests = []

    # FTPS tests
    if hasattr(ftplib, 'FTP_TLS'):  # Added in Python 2.7
        ftps_tests = [TestFTPS,
                      TestFtpAuthenticationTLSMixin,
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
                     ]
        if SUPPORTS_IPV4:
            ftps_tests.append(TestIPv4EnvironmentTLSMixin)
        if SUPPORTS_IPV6:
            ftps_tests.append(TestIPv6EnvironmentTLSMixin)
        tests += ftps_tests

    # authorizers tests
    if hasattr(authorizers, "UnixAuthorizer"):
        try:
            authorizers.UnixAuthorizer()
        except ftpserver.AuthorizerError:  # not root
            pass
        else:
            tests.append(TestUnixAuthorizer)

    tests = [TestUnixAuthorizer]
    for test in tests:
        test_suite.addTest(unittest.makeSuite(test))
    safe_remove(TESTFN)
    unittest.TextTestRunner(verbosity=2).run(test_suite)
    safe_remove(TESTFN)


if __name__ == '__main__':
    test_main()

