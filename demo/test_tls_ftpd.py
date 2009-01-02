#!/usr/bin/env python
# test_tls_ftpd.py

"""Minimal test suite for tls_ftpd.py script"""

import unittest
import ftplib
import ssl
import os
import socket
import threading
import StringIO

import tls_ftpd
from pyftpdlib import ftpserver


HOST = 'localhost'
USER = 'user'
PASSWD = 'passwd'
HOME = os.getcwd()
try:
    from test.test_support import TESTFN
except ImportError:
    TESTFN = 'temp-fname'


class TLS_FTP(ftplib.FTP):
    """A ftplib.FTP subclass which adds TLS support to FTP as described
    in RFC-4217.

    Connect as usual to port 21 securing control connection before
    authenticating.

    Usage example:
    >>> import TLS_FTP
    >>> ftps = TLS_FTP('ftp.python.org')
    >>> ftps.login()  # login anonimously
    '230 Guest login ok, access restrictions apply.'
    >>> ftps.prot_p()  # switch to secure data connection
    '200 Protection level set to P'
    >>> ftps.retrlines('LIST')  # list directory content securely
    total 9
    drwxr-xr-x   8 root     wheel        1024 Jan  3  1994 .
    drwxr-xr-x   8 root     wheel        1024 Jan  3  1994 ..
    drwxr-xr-x   2 root     wheel        1024 Jan  3  1994 bin
    drwxr-xr-x   2 root     wheel        1024 Jan  3  1994 etc
    d-wxrwxr-x   2 ftp      wheel        1024 Sep  5 13:43 incoming
    drwxr-xr-x   2 root     wheel        1024 Nov 17  1993 lib
    drwxr-xr-x   6 1094     wheel        1024 Sep 13 19:07 pub
    drwxr-xr-x   3 root     wheel        1024 Jan  3  1994 usr
    -rw-r--r--   1 root     root          312 Aug  1  1994 welcome.msg
    '226 Transfer complete.'
    >>> ftps.quit()
    '221 Goodbye.'
    >>>
    """

    def __init__(self, host='', user='', passwd='', acct='', keyfile=None,
                 certfile=None, timeout=None):
        self.keyfile = keyfile
        self.certfile = certfile
        self.encrypted_pi = False
        self.prot_private = False
        ftplib.FTP.__init__(self, host, user, passwd, acct, timeout)

    def auth_tls(self):
        """Set up secure control connection by using TLS."""
        resp = self.voidcmd('AUTH TLS')
        self.sock = ssl.wrap_socket(self.sock, self.keyfile, self.certfile,
                                    ssl_version=ssl.PROTOCOL_TLSv1)
        self.file = self.sock.makefile(mode='rb')
        return resp

    def prot_p(self):
        """Set up secure data connection."""
        # PROT defines whether or not the data channel is to be protected.
        # Though RFC-2228 defines four possible protection levels,
        # RFC-4217 only recommends two, Clear and Private.
        # Clear (PROT C) means that no security is to be used on the
        # data-channel, Private (PROT P) means that the data-channel
        # should be protected by TLS.
        # PBSZ command MUST still be issued, but must have a parameter of
        # '0' to indicate that no buffering is taking place and the data
        # connection should not be encapsulated.
        self.voidcmd('PBSZ 0')
        resp = self.voidcmd('PROT P')
        self.prot_private = True
        return resp

    def prot_c(self):
        """Set up clear text data channel."""
        resp = self.voidcmd('PROT C')
        self.prot_private = False
        return resp

    # --- Overridden FTP methods

    def ntransfercmd(self, cmd, rest=None):
        conn, size = ftplib.FTP.ntransfercmd(self, cmd, rest)
        if self.prot_private:
            conn = ssl.wrap_socket(conn, self.keyfile, self.certfile, ssl_version=ssl.PROTOCOL_TLSv1)
        return conn, size

    def retrbinary(self, cmd, callback, blocksize=8192, rest=None):
        self.voidcmd('TYPE I')
        conn = self.transfercmd(cmd, rest)
        while 1:
            data = conn.recv(blocksize)
            if not data:
                break
            callback(data)
        # shutdown ssl layer
        if isinstance(conn, ssl.SSLSocket):
            conn.unwrap()
        conn.close()
        return self.voidresp()

    def retrlines(self, cmd, callback = None):
        from ftplib import print_line, CRLF
        if callback is None: callback = print_line
        resp = self.sendcmd('TYPE A')
        conn = self.transfercmd(cmd)
        fp = conn.makefile('rb')
        while 1:
            line = fp.readline()
            if self.debugging > 2: print '*retr*', repr(line)
            if not line:
                break
            if line[-2:] == CRLF:
                line = line[:-2]
            elif line[-1:] == '\n':
                line = line[:-1]
            callback(line)
        # shutdown ssl layer
        if isinstance(conn, ssl.SSLSocket):
            conn.unwrap()
        fp.close()
        conn.close()
        return self.voidresp()

    def storbinary(self, cmd, fp, blocksize=8192, callback=None):
        self.voidcmd('TYPE I')
        conn = self.transfercmd(cmd)
        while 1:
            buf = fp.read(blocksize)
            if not buf: break
            conn.sendall(buf)
            if callback: callback(buf)
        # shutdown ssl layer
        if isinstance(conn, ssl.SSLSocket):
            conn.unwrap()
        conn.close()
        return self.voidresp()

    def storlines(self, cmd, fp, callback=None):
        from ftplib import CRLF
        self.voidcmd('TYPE A')
        conn = self.transfercmd(cmd)
        while 1:
            buf = fp.readline()
            if not buf: break
            if buf[-2:] != CRLF:
                if buf[-1] in CRLF: buf = buf[:-1]
                buf = buf + CRLF
            conn.sendall(buf)
            if callback: callback(buf)
        # shutdown ssl layer
        if isinstance(conn, ssl.SSLSocket):
            conn.unwrap()
        conn.close()
        return self.voidresp()

    # overridden to accept 6xy as valid response code
    def getresp(self):
        resp = self.getmultiline()
        if self.debugging: print '*resp*', self.sanitize(resp)
        self.lastresp = resp[:3]
        c = resp[:1]
        if c in ('1', '2', '3', '6'):
            return resp
        if c == '4':
            raise ftplib.error_temp, resp
        if c == '5':
            raise ftplib.error_perm, resp
        raise ftplib.error_proto, resp


