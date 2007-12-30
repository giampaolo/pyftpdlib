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


import threading
import unittest
import socket
import os
import atexit
import time
import tempfile
import ftplib
import random
import warnings
from test import test_support

from pyftpdlib import ftpserver

__release__ = 'pyftpdlib 0.2.1'


# This test suite has been run successfully on the following systems:

# -------------------------------------------------------
#  System                          | Python version
# -------------------------------------------------------
#  Windows XP prof sp2             | 2.3, 2.4, 2.5, 2.6a
#  Linux CentOS 2.6.20.15          | 2.4
#  Linux Ubuntu 2.6.20-15          | 2.4, 2.5
#  Linux Debian 2.4.27-2-386       | 2.3.5
#  OS X 10.4.10                    | 2.3, 2.4, 2.5
#  FreeBSD 6.0, 7.0                | 2.4, 2.5
# -------------------------------------------------------


# TODO:
# - Test QUIT while a transfer is in progress.
# - Test data transfer in ASCII mode.
# - Test FTPHandler.masquearade_address and FTPHandler.passive_ports


TESTFN = test_support.TESTFN
TESTFN2 = TESTFN + '2'
TESTFN3 = TESTFN + '3'


class AbstractedFSClass(unittest.TestCase):
    """Test for conversion utility methods of AbstractedFS class."""

    def test_ftpnorm(self):
        """Tests for ftpnorm method."""
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
        ae(fs.ftpnorm('//'), '/') # UNC paths must be collapsed

    def test_ftp2fs(self):
        """Tests for ftp2fs method."""
        ae = self.assertEquals
        fs = ftpserver.AbstractedFS()
        join = lambda x,y: os.path.join(x, y.replace('/', os.sep))

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
            ae(fs.ftp2fs('//a'), join(root, 'a')) # UNC paths must be collapsed

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
        """Tests for fs2ftp method."""
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
            goforit('/home/user')
            goforit('/')
            fs.root = r'/home/user'
            ae(fs.fs2ftp('/home'), '/')
            ae(fs.fs2ftp('/'), '/')
            ae(fs.fs2ftp('/home/userx'), '/')
        else:
            # os.sep == ':'? Don't know... let's try it anyway
            goforit(os.getcwd())

    def test_validpath(self):
        """Tests for validpath method."""
        fs = ftpserver.AbstractedFS()
        fs.root = home
        self.failUnless(fs.validpath(home))
        self.failUnless(fs.validpath(home + '/'))
        self.failIf(fs.validpath(home + 'xxx'))
        
    if hasattr(os, 'symlink'):
        # Tests for validpath on systems supporting symbolic links

        def _safe_remove(self, path):
            # convenience function for removing temporary files
            try:
                os.remove(path)
            except os.error:
                pass
        
        def test_validpath_validlink(self):
            """Test validpath by issuing a symlink pointing to a path
            inside the root directory."""
            fs = ftpserver.AbstractedFS()
            fs.root = home
            try:
                open(TESTFN, 'w')
                os.symlink(TESTFN, TESTFN2)
                self.failUnless(fs.validpath(TESTFN))
            finally:
                self._safe_remove(TESTFN)
                self._safe_remove(TESTFN2)

        def test_validpath_external_symlink(self):
            """Test validpath by issuing a symlink pointing to a path
            outside the root directory."""
            fs = ftpserver.AbstractedFS()
            fs.root = home           
            try:
                # tempfile should create our file in /tmp directory
                # which should be outside the user root. If it is not
                # we just skip the test.
                file = tempfile.NamedTemporaryFile()
                if home == os.path.dirname(file.name):
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
        auth.add_user(user, pwd, home)
        auth.add_anonymous(home)
        # check credentials
        self.failUnless(auth.validate_authentication(user, pwd))
        self.failIf(auth.validate_authentication(user, 'wrongpwd'))
        # remove them
        auth.remove_user(user)
        auth.remove_user('anonymous')

        # raise exc if user does not exists
        self.assertRaises(KeyError, auth.remove_user, user)
        # raise exc if path does not exist
        self.assertRaises(ftpserver.AuthorizerError, auth.add_user, user,
                            pwd, '?:\\')
        self.assertRaises(ftpserver.AuthorizerError, auth.add_anonymous, '?:\\')
        # raise exc if user already exists
        auth.add_user(user, pwd, home)
        auth.add_anonymous(home)
        self.assertRaises(ftpserver.AuthorizerError, auth.add_user, user,
                            pwd, home)
        self.assertRaises(ftpserver.AuthorizerError, auth.add_anonymous, home)
        auth.remove_user(user)
        auth.remove_user('anonymous')

        # raise on wrong permission
        self.assertRaises(ftpserver.AuthorizerError, auth.add_user, user, pwd,
                            home, perm='?')
        self.assertRaises(ftpserver.AuthorizerError, auth.add_anonymous, home,
                            perm='?')
        # expect warning on write permissions assigned to anonymous user
        for x in "adfmw":
            self.assertRaises(RuntimeWarning, auth.add_anonymous, home, perm=x)


