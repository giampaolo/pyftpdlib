#!/usr/bin/env python
# test_ftpd.py

#  ======================================================================
#  Copyright (C) 2007 Giampaolo Rodola' <g.rodola@gmail.com>
#
#                         All Rights Reserved
#
#  Permission to use, copy, modify, and distribute this software and
#  its documentation for any purpose and without fee is hereby
#  granted, provided that the above copyright notice appear in all
#  copies and that both that copyright notice and this permission
#  notice appear in supporting documentation, and that the name of
#  Giampaolo Rodola' not be used in advertising or publicity pertaining to
#  distribution of the software without specific, written prior
#  permission.
#
#  Giampaolo Rodola' DISCLAIMS ALL WARRANTIES WITH REGARD TO THIS SOFTWARE,
#  INCLUDING ALL IMPLIED WARRANTIES OF MERCHANTABILITY AND FITNESS, IN
#  NO EVENT Giampaolo Rodola' BE LIABLE FOR ANY SPECIAL, INDIRECT OR
#  CONSEQUENTIAL DAMAGES OR ANY DAMAGES WHATSOEVER RESULTING FROM LOSS
#  OF USE, DATA OR PROFITS, WHETHER IN AN ACTION OF CONTRACT,
#  NEGLIGENCE OR OTHER TORTIOUS ACTION, ARISING OUT OF OR IN
#  CONNECTION WITH THE USE OR PERFORMANCE OF THIS SOFTWARE.
#  ======================================================================


# This test suite has been run successfully on the following systems:
#
# -------------------------------------------------------
#  System                          | Python version
# -------------------------------------------------------
#  Linux CentOS 2.6.20.15          | 2.4, 2.5
#  Linux Ubuntu 2.6.20-15          | 2.4, 2.5
#  Linux Debian 2.4.27-2-386       | 2.3.5
#  Windows XP prof sp2             | 2.3, 2.4, 2.5, 2.6a
#  OS X 10.4.10                    | 2.3, 2.4, 2.5
#  FreeBSD 6.2, 7.0-RC1            | 2.4, 2.5
#  Windows Mobile 6                | PythonCE 2.5
# -------------------------------------------------------


import threading
import unittest
import socket
import os
import re
import tempfile
import ftplib
import random
import warnings

from pyftpdlib import ftpserver


__release__ = 'pyftpdlib 0.3.0'

HOST = 'localhost'
USER = 'user'
PASSWD = '12345'
HOME = os.getcwd()
try:
    from test.test_support import TESTFN
except ImportError:
    TESTFN = 'temp-fname'
TESTFN2 = TESTFN + '2'
TESTFN3 = TESTFN + '3'