class TLS_FTPd(threading.Thread):
    """A threaded FTPS server used for running tests.

    This is basically a modified version of the FTPServer class which
    wraps the polling loop into a thread.

    The instance returned can be used to start(), stop() and
    eventually re-start() the server.
    """

    def __init__(self, host=HOST, port=0, verbose=False):
        threading.Thread.__init__(self)
        self.__serving = False
        self.__stopped = False
        self.__lock = threading.Lock()
        self.__flag = threading.Event()

        if not verbose:
            ftpserver.log = ftpserver.logline = lambda x: x
        self.authorizer = ftpserver.DummyAuthorizer()
        self.authorizer.add_user(USER, PASSWD, HOME, perm='elradfmw')  # full perms
        self.authorizer.add_anonymous(HOME)
        self.handler = tls_ftpd.TLS_FTPHandler
        self.handler.authorizer = self.authorizer
        self.server = ftpserver.FTPServer((host, port), self.handler)
        self.host, self.port = self.server.socket.getsockname()[:2]

    def __repr__(self):
        status = [self.__class__.__module__ + "." + self.__class__.__name__]
        if self.__serving:
            status.append('active')
        else:
            status.append('inactive')
        status.append('%s:%s' %self.server.socket.getsockname()[:2])
        return '<%s at %#x>' % (' '.join(status), id(self))

    def start(self, timeout=0.001, use_poll=False, map=None):
        """Start serving until an explicit stop() request.
        Polls for shutdown every 'timeout' seconds.
        """
        if self.__serving:
            raise RuntimeError("Server already started")
        if self.__stopped:
            # ensure the server can be started again
            ThreadedFTPServer.__init__(self, self.socket.getsockname(),
                                       self.handler)
        self.__timeout = timeout
        self.__use_poll = use_poll
        self.__map = map
        threading.Thread.start(self)
        self.__flag.wait()

    def run(self):
        self.__serving = True
        self.__flag.set()
        while self.__serving:
            self.__lock.acquire()
            self.server.serve_forever(timeout=self.__timeout, count=1,
                                      use_poll=self.__use_poll, map=self.__map)
            self.__lock.release()
        self.server.close_all(ignore_all=True)

    def stop(self):
        """Stop serving (also disconnecting all currently connected
        clients) by telling the serve_forever() loop to stop and
        waits until it does.
        """
        if not self.__serving:
            raise RuntimeError("Server not started yet")
        self.__serving = False
        self.__stopped = True
        self.join()