class FtpAuthentication(unittest.TestCase):
    "test: USER, PASS, REIN."

    def setUp(self):
        global ftp
        ftp = ftplib.FTP()
        ftp.connect(host=host, port=port)
        self.f1 = open(TESTFN, 'w+b')
        self.f2 = open(TESTFN2, 'w+b')

    def tearDown(self):
        ftp.close()
        if not self.f1.closed:
            self.f1.close()
        if not self.f2.closed:
            self.f2.close()
        os.remove(TESTFN)
        os.remove(TESTFN2)

    def test_auth_ok(self):
        ftp.login(user=user, passwd=pwd)

    def test_auth_failed(self):
        self.failUnlessRaises(ftplib.error_perm, ftp.login, user, passwd='wrong')

    def test_anon_auth(self):
        ftp.login(user='anonymous', passwd='anon@')
        ftp.login(user='AnonYmoUs', passwd='anon@')
        ftp.login(user='anonymous', passwd='')

    def test_max_auth(self):
        self.failUnlessRaises(ftplib.error_perm, ftp.login, user, passwd='wrong')
        self.failUnlessRaises(ftplib.error_perm, ftp.login, user, passwd='wrong')
        self.failUnlessRaises(ftplib.error_perm, ftp.login, user, passwd='wrong')
        # If authentication fails for 3 times ftpd disconnects the client.
        # We can check if this happens by using ftp.sendcmd() on the 'dead'
        # socket object.  If socket object is really closed it should be raised
        # socket.error exception (Windows) or EOFError exception (Linux).
        self.failUnlessRaises((socket.error, EOFError), ftp.sendcmd, '')

    def test_rein(self):
        ftp.login(user=user, passwd=pwd)
        ftp.sendcmd('rein')
        # user is not yet authenticated, a permission error response is expected
        self.assertRaises(ftplib.error_perm, ftp.sendcmd, 'pwd')
        # by logging-in again we should be able to execute a file-system command
        ftp.login(user=user, passwd=pwd)
        ftp.sendcmd('pwd')

    def test_rein_during_transfer(self):
        ftp.login(user=user, passwd=pwd)
        data = 'abcde12345' * 100000
        self.f1.write(data)
        self.f1.close()

        ftp.voidcmd('TYPE I')
        conn = ftp.transfercmd('retr ' + TESTFN)
        bytes_recv = 0
        rein_sent = 0
        while 1:
            chunk = conn.recv(8192)
            # stop transfer while it isn't finished yet
            if bytes_recv >= 524288: # 2^19
                if not rein_sent:
                    # flush account, expect an error response
                    ftp.sendcmd('rein')
                    self.assertRaises(ftplib.error_perm, ftp.sendcmd, 'pwd')
                    rein_sent = 1
            if not chunk:
                break
            self.f2.write(chunk)
            bytes_recv += len(chunk)

        # a 226 response is expected once tranfer finishes
        self.assertEqual(ftp.voidresp()[:3], '226')
        # account is still flushed, error response is still expected
        self.assertRaises(ftplib.error_perm, ftp.sendcmd, 'size ' + TESTFN)
        # by logging-in again we should be able to execute a filesystem command
        ftp.login(user=user, passwd=pwd)
        ftp.sendcmd('pwd')
        self.f2.seek(0)
        self.assertEqual(hash(data), hash (self.f2.read()))

    def test_user(self):
        """Test USER while already authenticated and no transfer
        is in progress.
        """
        ftp.login(user=user, passwd=pwd)
        ftp.sendcmd('user ' + user)  # authentication flushed
        self.assertRaises(ftplib.error_perm, ftp.sendcmd, 'pwd')
        ftp.sendcmd('pass ' + pwd)
        ftp.sendcmd('pwd')

    def test_user_on_transfer(self):
        """Test USER while already authenticated and a transfer is
        in progress.
        """
        ftp.login(user=user, passwd=pwd)
        data = 'abcde12345' * 100000
        self.f1.write(data)
        self.f1.close()

        ftp.voidcmd('TYPE I')
        conn = ftp.transfercmd('retr ' + TESTFN)
        bytes_recv = 0
        rein_sent = 0
        while 1:
            chunk = conn.recv(8192)
            # stop transfer while it isn't finished yet
            if bytes_recv >= 524288: # 2^19
                if not rein_sent:
                    # flush account, expect an error response
                    ftp.sendcmd('user ' + user)
                    self.assertRaises(ftplib.error_perm, ftp.sendcmd, 'pwd')
                    rein_sent = 1
            if not chunk:
                break
            self.f2.write(chunk)
            bytes_recv += len(chunk)

        # a 226 response is expected once tranfer finishes
        self.assertEqual(ftp.voidresp()[:3], '226')
        # account is still flushed, error response is still expected
        self.assertRaises(ftplib.error_perm, ftp.sendcmd, 'pwd')
        # by logging-in again we should be able to execute a filesystem command
        ftp.sendcmd('pass ' + pwd)
        ftp.sendcmd('pwd')
        self.f2.seek(0)
        self.assertEqual(hash(data), hash (self.f2.read()))