class AbstractedFSClass(unittest.TestCase):
    """Test for conversion utility methods of AbstractedFS class."""

    def test_ftpnorm(self):
        # Tests for ftpnorm method.
        ae = self.assertEquals
        fs = ftpserver.AbstractedFS()

        fs.cwd = '/'
        ae(fs.ftpnorm(''), '/')
        ae(fs.ftpnorm('/'), '/')
        ae(fs.ftpnorm('.'), '/')
        ae(fs.ftpnorm('..'), '/')
        ae(fs.ftpnorm('a'), '/a')
        ae(fs.ftpnorm('/a'), '/a')
        ae(fs.ftpnorm('/a/'), '/a')
        ae(fs.ftpnorm('a/..'), '/')
        ae(fs.ftpnorm('a/b'), '/a/b')
        ae(fs.ftpnorm('a/b/..'), '/a')
        ae(fs.ftpnorm('a/b/../..'), '/')
        fs.cwd = '/sub'
        ae(fs.ftpnorm(''), '/sub')
        ae(fs.ftpnorm('/'), '/')
        ae(fs.ftpnorm('.'), '/sub')
        ae(fs.ftpnorm('..'), '/')
        ae(fs.ftpnorm('a'), '/sub/a')
        ae(fs.ftpnorm('a/'), '/sub/a')
        ae(fs.ftpnorm('a/..'), '/sub')
        ae(fs.ftpnorm('a/b'), '/sub/a/b')
        ae(fs.ftpnorm('a/b/'), '/sub/a/b')
        ae(fs.ftpnorm('a/b/..'), '/sub/a')
        ae(fs.ftpnorm('a/b/../..'), '/sub')
        ae(fs.ftpnorm('a/b/../../..'), '/')
        ae(fs.ftpnorm('//'), '/')  # UNC paths must be collapsed

    def test_ftp2fs(self):
        # Tests for ftp2fs method.
        ae = self.assertEquals
        fs = ftpserver.AbstractedFS()
        join = lambda x, y: os.path.join(x, y.replace('/', os.sep))

        def goforit(root):
            fs.root = root
            fs.cwd = '/'
            ae(fs.ftp2fs(''), root)
            ae(fs.ftp2fs('/'), root)
            ae(fs.ftp2fs('.'), root)
            ae(fs.ftp2fs('..'), root)
            ae(fs.ftp2fs('a'), join(root, 'a'))
            ae(fs.ftp2fs('/a'), join(root, 'a'))
            ae(fs.ftp2fs('/a/'), join(root, 'a'))
            ae(fs.ftp2fs('a/..'), root)
            ae(fs.ftp2fs('a/b'), join(root, r'a/b'))
            ae(fs.ftp2fs('/a/b'), join(root, r'a/b'))
            ae(fs.ftp2fs('/a/b/..'), join(root, 'a'))
            ae(fs.ftp2fs('/a/b/../..'), root)
            fs.cwd = '/sub'
            ae(fs.ftp2fs(''), join(root, 'sub'))
            ae(fs.ftp2fs('/'), root)
            ae(fs.ftp2fs('.'), join(root, 'sub'))
            ae(fs.ftp2fs('..'), root)
            ae(fs.ftp2fs('a'), join(root, 'sub/a'))
            ae(fs.ftp2fs('a/'), join(root, 'sub/a'))
            ae(fs.ftp2fs('a/..'), join(root, 'sub'))
            ae(fs.ftp2fs('a/b'), join(root, 'sub/a/b'))
            ae(fs.ftp2fs('a/b/..'), join(root, 'sub/a'))
            ae(fs.ftp2fs('a/b/../..'), join(root, 'sub'))
            ae(fs.ftp2fs('a/b/../../..'), root)
            ae(fs.ftp2fs('//a'), join(root, 'a'))  # UNC paths must be collapsed

        if os.sep == '\\':
            goforit(r'C:\dir')
            goforit('C:\\')
            # on DOS-derived filesystems (e.g. Windows) this is the same
            # as specifying the current drive directory (e.g. 'C:\\')
            goforit('\\')
        elif os.sep == '/':
            goforit('/home/user')
            goforit('/')
        else:
            # os.sep == ':'? Don't know... let's try it anyway
            goforit(os.getcwd())

    def test_fs2ftp(self):
        # Tests for fs2ftp method.
        ae = self.assertEquals
        fs = ftpserver.AbstractedFS()
        join = lambda x,y: os.path.join(x, y.replace('/', os.sep))

        def goforit(root):
            fs.root = root
            ae(fs.fs2ftp(root), '/')
            ae(fs.fs2ftp(join(root, '/')), '/')
            ae(fs.fs2ftp(join(root, '.')), '/')
            ae(fs.fs2ftp(join(root, '..')), '/')  # can't escape from root
            ae(fs.fs2ftp(join(root, 'a')), '/a')
            ae(fs.fs2ftp(join(root, 'a/')), '/a')
            ae(fs.fs2ftp(join(root, 'a/..')), '/')
            ae(fs.fs2ftp(join(root, 'a/b')), '/a/b')
            ae(fs.fs2ftp(join(root, 'a/b')), '/a/b')
            ae(fs.fs2ftp(join(root, 'a/b/..')), '/a')
            ae(fs.fs2ftp(join(root, '/a/b/../..')), '/')
            fs.cwd = '/sub'
            ae(fs.fs2ftp(join(root, 'a/')), '/a')

        if os.sep == '\\':
            goforit(r'C:\dir')
            goforit('C:\\')
            # on DOS-derived filesystems (e.g. Windows) this is the same
            # as specifying the current drive directory (e.g. 'C:\\')
            goforit('\\')
            fs.root = r'C:\dir'
            ae(fs.fs2ftp('C:\\'), '/')
            ae(fs.fs2ftp('D:\\'), '/')
            ae(fs.fs2ftp('D:\\dir'), '/')
        elif os.sep == '/':
            goforit('/')
            assert os.path.realpath('/__home/user') == '/__home/user',\
                                    'Test skipped (symlinks not allowed).'
            goforit('/__home/user')
            fs.root = '/__home/user'
            ae(fs.fs2ftp('/__home'), '/')
            ae(fs.fs2ftp('/'), '/')
            ae(fs.fs2ftp('/__home/userx'), '/')
        else:
            # os.sep == ':'? Don't know... let's try it anyway
            goforit(os.getcwd())

    def test_validpath(self):
        # Tests for validpath method.
        fs = ftpserver.AbstractedFS()
        fs.root = HOME
        self.failUnless(fs.validpath(HOME))
        self.failUnless(fs.validpath(HOME + '/'))
        self.failIf(fs.validpath(HOME + 'xxx'))

    if hasattr(os, 'symlink'):
        # Tests for validpath on systems supporting symbolic links.

        def _safe_remove(self, path):
            # convenience function for removing temporary files
            try:
                os.remove(path)
            except os.error:
                pass

        def test_validpath_validlink(self):
            # Test validpath by issuing a symlink pointing to a path
            # inside the root directory.
            fs = ftpserver.AbstractedFS()
            fs.root = HOME
            try:
                open(TESTFN, 'w')
                os.symlink(TESTFN, TESTFN2)
                self.failUnless(fs.validpath(TESTFN))
            finally:
                self._safe_remove(TESTFN)
                self._safe_remove(TESTFN2)

        def test_validpath_external_symlink(self):
            # Test validpath by issuing a symlink pointing to a path
            # outside the root directory.
            fs = ftpserver.AbstractedFS()
            fs.root = HOME
            try:
                # tempfile should create our file in /tmp directory
                # which should be outside the user root. If it is not
                # we just skip the test.
                file = tempfile.NamedTemporaryFile()
                if HOME == os.path.dirname(file.name):
                    return
                os.symlink(file.name, TESTFN)
                self.failIf(fs.validpath(TESTFN))
            finally:
                self._safe_remove(TESTFN)
                file.close()