class TestCase(unittest.TestCase):

    def setUp(self):
        self.server = TLS_FTPd()
        self.server.start()
        self.client = TLS_FTP()
        self.client.connect(self.server.host, self.server.port)
        self.client.sock.settimeout(2)
        self.dummy_recvfile = StringIO.StringIO()
        self.dummy_sendfile = StringIO.StringIO()

    def tearDown(self):
        self.client.close()
        self.server.stop()
        self.dummy_recvfile.close()
        self.dummy_sendfile.close()
        if os.path.isfile(TESTFN):
            os.remove(TESTFN)

    def transfer_data(self):
        try:
            data = 'abcde12345' * 100000
            self.dummy_sendfile.write(data)
            self.dummy_sendfile.seek(0)
            self.client.storbinary('stor ' + TESTFN, self.dummy_sendfile)
            self.client.retrbinary('retr ' + TESTFN, self.dummy_recvfile.write)
            self.dummy_recvfile.seek(0)
            self.assertEqual(hash(data), hash (self.dummy_recvfile.read()))
        finally:
            # We do not use os.remove() because file could still be
            # locked by ftpd thread.
            if os.path.exists(TESTFN):
                try:
                    self.client.delete(TESTFN)
                except (ftplib.Error, EOFError, socket.error):
                    pass

    def test_auth(self):
        self.assertEqual(self.client.auth_tls()[:3], '234')
        self.assertRaises(ftplib.error_perm, self.client.auth_tls)
        self.assertRaises(ftplib.error_perm, self.client.sendcmd, 'auth foo')

    def test_pbsz(self):
        # authentication is required
        self.assertRaises(ftplib.error_perm, self.client.sendcmd, 'pbsz 0')
        self.client.login()
        self.client.auth_tls()
        self.assertEqual(self.client.sendcmd('pbsz 0'), '200 PBSZ=0 successful.')
        self.assertEqual(self.client.sendcmd('pbsz 9'), '200 PBSZ=0 successful.')
        self.assertRaises(ftplib.error_perm, self.client.sendcmd, 'pbsz')

    def test_prot(self):
        self.client.auth_tls()
        # authentication is required
        self.assertRaises(ftplib.error_perm, self.client.sendcmd, 'prot p')
        self.client.login()
        # no argument
        self.assertRaises(ftplib.error_perm, self.client.sendcmd, 'prot')
        # no PBSZ issued before PROT
        self.assertRaises(ftplib.error_perm, self.client.sendcmd, 'prot p')
        # unsupported arguments
        self.assertRaises(ftplib.error_perm, self.client.sendcmd, 'prot s')
        self.assertRaises(ftplib.error_perm, self.client.sendcmd, 'prot e')
        # unrecognized argument
        self.assertRaises(ftplib.error_perm, self.client.sendcmd, 'prot x')
        # supported arguments
        self.client.sendcmd('pbsz 0')
        self.assertEqual(self.client.sendcmd('prot c'), '200 Protection set to Clear')
        self.assertEqual(self.client.sendcmd('prot p'), '200 Protection set to Private')

    def test_cleartext_data_transfer_1(self):
        self.client.login(USER, PASSWD)
        self.transfer_data()

    def test_cleartext_data_transfer_2(self):
        # like above but using an encrypted control channel
        self.client.login(USER, PASSWD)
        self.client.auth_tls()
        self.transfer_data()

    def test_encrypted_data_transfer(self):
        # like above but using an encrypted control channel
        self.client.login(USER, PASSWD)
        self.client.auth_tls()
        self.client.prot_p()
        self.transfer_data()


def test_main():
    test_suite = unittest.TestSuite()
    tests = [TestCase]
    for test in tests:
        test_suite.addTest(unittest.makeSuite(test))
    unittest.TextTestRunner(verbosity=2).run(test_suite)

if __name__ == '__main__':
    test_main()