class FtpDummyCmds(unittest.TestCase):
    "test: TYPE, STRU, MODE, NOOP, SYST, ALLO, HELP"

    def setUp(self):
        global ftp
        ftp = ftplib.FTP()
        ftp.connect(host=host, port=port)
        ftp.login(user=user, passwd=pwd)

    def tearDown(self):
        ftp.close()

    def test_type(self):
        ftp.sendcmd('type a')
        ftp.sendcmd('type i')
        self.failUnlessRaises(ftplib.error_perm, ftp.sendcmd, 'type')
        self.failUnlessRaises(ftplib.error_perm, ftp.sendcmd, 'type ?!?')

    def test_stru(self):
        ftp.sendcmd('stru f')
        ftp.sendcmd('stru F')
        self.failUnlessRaises(ftplib.error_perm, ftp.sendcmd, 'stru')
        self.failUnlessRaises(ftplib.error_perm, ftp.sendcmd, 'stru ?!?')

    def test_mode(self):
        ftp.sendcmd('mode s')
        ftp.sendcmd('mode S')
        self.failUnlessRaises(ftplib.error_perm, ftp.sendcmd, 'mode')
        self.failUnlessRaises(ftplib.error_perm, ftp.sendcmd, 'mode ?!?')

    def test_noop(self):
        ftp.sendcmd('noop')

    def test_syst(self):
        ftp.sendcmd('syst')

    def test_allo(self):
        ftp.sendcmd('allo x')

    def test_help(self):
        ftp.sendcmd('help')
        cmd = random.choice(ftpserver.proto_cmds.keys())
        ftp.sendcmd('help %s' %cmd)
        self.failUnlessRaises(ftplib.error_perm, ftp.sendcmd, 'help ?!?')

    def test_rest(self):
        # just test rest's semantic without using data-transfer
        self.failUnlessRaises(ftplib.error_perm, ftp.sendcmd, 'rest')
        self.failUnlessRaises(ftplib.error_perm, ftp.sendcmd, 'rest str')
        self.failUnlessRaises(ftplib.error_perm, ftp.sendcmd, 'rest -1')

    def test_feat(self):
        ftp.sendcmd('feat')

    def test_quit(self):
        ftp.sendcmd('quit')