class DummyAuthorizerClass(unittest.TestCase):

    # temporarily change warnings to exceptions for the purposes of testing
    def setUp(self):
        warnings.filterwarnings("error")

    def tearDown(self):
        warnings.resetwarnings()

    def test_dummy_authorizer(self):
        auth = ftpserver.DummyAuthorizer()
        auth.user_table = {}

        # create user
        auth.add_user(USER, PASSWD, HOME)
        auth.add_anonymous(HOME)
        # check credentials
        self.failUnless(auth.validate_authentication(USER, PASSWD))
        self.failIf(auth.validate_authentication(USER, 'wrongpwd'))
        # remove them
        auth.remove_user(USER)
        auth.remove_user('anonymous')

        # raise exc if user does not exists
        self.assertRaises(KeyError, auth.remove_user, USER)
        # raise exc if path does not exist
        self.assertRaises(ftpserver.AuthorizerError, auth.add_user, USER,
                            PASSWD, '?:\\')
        self.assertRaises(ftpserver.AuthorizerError, auth.add_anonymous, '?:\\')
        # raise exc if user already exists
        auth.add_user(USER, PASSWD, HOME)
        auth.add_anonymous(HOME)
        self.assertRaises(ftpserver.AuthorizerError, auth.add_user, USER,
                            PASSWD, HOME)
        self.assertRaises(ftpserver.AuthorizerError, auth.add_anonymous, HOME)
        auth.remove_user(USER)
        auth.remove_user('anonymous')

        # raise on wrong permission
        self.assertRaises(ftpserver.AuthorizerError, auth.add_user, USER, 
                          PASSWD, HOME, perm='?')
        self.assertRaises(ftpserver.AuthorizerError, auth.add_anonymous, HOME,
                            perm='?')
        # expect warning on write permissions assigned to anonymous user
        for x in "adfmw":
            self.assertRaises(RuntimeWarning, auth.add_anonymous, HOME, perm=x)


class FtpAuthentication(unittest.TestCase):
    "test: USER, PASS, REIN."

    def setUp(self):
        self.server = FTPd()
        self.server.start()
        self.client = ftplib.FTP()
        self.client.connect(self.server.host, self.server.port)
        self.f1 = open(TESTFN, 'w+b')
        self.f2 = open(TESTFN2, 'w+b')

    def tearDown(self):
        self.client.close()
        self.server.stop()
        if not self.f1.closed:
            self.f1.close()
        if not self.f2.closed:
            self.f2.close()
        os.remove(TESTFN)
        os.remove(TESTFN2)        

    def test_auth_ok(self):
        self.client.login(user=USER, passwd=PASSWD)

    def test_auth_failed(self):
        self.assertRaises(ftplib.error_perm, self.client.login, USER, 
                              passwd='wrong')

    def test_anon_auth(self):
        self.client.login(user='anonymous', passwd='anon@')
        self.client.login(user='AnonYmoUs', passwd='anon@')
        self.client.login(user='anonymous', passwd='')

    def test_max_auth(self):
        self.assertRaises(ftplib.error_perm, self.client.login, USER, 'wrong')
        self.assertRaises(ftplib.error_perm, self.client.login, USER, 'wrong')
        self.assertRaises(ftplib.error_perm, self.client.login, USER, 'wrong')
        # If authentication fails for 3 times ftpd disconnects the
        # client.  We can check if that happens by using self.client.sendcmd()
        # on the 'dead' socket object.  If socket object is really
        # closed it should be raised a socket.error exception (Windows)
        # or a EOFError exception (Linux).
        self.assertRaises((socket.error, EOFError), self.client.sendcmd, '')

    def test_rein(self):
        self.client.login(user=USER, passwd=PASSWD)
        self.client.sendcmd('rein')
        # user not authenticated, error response expected
        self.assertRaises(ftplib.error_perm, self.client.sendcmd, 'pwd')
        # by logging-in again we should be able to execute a
        # file-system command
        self.client.login(user=USER, passwd=PASSWD)
        self.client.sendcmd('pwd')

    def test_rein_during_transfer(self):
        self.client.login(user=USER, passwd=PASSWD)
        data = 'abcde12345' * 100000
        self.f1.write(data)
        self.f1.close()

        self.client.voidcmd('TYPE I')
        conn = self.client.transfercmd('retr ' + TESTFN)
        bytes_recv = 0
        rein_sent = 0
        while 1:
            chunk = conn.recv(8192)
            # stop transfer while it isn't finished yet
            if bytes_recv >= 524288: # 2^19
                if not rein_sent:
                    # flush account, error response expected
                    self.client.sendcmd('rein')
                    self.assertRaises(ftplib.error_perm, self.client.dir)
                    rein_sent = 1
            if not chunk:
                break
            self.f2.write(chunk)
            bytes_recv += len(chunk)

        # a 226 response is expected once tranfer finishes
        self.assertEqual(self.client.voidresp()[:3], '226')
        # account is still flushed, error response is still expected
        self.assertRaises(ftplib.error_perm, self.client.sendcmd, 
                          'size ' + TESTFN)
        # by logging-in again we should be able to execute a
        # filesystem command
        self.client.login(user=USER, passwd=PASSWD)
        self.client.sendcmd('pwd')
        self.f2.seek(0)
        self.assertEqual(hash(data), hash (self.f2.read()))

    def test_user(self):
        # Test USER while already authenticated and no transfer
        # is in progress.
        self.client.login(user=USER, passwd=PASSWD)
        self.client.sendcmd('user ' + USER)  # authentication flushed
        self.assertRaises(ftplib.error_perm, self.client.sendcmd, 'pwd')
        self.client.sendcmd('pass ' + PASSWD)
        self.client.sendcmd('pwd')

    def test_user_on_transfer(self):
        # Test USER while already authenticated and a transfer is
        # in progress.
        self.client.login(user=USER, passwd=PASSWD)
        data = 'abcde12345' * 100000
        self.f1.write(data)
        self.f1.close()

        self.client.voidcmd('TYPE I')
        conn = self.client.transfercmd('retr ' + TESTFN)
        bytes_recv = 0
        rein_sent = 0
        while 1:
            chunk = conn.recv(8192)
            # stop transfer while it isn't finished yet
            if bytes_recv >= 524288: # 2^19
                if not rein_sent:
                    # flush account, expect an error response
                    self.client.sendcmd('user ' + USER)
                    self.assertRaises(ftplib.error_perm, self.client.dir)
                    rein_sent = 1
            if not chunk:
                break
            self.f2.write(chunk)
            bytes_recv += len(chunk)

        # a 226 response is expected once tranfer finishes
        self.assertEqual(self.client.voidresp()[:3], '226')
        # account is still flushed, error response is still expected
        self.assertRaises(ftplib.error_perm, self.client.sendcmd, 'pwd')
        # by logging-in again we should be able to execute a
        # filesystem command
        self.client.sendcmd('pass ' + PASSWD)
        self.client.sendcmd('pwd')
        self.f2.seek(0)
        self.assertEqual(hash(data), hash (self.f2.read()))