class FtpFsOperations(unittest.TestCase):
    "test: PWD, CWD, CDUP, SIZE, RNFR, RNTO, DELE, MKD, RMD, MDTM, STAT"

    def setUp(self):
        global ftp
        ftp = ftplib.FTP()
        ftp.connect(host=host, port=port)
        ftp.login(user=user, passwd=pwd)
        self.tempfile = os.path.basename(open(TESTFN, 'w+b').name)
        self.tempdir = os.path.basename(tempfile.mktemp(dir=home))
        os.mkdir(self.tempdir)

    def tearDown(self):
        ftp.close()
        if os.path.exists(self.tempfile):
            os.remove(self.tempfile)
        if os.path.exists(self.tempdir):
            os.rmdir(self.tempdir)

    def test_cwd(self):
        ftp.cwd(self.tempdir)
        self.assertRaises(ftplib.error_perm, ftp.cwd, 'subtempdir')

    def test_pwd(self):
        self.assertEqual(ftp.pwd(), '/')
        ftp.cwd(self.tempdir)
        self.assertEqual(ftp.pwd(), '/' + self.tempdir)

    def test_cdup(self):
        # ftplib.parse257 function is usually used for parsing the
        # '257' response for a MKD or PWD request returning the
        # directory name in the 257 reply.
        # Although CDUP response code is different (250) we can use
        # parse257 for getting directory name.
        ftp.cwd(self.tempdir)
        dir = ftplib.parse257(ftp.sendcmd('cdup').replace('250', '257'))
        self.assertEqual(dir, '/')
        dir = ftplib.parse257(ftp.sendcmd('cdup').replace('250', '257'))
        self.assertEqual(dir, '/')

    def test_mkd(self):
        tempdir = os.path.basename(tempfile.mktemp(dir=home))
        ftp.mkd(tempdir)
        # make sure we can't create directories which already exist
        # (probably not really necessary);
        # let's use a try/except statement to avoid leaving behind
        # orphaned temporary directory in the event of a test failure.
        try:
            ftp.mkd(tempdir)
        except ftplib.error_perm, err:
            os.rmdir(tempdir)  # ok
        else:
            self.fail('ftplib.error_perm not raised.')

    def test_rmd(self):
        ftp.rmd(self.tempdir)
        self.assertRaises(ftplib.error_perm, ftp.rmd, self.tempfile)
        # make sure we can't use rmd against root directory
        self.assertRaises(ftplib.error_perm, ftp.rmd, '/')

    def test_dele(self):
        ftp.delete(self.tempfile)
        self.assertRaises(ftplib.error_perm, ftp.delete, self.tempdir)

    def test_rnfr_rnto(self):
        # rename file
        tempname = os.path.basename(tempfile.mktemp(dir=home))
        ftp.rename(self.tempfile, tempname)
        ftp.rename(tempname, self.tempfile)
        # rename dir
        tempname = os.path.basename(tempfile.mktemp(dir=home))
        ftp.rename(self.tempdir, tempname)
        ftp.rename(tempname, self.tempdir)
        # rnfr/rnto over non-existing paths
        bogus = os.path.basename(tempfile.mktemp(dir=home))
        self.assertRaises(ftplib.error_perm, ftp.rename, bogus, '/x')
        self.assertRaises(ftplib.error_perm, ftp.rename, self.tempfile, '/')
        # make sure we can't rename root directory, just to be safe,
        # maybe not really necessary...
        self.assertRaises(ftplib.error_perm, ftp.rename, '/', '/x')

    def test_mdtm(self):
        ftp.sendcmd('mdtm ' + self.tempfile)
        # make sure we can't use mdtm against directories
        self.assertRaises(ftplib.error_perm, ftp.sendcmd, 'mdtm ' + self.tempdir)

    def test_size(self):
        ftp.size(self.tempfile)
        # make sure we can't use size against directories
        self.assertRaises(ftplib.error_perm, ftp.size, self.tempdir)

    def test_stat(self):
        ftp.sendcmd('stat')


class FtpRetrieveData(unittest.TestCase):
    "test: RETR, REST, LIST, NLST, argumented STAT"

    def setUp(self):
        global ftp
        ftp = ftplib.FTP()
        ftp.connect(host=host, port=port)
        ftp.login(user=user, passwd=pwd)
        self.f1 = open(TESTFN, 'w+b')
        self.f2 = open(TESTFN2, 'w+b')

    def tearDown(self):
        ftp.close()
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
        ftp.retrbinary("retr " + TESTFN, self.f2.write)
        self.f2.seek(0)
        self.assertEqual(hash(data), hash(self.f2.read()))

    def test_restore_on_retr(self):
        data = 'abcde12345' * 100000
        fname_1 = os.path.basename(self.f1.name)
        fname_2 = os.path.basename(self.f2.name)
        self.f1.write(data)
        self.f1.close()

        # look at ftplib.FTP.retrbinary method to understand this mess
        ftp.voidcmd('TYPE I')
        conn = ftp.transfercmd('retr ' + fname_1)
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
        self.failUnlessRaises(ftplib.error_temp, ftp.voidresp)

        # resuming transfer by using a marker value greater than the file
        # size stored on the server should result in an error on retr
        file_size = ftp.size(fname_1)
        ftp.sendcmd('rest %s' %((file_size + 1)))
        self.assertRaises(ftplib.error_perm, ftp.sendcmd, 'retr ' + fname_1)

        # test resume
        ftp.sendcmd('rest %s' %bytes_recv)
        ftp.retrbinary("retr " + fname_1, self.f2.write)
        self.f2.seek(0)
        self.assertEqual(hash(data), hash (self.f2.read()))

    def _test_listing_cmds(self, cmd):
        """Tests common to LIST NLST and MLSD commands."""
        # assume that no argument has the same meaning of "/"
        l1 = l2 = []
        ftp.retrlines(cmd, l1.append)
        ftp.retrlines(cmd + ' /', l2.append)
        self.assertEqual(l1, l2)
        if not cmd.lower() in 'mlsd':
            # if pathname is a file one line is expected
            x = []
            ftp.retrlines('%s ' %cmd + TESTFN, x.append)
            self.assertEqual(len(x), 1)
            self.failUnless(''.join(x).endswith(TESTFN))
        # non-existent path
        bogus = os.path.basename(tempfile.mktemp(dir=home))
        self.assertRaises(ftplib.error_perm, ftp.retrlines, '%s ' %cmd + bogus,
                          lambda x: x)
        # for an empty directory we excpect that the data channel is
        # opened anyway and that no data is received
        x = []
        tempdir = os.path.basename(tempfile.mkdtemp(dir=home))
        try:
            ftp.retrlines('%s %s' %(cmd, tempdir), x.append)
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
        ftp.retrlines('list /', l1.append)
        ftp.retrlines('list -a', l2.append)
        ftp.retrlines('list -l', l3.append)
        ftp.retrlines('list -al', l4.append)
        ftp.retrlines('list -la', l5.append)
        tot = (l1, l2, l3, l4, l5)
        for x in range(len(tot) - 1):
            self.assertEqual(tot[x], tot[x+1])
            
    def test_mlst(self):
        # utility function for extracting the line of interest
        mlstline = lambda cmd: ftp.voidcmd(cmd).split('\n')[1]

        # the fact set must be preceded by a space
        self.failUnless(mlstline('mlst').startswith(' '))
        # where TVFS is supported, a fully qualified pathname is expected
        self.failUnless(mlstline('mlst ' + TESTFN).endswith('/' + TESTFN))
        self.failUnless(mlstline('mlst').endswith('/'))
        # assume that no argument has the same meaning of "/"
        self.assertEqual(mlstline('mlst'), mlstline('mlst /'))
        # non-existent path
        bogus = os.path.basename(tempfile.mktemp(dir=home))
        self.assertRaises(ftplib.error_perm, mlstline, bogus)
        # test file/dir notations
        self.failUnless('type=dir' in mlstline('mlst'))
        self.failUnless('type=file' in mlstline('mlst ' + TESTFN))
        
    def test_mlsd(self):
        # common tests
        self._test_listing_cmds('mlsd')
        # if path is a file a 501 response code is expected
        dir = os.path.basename(tempfile.mkdtemp(dir=home))
        try:
            try:
                ftp.retrlines('mlsd ' + TESTFN, lambda x: x)
            except ftplib.error_perm, resp:
                self.assertEqual(str(resp)[0:3], "501")
            else:
                self.fail("Exception not raised")
        finally:
            os.rmdir(dir)

    def test_stat(self):
        # test argumented STAT which is equal to LIST plus
        # globbing support
        ftp.sendcmd('stat *')
        ftp.sendcmd('stat /')
        ftp.sendcmd('stat ' + TESTFN)
        self.failUnless('recursion not supported' in ftp.sendcmd('stat /*/*'))
        bogus = os.path.basename(tempfile.mktemp(dir=home))
        self.assertRaises(ftplib.error_perm, ftp.sendcmd, 'stat ' + bogus)