class FtpDummyCmds(unittest.TestCase):
    "test: TYPE, STRU, MODE, NOOP, SYST, ALLO, HELP"

    def setUp(self):
        self.server = FTPd()
        self.server.start()
        self.client = ftplib.FTP()        
        self.client.connect(self.server.host, self.server.port)
        self.client.login(USER, PASSWD)

    def tearDown(self):
        self.client.close()
        self.server.stop()

    def test_type(self):
        self.client.sendcmd('type a')
        self.client.sendcmd('type i')
        self.assertRaises(ftplib.error_perm, self.client.sendcmd, 'type')
        self.assertRaises(ftplib.error_perm, self.client.sendcmd, 'type ?!?')

    def test_stru(self):
        self.client.sendcmd('stru f')
        self.client.sendcmd('stru F')
        self.assertRaises(ftplib.error_perm, self.client.sendcmd, 'stru')
        self.assertRaises(ftplib.error_perm, self.client.sendcmd, 'stru ?!?')

    def test_mode(self):
        self.client.sendcmd('mode s')
        self.client.sendcmd('mode S')
        self.assertRaises(ftplib.error_perm, self.client.sendcmd, 'mode')
        self.assertRaises(ftplib.error_perm, self.client.sendcmd, 'mode ?!?')

    def test_noop(self):
        self.client.sendcmd('noop')

    def test_syst(self):
        self.client.sendcmd('syst')

    def test_allo(self):
        self.client.sendcmd('allo x')

    def test_help(self):
        self.client.sendcmd('help')
        cmd = random.choice(ftpserver.proto_cmds.keys())
        self.client.sendcmd('help %s' %cmd)
        self.assertRaises(ftplib.error_perm, self.client.sendcmd, 'help ?!?')

    def test_rest(self):
        # test error conditions only;
        # restored data-transfer is tested later
        self.assertRaises(ftplib.error_perm, self.client.sendcmd, 'rest')
        self.assertRaises(ftplib.error_perm, self.client.sendcmd, 'rest str')
        self.assertRaises(ftplib.error_perm, self.client.sendcmd, 'rest -1')

    def test_opts_feat(self):
        self.assertRaises(ftplib.error_perm, self.client.sendcmd, 'opts')
        self.assertRaises(ftplib.error_perm, self.client.sendcmd, 'opts mlst bad_fact')
        self.assertRaises(ftplib.error_perm, self.client.sendcmd, 'opts mlst type ;')
        self.assertRaises(ftplib.error_perm, self.client.sendcmd, 'opts not_mlst')
        # utility function which used for extracting the MLST "facts"
        # string from the FEAT response
        def mlst():
            resp = self.client.sendcmd('feat')
            return re.search(r'^\s*MLST\s+(\S+)$', resp, re.MULTILINE).group(1)
        # we rely on "type", "perm", "size", and "modify" facts which
        # are those available on all platforms
        self.failUnless('type*;perm*;size*;modify*;' in mlst())
        self.assertEqual(self.client.sendcmd('opts mlst type;'), '200 MLST OPTS type;')
        self.assertEqual(self.client.sendcmd('opts mLSt TypE;'), '200 MLST OPTS type;')
        self.failUnless('type*;perm;size;modify;' in mlst())

        self.assertEqual(self.client.sendcmd('opts mlst'), '200 MLST OPTS ')
        self.failUnless(not '*' in mlst())

        self.assertEqual(self.client.sendcmd('opts mlst fish;cakes;'), '200 MLST OPTS ')
        self.failUnless(not '*' in mlst())
        self.assertEqual(self.client.sendcmd('opts mlst fish;cakes;type;'), \
                                     '200 MLST OPTS type;')
        self.failUnless('type*;perm;size;modify;' in mlst())

    def test_quit(self):
        self.client.sendcmd('quit')


class FtpFsOperations(unittest.TestCase):
    "test: PWD, CWD, CDUP, SIZE, RNFR, RNTO, DELE, MKD, RMD, MDTM, STAT"

    def setUp(self):
        self.server = FTPd()
        self.server.start()
        self.client = ftplib.FTP()
        self.client.connect(self.server.host, self.server.port)
        self.client.login(USER, PASSWD)
        self.tempfile = os.path.basename(open(TESTFN, 'w+b').name)
        self.tempdir = os.path.basename(tempfile.mktemp(dir=HOME))
        os.mkdir(self.tempdir)

    def tearDown(self):
        self.client.close()
        self.server.stop()
        if os.path.exists(self.tempfile):
            os.remove(self.tempfile)
        if os.path.exists(self.tempdir):
            os.rmdir(self.tempdir)        

    def test_cwd(self):
        self.client.cwd(self.tempdir)
        self.assertRaises(ftplib.error_perm, self.client.cwd, 'subtempdir')

    def test_pwd(self):
        self.assertEqual(self.client.pwd(), '/')
        self.client.cwd(self.tempdir)
        self.assertEqual(self.client.pwd(), '/' + self.tempdir)

    def test_cdup(self):
        # ftplib.parse257 function is usually used for parsing the
        # '257' response for a MKD or PWD request returning the
        # directory name in the 257 reply.
        # Although CDUP response code is different (250) we can use
        # parse257 for getting directory name.
        self.client.cwd(self.tempdir)
        dir = ftplib.parse257(self.client.sendcmd('cdup').replace('250', '257'))
        self.assertEqual(dir, '/')
        dir = ftplib.parse257(self.client.sendcmd('cdup').replace('250', '257'))
        self.assertEqual(dir, '/')

    def test_mkd(self):
        tempdir = os.path.basename(tempfile.mktemp(dir=HOME))
        self.client.mkd(tempdir)
        # make sure we can't create directories which already exist
        # (probably not really necessary);
        # let's use a try/except statement to avoid leaving behind
        # orphaned temporary directory in the event of a test failure.
        try:
            self.client.mkd(tempdir)
        except ftplib.error_perm:
            os.rmdir(tempdir)  # ok
        else:
            self.fail('ftplib.error_perm not raised.')

    def test_rmd(self):
        self.client.rmd(self.tempdir)
        self.assertRaises(ftplib.error_perm, self.client.rmd, self.tempfile)
        # make sure we can't remove the root directory
        self.assertRaises(ftplib.error_perm, self.client.rmd, '/')

    def test_dele(self):
        self.client.delete(self.tempfile)
        self.assertRaises(ftplib.error_perm, self.client.delete, self.tempdir)

    def test_rnfr_rnto(self):
        # rename file
        tempname = os.path.basename(tempfile.mktemp(dir=HOME))
        self.client.rename(self.tempfile, tempname)
        self.client.rename(tempname, self.tempfile)
        # rename dir
        tempname = os.path.basename(tempfile.mktemp(dir=HOME))
        self.client.rename(self.tempdir, tempname)
        self.client.rename(tempname, self.tempdir)
        # rnfr/rnto over non-existing paths
        bogus = os.path.basename(tempfile.mktemp(dir=HOME))
        self.assertRaises(ftplib.error_perm, self.client.rename, bogus, '/x')
        self.assertRaises(ftplib.error_perm, self.client.rename, self.tempfile, '/')
        # make sure we can't rename root directory
        self.assertRaises(ftplib.error_perm, self.client.rename, '/', '/x')

    def test_mdtm(self):
        self.client.sendcmd('mdtm ' + self.tempfile)
        # make sure we can't use mdtm against directories
        try:
            self.client.sendcmd('mdtm ' + self.tempdir)
        except ftplib.error_perm, err:
            self.failUnless("not retrievable" in str(err))
        else:
            self.fail('Exception not raised')

    def test_size(self):
        self.client.size(self.tempfile)
        # make sure we can't use size against directories
        try:
            self.client.sendcmd('size ' + self.tempdir)
        except ftplib.error_perm, err:
            self.failUnless("not retrievable" in str(err))
        else:
            self.fail('Exception not raised')

    def test_stat(self):
        self.client.sendcmd('stat')