class FtpAbort(unittest.TestCase):
    "test: ABOR"

    def setUp(self):
        global ftp
        ftp = ftplib.FTP()
        ftp.connect(host=host, port=port)
        ftp.login(user=user, passwd=pwd)
        self.f1 = open(TESTFN, 'w+b')
        self.f2 = open(TESTFN2, 'w+b')

    def tearDown(self):
        ftp.close()
        if not self.f1.closed:
            self.f1.close()
        if not self.f2.closed:
            self.f2.close()
        os.remove(self.f1.name)
        os.remove(self.f2.name)

    def test_abor_no_data(self):
        # Case 1: ABOR while no data channel is opened: respond with 225.
        resp = ftp.sendcmd('ABOR')
        self.failUnlessEqual('225 No transfer to abort.', resp)

    def test_abor_pasv(self):
        # Case 2: user sends a PASV, a data-channel socket is listening
        # but not connected, and ABOR is sent: close listening data
        # socket, respond with 225.
        ftp.sendcmd('PASV')
        respcode = ftp.sendcmd('ABOR')[:3]
        self.failUnlessEqual('225', respcode)

    def test_abor_port(self):
        # Case 3: data channel opened with PASV or PORT, but ABOR sent
        # before a data transfer has been started: close data channel,
        # respond with 225
        ftp.makeport()
        respcode = ftp.sendcmd('ABOR')[:3]
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
        ftp.voidcmd('TYPE I')
        conn = ftp.transfercmd('retr ' + TESTFN)
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
        ftp.putcmd('ABOR')

        # transfer isn't finished yet so ftpd should respond with 426
        self.failUnlessRaises(ftplib.error_temp, ftp.voidresp)

        # transfer successfully aborted, so should now respond with a 226
        self.failUnlessEqual('226', ftp.voidresp()[:3])