class FtpRetrieveData(unittest.TestCase):
    "test: RETR, REST, LIST, NLST, argumented STAT"

    def setUp(self):
        self.server = FTPd()
        self.server.start()
        self.client = ftplib.FTP()
        self.client.connect(self.server.host, self.server.port)
        self.client.login(USER, PASSWD)
        self.f1 = open(TESTFN, 'w+b')
        self.f2 = open(TESTFN2, 'w+b')

    def tearDown(self):
        self.client.close()
        self.server.stop()
        if not self.f1.closed:
            self.f1.close()
        if not self.f2.closed:
            self.f2.close()
        os.remove(TESTFN)
        os.remove(TESTFN2)        

    def test_retr(self):
        data = 'abcde12345' * 100000
        self.f1.write(data)
        self.f1.close()
        self.client.retrbinary("retr " + TESTFN, self.f2.write)
        self.f2.seek(0)
        self.assertEqual(hash(data), hash(self.f2.read()))

    def test_restore_on_retr(self):
        data = 'abcde12345' * 100000
        fname_1 = os.path.basename(self.f1.name)
        fname_2 = os.path.basename(self.f2.name)
        self.f1.write(data)
        self.f1.close()

        # look at ftplib.FTP.retrbinary method to understand this mess
        self.client.voidcmd('TYPE I')
        conn = self.client.transfercmd('retr ' + fname_1)
        bytes_recv = 0
        while 1:
            chunk = conn.recv(8192)
            # stop transfer while it isn't finished yet
            if bytes_recv >= 524288: # 2^19
                break
            elif not chunk:
                break
            self.f2.write(chunk)
            bytes_recv += len(chunk)
        conn.close()

        # transfer wasn't finished yet so we expect a 426 response
        self.assertRaises(ftplib.error_temp, self.client.voidresp)

        # resuming transfer by using a marker value greater than the
        # file size stored on the server should result in an error
        # on retr (RFC-1123)
        file_size = self.client.size(fname_1)
        self.client.sendcmd('rest %s' %((file_size + 1)))
        self.assertRaises(ftplib.error_perm, self.client.sendcmd, 'retr ' + fname_1)

        # test resume
        self.client.sendcmd('rest %s' %bytes_recv)
        self.client.retrbinary("retr " + fname_1, self.f2.write)
        self.f2.seek(0)
        self.assertEqual(hash(data), hash (self.f2.read()))

    def _test_listing_cmds(self, cmd):
        """Tests common to LIST NLST and MLSD commands."""
        # assume that no argument has the same meaning of "/"
        l1 = l2 = []
        self.client.retrlines(cmd, l1.append)
        self.client.retrlines(cmd + ' /', l2.append)
        self.assertEqual(l1, l2)
        if cmd.lower() != 'mlsd':
            # if pathname is a file one line is expected
            x = []
            self.client.retrlines('%s ' %cmd + TESTFN, x.append)
            self.assertEqual(len(x), 1)
            self.failUnless(''.join(x).endswith(TESTFN))
        # non-existent path, 550 response is expected
        bogus = os.path.basename(tempfile.mktemp(dir=HOME))
        self.assertRaises(ftplib.error_perm, self.client.retrlines, 
                          '%s ' %cmd + bogus, lambda x: x)
        # for an empty directory we excpect that the data channel is
        # opened anyway and that no data is received
        x = []
        tempdir = os.path.basename(tempfile.mkdtemp(dir=HOME))
        try:
            self.client.retrlines('%s %s' %(cmd, tempdir), x.append)
            self.assertEqual(x, [])
        finally:
            os.rmdir(tempdir)

    def test_nlst(self):
        # common tests
        self._test_listing_cmds('nlst')

    def test_list(self):
        # common tests
        self._test_listing_cmds('list')
        # known incorrect pathname arguments (e.g. old clients) are
        # expected to be treated as if pathname would be == '/'
        l1 = l2 = l3 = l4 = l5 = []
        self.client.retrlines('list /', l1.append)
        self.client.retrlines('list -a', l2.append)
        self.client.retrlines('list -l', l3.append)
        self.client.retrlines('list -al', l4.append)
        self.client.retrlines('list -la', l5.append)
        tot = (l1, l2, l3, l4, l5)
        for x in range(len(tot) - 1):
            self.assertEqual(tot[x], tot[x+1])

    def test_mlst(self):
        # utility function for extracting the line of interest
        mlstline = lambda cmd: self.client.voidcmd(cmd).split('\n')[1]

        # the fact set must be preceded by a space
        self.failUnless(mlstline('mlst').startswith(' '))
        # where TVFS is supported, a fully qualified pathname is expected
        self.failUnless(mlstline('mlst ' + TESTFN).endswith('/' + TESTFN))
        self.failUnless(mlstline('mlst').endswith('/'))
        # assume that no argument has the same meaning of "/"
        self.assertEqual(mlstline('mlst'), mlstline('mlst /'))
        # non-existent path
        bogus = os.path.basename(tempfile.mktemp(dir=HOME))
        self.assertRaises(ftplib.error_perm, mlstline, bogus)
        # test file/dir notations
        self.failUnless('type=dir' in mlstline('mlst'))
        self.failUnless('type=file' in mlstline('mlst ' + TESTFN))
        # let's add some tests for OPTS command
        self.client.sendcmd('opts mlst type;')
        self.assertEqual(mlstline('mlst'), ' type=dir; /')
        # where no facts are present, two leading spaces before the
        # pathname are required (RFC-3659)
        self.client.sendcmd('opts mlst')
        self.assertEqual(mlstline('mlst'), '  /')

    def test_mlsd(self):
        # common tests
        self._test_listing_cmds('mlsd')
        dir = os.path.basename(tempfile.mkdtemp(dir=HOME))
        try:
            try:
                self.client.retrlines('mlsd ' + TESTFN, lambda x: x)
            except ftplib.error_perm, resp:
                # if path is a file a 501 response code is expected
                self.assertEqual(str(resp)[0:3], "501")
            else:
                self.fail("Exception not raised")
        finally:
            os.rmdir(dir)

    def test_stat(self):
        # test argumented STAT which is equal to LIST plus globbing support
        self.client.sendcmd('stat *')
        self.client.sendcmd('stat /')
        self.client.sendcmd('stat ' + TESTFN)
        self.failUnless('recursion not supported' in self.client.sendcmd('stat /*/*'))
        bogus = os.path.basename(tempfile.mktemp(dir=HOME))
        self.assertRaises(ftplib.error_perm, self.client.sendcmd, 'stat ' + bogus)


class FtpAbort(unittest.TestCase):
    "test: ABOR"

    def setUp(self):
        self.server = FTPd()
        self.server.start()
        self.client = ftplib.FTP()
        self.client.connect(self.server.host, self.server.port)
        self.client.login(USER, PASSWD)
        self.f1 = open(TESTFN, 'w+b')
        self.f2 = open(TESTFN2, 'w+b')

    def tearDown(self):
        self.client.close()
        self.server.stop()
        if not self.f1.closed:
            self.f1.close()
        if not self.f2.closed:
            self.f2.close()
        os.remove(self.f1.name)
        os.remove(self.f2.name)        

    def test_abor_no_data(self):
        # Case 1: ABOR while no data channel is opened: respond with 225.
        resp = self.client.sendcmd('ABOR')
        self.failUnlessEqual('225 No transfer to abort.', resp)

    def test_abor_pasv(self):
        # Case 2: user sends a PASV, a data-channel socket is listening
        # but not connected, and ABOR is sent: close listening data
        # socket, respond with 225.
        self.client.sendcmd('PASV')
        respcode = self.client.sendcmd('ABOR')[:3]
        self.failUnlessEqual('225', respcode)

    def test_abor_port(self):
        # Case 3: data channel opened with PASV or PORT, but ABOR sent
        # before a data transfer has been started: close data channel,
        # respond with 225
        self.client.makeport()
        respcode = self.client.sendcmd('ABOR')[:3]
        self.failUnlessEqual('225', respcode)

    def test_abor(self):
        # Case 4: ABOR while a data transfer on DTP channel is in
        # progress: close data channel, respond with 426, respond
        # with 226.
        data = 'abcde12345' * 100000
        self.f1.write(data)
        self.f1.close()

        # this ugly loop construct is to simulate an interrupted
        # transfer since ftplib doesn't like running storbinary()
        # in a separate thread
        self.client.voidcmd('TYPE I')
        conn = self.client.transfercmd('retr ' + TESTFN)
        bytes_recv = 0
        while 1:
            chunk = conn.recv(8192)
            # stop transfer while it isn't finished yet
            if bytes_recv >= 524288: # 2^19
                break
            elif not chunk:
                break
            self.f2.write(chunk)
            bytes_recv += len(chunk)
        self.client.putcmd('ABOR')

        # transfer isn't finished yet so ftpd should respond with 426
        self.assertRaises(ftplib.error_temp, self.client.voidresp)

        # transfer successfully aborted, so should now respond with a 226
        self.failUnlessEqual('226', self.client.voidresp()[:3])