class FtpStoreData(unittest.TestCase):
    "test: STOR, STOU, APPE, REST"

    def setUp(self):
        global ftp
        ftp = ftplib.FTP()
        ftp.connect(host=host, port=port)
        ftp.login(user=user, passwd=pwd)
        self.f1 = open(TESTFN, 'w+b')
        self.f2 = open(TESTFN2, 'w+b')

    def tearDown(self):
        ftp.close()
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
            ftp.storbinary('stor ' + TESTFN3, self.f1)
            ftp.retrbinary('retr ' + TESTFN3, self.f2.write)
            self.f2.seek(0)
            self.assertEqual(hash(data), hash (self.f2.read()))
        finally:
            # we do not use os.remove because file could be still
            # locked by ftpd thread
            if os.path.exists(TESTFN3):
                ftp.delete(TESTFN3)

    def test_stou(self):
        data = 'abcde12345' * 100000
        self.f1.write(data)
        self.f1.seek(0)

        ftp.voidcmd('TYPE I')
        # filename comes in as 1xx FILE: <filename>
        try:
            filename = ftp.sendcmd('stou').split('FILE: ')[1]
            sock = ftp.makeport()
            conn, sockaddr = sock.accept()
            while 1:
                buf = self.f1.read(8192)
                if not buf:
                    break
                conn.sendall(buf)
            conn.close()
            # transfer finished, a 226 response is expected
            ftp.voidresp()
            ftp.retrbinary('retr ' + filename, self.f2.write)
            self.f2.seek(0)
            self.assertEqual(hash(data), hash (self.f2.read()))
        finally:
            # we do not use os.remove because file could be
            # still locked by ftpd thread
            try:
                if os.path.exists(filename):
                    ftp.delete(filename)
            except NameError:
                pass

    def test_stou_rest(self):
        # watch for STOU preceded by REST, which makes no sense.
        ftp.sendcmd('rest 10')
        self.assertRaises(ftplib.error_perm, ftp.sendcmd, 'stou')

    def test_appe(self):
        # TESTFN3 is the remote file name
        try:
            data1 = 'abcde12345' * 100000
            self.f1.write(data1)
            self.f1.seek(0)
            ftp.storbinary('stor ' + TESTFN3, self.f1)

            data2 = 'fghil67890' * 100000
            self.f1.write(data2)
            self.f1.seek(ftp.size(TESTFN3))
            ftp.storbinary('appe ' + TESTFN3, self.f1)

            ftp.retrbinary("retr " + TESTFN3, self.f2.write)
            self.f2.seek(0)
            self.assertEqual(hash(data1 + data2), hash (self.f2.read()))
        finally:
            # we do not use os.remove because file could be still
            # locked by ftpd thread
            if os.path.exists(TESTFN3):
                ftp.delete(TESTFN3)

    def test_appe_rest(self):
        # watch for APPE preceded by REST, which makes no sense.
        ftp.sendcmd('rest 10')
        self.assertRaises(ftplib.error_perm, ftp.sendcmd, 'appe x')

    def test_rest_on_stor(self):
        # TESTFN3 is the remote file name
        data = 'abcde12345' * 100000
        self.f1.write(data)
        self.f1.seek(0)

        ftp.voidcmd('TYPE I')
        conn = ftp.transfercmd('stor ' + TESTFN3)
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
        ftp.voidresp()

        # resuming transfer by using a marker value greater than the file
        # size stored on the server should result in an error on stor
        file_size = ftp.size(TESTFN3)
        self.assertEqual(file_size, bytes_sent)
        ftp.sendcmd('rest %s' %((file_size + 1)))
        self.assertRaises(ftplib.error_perm, ftp.sendcmd, 'stor ' + TESTFN3)

        ftp.sendcmd('rest %s' %bytes_sent)
        ftp.storbinary('stor ' + TESTFN3, self.f1)

        ftp.retrbinary('retr ' + TESTFN3, self.f2.write)
        self.f1.seek(0)
        self.f2.seek(0)
        self.assertEqual(hash(self.f1.read()), hash(self.f2.read()))
        ftp.delete(TESTFN3)
        

def run():
    class FTPd(threading.Thread):
        def __init__(self):
            self.active = False
            threading.Thread.__init__(self)
            self.setDaemon(True)

        def start(self, flag=None):
            assert not self.active
            self.flag = flag
            threading.Thread.start(self)

        def run(self):
            devnull = lambda x: x
            ftpserver.log = devnull
            ftpserver.logline = devnull
            ftpserver.debug = devnull
            authorizer = ftpserver.DummyAuthorizer()
            authorizer.add_user(user, pwd, home, perm='elradfmw')  # full perms
            authorizer.add_anonymous(home)
            ftp_handler = ftpserver.FTPHandler
            ftp_handler.authorizer = authorizer
            address = (host, port)
            self.__ftpd = ftpserver.FTPServer(address, ftp_handler)
            self.flag.set()
            self.active = True
            self.__ftpd.serve_forever()

        def stop(self):
            assert self.active
            self.active = False
            self.__ftpd.close_all()
    
    flag = threading.Event()
    ftpd = FTPd()
    ftpd.start(flag)
    # wait for it to start
    flag.wait()
    tests = [AbstractedFSClass, DummyAuthorizerClass, FtpAuthentication,
             FtpDummyCmds, FtpFsOperations, FtpRetrieveData, FtpAbort,
             FtpStoreData]
    test_support.run_unittest(*tests)
    ftpd.stop()


host = '127.0.0.1'
port = 54321
user = 'user'
pwd = '12345'
home = os.getcwd()

if __name__ == '__main__':
    run()