class FtpStoreData(unittest.TestCase):
    "test: STOR, STOU, APPE, REST"

    def setUp(self):
        self.server = FTPd()
        self.server.start()
        self.client = ftplib.FTP()
        self.client.connect(self.server.host, self.server.port)
        self.client.login(USER, PASSWD)
        self.f1 = open(TESTFN, 'w+b')
        self.f2 = open(TESTFN2, 'w+b')

    def tearDown(self):
        self.client.close()
        self.server.stop()
        if not self.f1.closed:
            self.f1.close()
        if not self.f2.closed:
            self.f2.close()
        os.remove(TESTFN)
        os.remove(TESTFN2)        

    def test_stor(self):
        # TESTFN3 is the remote file name
        try:
            data = 'abcde12345' * 100000
            self.f1.write(data)
            self.f1.seek(0)
            self.client.storbinary('stor ' + TESTFN3, self.f1)
            self.client.retrbinary('retr ' + TESTFN3, self.f2.write)
            self.f2.seek(0)
            self.assertEqual(hash(data), hash (self.f2.read()))
        finally:
            # we do not use os.remove because file could be still
            # locked by ftpd thread
            if os.path.exists(TESTFN3):
                self.client.delete(TESTFN3)

    def test_stou(self):
        data = 'abcde12345' * 100000
        self.f1.write(data)
        self.f1.seek(0)

        self.client.voidcmd('TYPE I')
        # filename comes in as "1xx FILE: <filename>"
        filename = self.client.sendcmd('stou').split('FILE: ')[1]
        try:
            sock = self.client.makeport()
            conn, sockaddr = sock.accept()
            while 1:
                buf = self.f1.read(8192)
                if not buf:
                    break
                conn.sendall(buf)
            conn.close()
            # transfer finished, a 226 response is expected
            self.client.voidresp()
            self.client.retrbinary('retr ' + filename, self.f2.write)
            self.f2.seek(0)
            self.assertEqual(hash(data), hash (self.f2.read()))
        finally:
            # we do not use os.remove because file could be
            # still locked by ftpd thread
            if os.path.exists(filename):
                self.client.delete(filename)

    def test_stou_rest(self):
        # watch for STOU preceded by REST, which makes no sense.
        self.client.sendcmd('rest 10')
        self.assertRaises(ftplib.error_temp, self.client.sendcmd, 'stou')

    def test_appe(self):
        # TESTFN3 is the remote file name
        try:
            data1 = 'abcde12345' * 100000
            self.f1.write(data1)
            self.f1.seek(0)
            self.client.storbinary('stor ' + TESTFN3, self.f1)

            data2 = 'fghil67890' * 100000
            self.f1.write(data2)
            self.f1.seek(self.client.size(TESTFN3))
            self.client.storbinary('appe ' + TESTFN3, self.f1)

            self.client.retrbinary("retr " + TESTFN3, self.f2.write)
            self.f2.seek(0)
            self.assertEqual(hash(data1 + data2), hash (self.f2.read()))
        finally:
            # we do not use os.remove because file could be still
            # locked by ftpd thread
            if os.path.exists(TESTFN3):
                self.client.delete(TESTFN3)

    def test_appe_rest(self):
        # watch for APPE preceded by REST, which makes no sense.
        self.client.sendcmd('rest 10')
        self.assertRaises(ftplib.error_perm, self.client.sendcmd, 'appe x')

    def test_rest_on_stor(self):
        # TESTFN3 is the remote file name
        data = 'abcde12345' * 100000
        self.f1.write(data)
        self.f1.seek(0)

        self.client.voidcmd('TYPE I')
        conn = self.client.transfercmd('stor ' + TESTFN3)
        bytes_sent = 0
        while 1:
            chunk = self.f1.read(8192)
            conn.sendall(chunk)
            bytes_sent += len(chunk)
            # stop transfer while it isn't finished yet
            if bytes_sent >= 524288: # 2^19
                break
            elif not chunk:
                break
        conn.close()
        # transfer wasn't finished yet so we expect a 426 response
        self.client.voidresp()

        # resuming transfer by using a marker value greater than the
        # file size stored on the server should result in an error
        # on stor
        file_size = self.client.size(TESTFN3)
        self.assertEqual(file_size, bytes_sent)
        self.client.sendcmd('rest %s' %((file_size + 1)))
        self.assertRaises(ftplib.error_perm, self.client.sendcmd, 'stor ' + TESTFN3)

        self.client.sendcmd('rest %s' %bytes_sent)
        self.client.storbinary('stor ' + TESTFN3, self.f1)

        self.client.retrbinary('retr ' + TESTFN3, self.f2.write)
        self.f1.seek(0)
        self.f2.seek(0)
        self.assertEqual(hash(self.f1.read()), hash(self.f2.read()))
        self.client.delete(TESTFN3)

        
class FTPd(threading.Thread):
    """A threaded FTP server used for running tests."""

    def __init__(self, host=HOST, port=0, verbose=False):
        threading.Thread.__init__(self)
        self.active = False
        if not verbose:
            ftpserver.log = ftpserver.logline = lambda x: x
        self.authorizer = ftpserver.DummyAuthorizer()
        self.authorizer.user_table = {}
        self.authorizer.add_user(USER, PASSWD, HOME, perm='elradfmw')  # full perms
        self.authorizer.add_anonymous(HOME)
        self.handler = ftpserver.FTPHandler
        self.handler.authorizer = self.authorizer        
        self.server = ftpserver.FTPServer((host, port), self.handler)
        self.host, self.port = self.server.socket.getsockname()[:2]
        self.active_lock = threading.Lock()

    def start(self):
        assert not self.active
        self.__flag = threading.Event()
        threading.Thread.start(self)
        self.__flag.wait()

    def run(self):
        # hack for granting backward compatibility with Python 2.3
        # where asyncore.loop() doesn't provide the 'count' argument
        import inspect, asyncore
        if 'count' in inspect.getargspec(asyncore.loop)[0]:
            poller = self.server.serve_forever
            kwargs = {"timeout":0.001, "count":1}
        else:
            poller = asyncore.poll
            kwargs = {"timeout":0.001}
        self.active = True
        self.__flag.set()        
        while self.active:
            self.active_lock.acquire()            
            poller(**kwargs)
            self.active_lock.release()
        self.server.close()

    def stop(self):
        assert self.active
        self.active = False
        self.join()


def remove_test_files():
    "Convenience function for removing temporary test files"
    for file in [TESTFN, TESTFN2, TESTFN3]:
        try:
            os.remove(file)
        except os.error:
            pass

def test_main(tests=None):
    test_suite = unittest.TestSuite()
    if tests is None:
        tests = [AbstractedFSClass,
                 DummyAuthorizerClass,
                 FtpAuthentication,
                 FtpDummyCmds,
                 FtpFsOperations,
                 FtpRetrieveData,
                 FtpAbort,
                 FtpStoreData
                 ]
    for test in tests:
        test_suite.addTest(unittest.makeSuite(test))
    remove_test_files()
    unittest.TextTestRunner(verbosity=2).run(test_suite)
    remove_test_files()


if __name__ == '__main__':
    test_main()
