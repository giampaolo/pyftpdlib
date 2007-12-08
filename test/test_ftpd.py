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

from pyftpdlib import ftpserver

__release__ = 'pyftpdlib 0.2.0'


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
# - Test FTPHandler.masquearade_address and FTPHandler.passive_ports behaviours


class AbstractedFSClass(unittest.TestCase):

    def test_normalize(self):
        ae = self.assertEquals
        fs = ftpserver.AbstractedFS()

        fs.cwd = '/'
        ae(fs.normalize(''), '/')
        ae(fs.normalize('/'), '/')
        ae(fs.normalize('.'), '/')
        ae(fs.normalize('..'), '/')
        ae(fs.normalize('a'), '/a')
        ae(fs.normalize('/a'), '/a')
        ae(fs.normalize('/a/'), '/a')
        ae(fs.normalize('a/..'), '/')
        ae(fs.normalize('a/b'), '/a/b')
        ae(fs.normalize('a/b/..'), '/a')
        ae(fs.normalize('a/b/../..'), '/')
        fs.cwd = '/sub'
        ae(fs.normalize(''), '/sub')
        ae(fs.normalize('/'), '/')
        ae(fs.normalize('.'), '/sub')
        ae(fs.normalize('..'), '/')
        ae(fs.normalize('a'), '/sub/a')
        ae(fs.normalize('a/'), '/sub/a')
        ae(fs.normalize('a/..'), '/sub')
        ae(fs.normalize('a/b'), '/sub/a/b')
        ae(fs.normalize('a/b/'), '/sub/a/b')
        ae(fs.normalize('a/b/..'), '/sub/a')
        ae(fs.normalize('a/b/../..'), '/sub')
        ae(fs.normalize('a/b/../../..'), '/')
        ae(fs.normalize('//'), '/') # UNC paths must be collapsed

    def test_translate(self):
        ae = self.assertEquals
        fs = ftpserver.AbstractedFS()
        join = lambda x,y: os.path.join(x, y.replace('/', os.sep))

        def goforit(root):
            fs.root = root
            fs.cwd = '/'
            ae(fs.translate(''), root)
            ae(fs.translate('/'), root)
            ae(fs.translate('.'), root)
            ae(fs.translate('..'), root)
            ae(fs.translate('a'), join(root, 'a'))
            ae(fs.translate('/a'), join(root, 'a'))
            ae(fs.translate('/a/'), join(root, 'a'))
            ae(fs.translate('a/..'), root)
            ae(fs.translate('a/b'), join(root, r'a/b'))
            ae(fs.translate('/a/b'), join(root, r'a/b'))
            ae(fs.translate('/a/b/..'), join(root, 'a'))
            ae(fs.translate('/a/b/../..'), root)
            fs.cwd = '/sub'
            ae(fs.translate(''), join(root, 'sub'))
            ae(fs.translate('/'), root)
            ae(fs.translate('.'), join(root, 'sub'))
            ae(fs.translate('..'), root)
            ae(fs.translate('a'), join(root, 'sub/a'))
            ae(fs.translate('a/'), join(root, 'sub/a'))
            ae(fs.translate('a/..'), join(root, 'sub'))
            ae(fs.translate('a/b'), join(root, 'sub/a/b'))
            ae(fs.translate('a/b/..'), join(root, 'sub/a'))
            ae(fs.translate('a/b/../..'), join(root, 'sub'))
            ae(fs.translate('a/b/../../..'), root)
            ae(fs.translate('//a'), join(root, 'a')) # UNC paths must be collapsed

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

    def test_validpath(self):
        fs = ftpserver.AbstractedFS()
        fs.root = home
        self.assertEqual(fs.validpath(home), True)
        self.assertEqual(fs.validpath(home + '/'), True)
        self.assertEqual(fs.validpath(home + 'xxx'), False)


# --- Tests for AbstractedFS.checksymlink() method.

if hasattr(os, 'symlink'):
    class TestValidSymlink(unittest.TestCase):
        """Test whether the symlink is considered to be valid."""
        def setUp(self):
            self.tf = tempfile.NamedTemporaryFile(dir=home)
            self.linkname = os.path.basename(tempfile.mktemp(dir=home))
            os.symlink(self.tf.name, self.linkname)
        def tearDown(self):
            self.tf.close()
            os.remove(self.linkname)

        def test_it(self):
            fs = ftpserver.AbstractedFS()
            fs.root = home
            fs.validpath(self.linkname)

    class TestExternalSymlink(unittest.TestCase):
        """Test whether a symlink is considered to be pointing to a
        path which is outside the user's root."""
        def setUp(self):
            # note: by not specifying a directory we should have our
            # tempfile created in /tmp directory, which should be
            # outside the user root
            self.tf = tempfile.NamedTemporaryFile()
            self.linkname = os.path.basename(tempfile.mktemp(dir=home))
            os.symlink(self.tf.name, self.linkname)
        def tearDown(self):
            self.tf.close()
            os.remove(self.linkname)

        def test_it(self):
            if os.getcwd() == os.path.dirname(self.tf.name):
                return
            fs = ftpserver.AbstractedFS()
            fs.root = home
            self.assertEqual(fs.validpath(self.linkname), False)


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
        auth.add_user(user, pwd, home, perm=('r', 'w'))
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
                            home, perm=('?'))
        self.assertRaises(ftpserver.AuthorizerError, auth.add_anonymous, home,
                            perm=('?'))
        # expect warning on 'w' permission assigned to anonymous user
        self.assertRaises(RuntimeWarning, auth.add_anonymous, home, perm=('w'))


class FtpAuthentication(unittest.TestCase):
    "test: USER, PASS, REIN"

    def setUp(self):
        global ftp
        ftp = ftplib.FTP()
        ftp.connect(host=host, port=port)
        self.f1 = open(tempfile.mktemp(dir=home), 'w+b')
        self.f2 = open(tempfile.mktemp(dir=home), 'w+b')

    def tearDown(self):
        ftp.close()
        if not self.f1.closed:
            self.f1.close()
        if not self.f2.closed:
            self.f2.close()
        os.remove(self.f1.name)
        os.remove(self.f2.name)

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
        # If authentication fails for 3 times ftpd disconnect us.
        # We can check if this happen by using ftp.sendcmd() on the 'dead'
        # socket object.  If socket object is really dead it should be raised
        # socket.error exception (Windows) or EOFError exception (Linux).
        self.failUnlessRaises((socket.error, EOFError), ftp.sendcmd, '')

    def test_rein(self):
        """Test REIN while no transfer is in progress."""
        ftp.login(user=user, passwd=pwd)
        ftp.sendcmd('rein')
        # user is not yet authenticated, a permission error response is expected
        self.assertRaises(ftplib.error_perm, ftp.sendcmd, 'pwd')
        # by logging-in again we should be able to execute a file-system command
        ftp.login(user=user, passwd=pwd)
        ftp.sendcmd('pwd')

    def test_rein_on_transfer(self):
        """Test REIN while a transfer is in progress."""
        ftp.login(user=user, passwd=pwd)
        data = 'abcde12345' * 100000
        fname_1 = os.path.basename(self.f1.name)
        self.f1.write(data)
        self.f1.close()

        ftp.voidcmd('TYPE I')
        conn = ftp.transfercmd('retr ' + fname_1)
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
        self.assertRaises(ftplib.error_perm, ftp.sendcmd, 'size ' + fname_1)
        # by logging-in again we should be able to execute a file-system command
        ftp.login(user=user, passwd=pwd)
        ftp.sendcmd('pwd')
        self.f2.seek(0)
        self.assertEqual(hash(data), hash (self.f2.read()))

    def test_user(self):
        """Test USER while already authenticated and no transfer is in progress.
        """
        ftp.login(user=user, passwd=pwd)
        ftp.sendcmd('user ' + user)
        # user is not yet authenticated, a permission error response is expected
        self.assertRaises(ftplib.error_perm, ftp.sendcmd, 'pwd')
        # by logging-in again we should be able to execute a file-system command
        ftp.sendcmd('pass ' + pwd)
        ftp.sendcmd('pwd')

    def test_user_on_transfer(self):
        """Test USER while already authenticated and a transfer is in progress.
        """
        ftp.login(user=user, passwd=pwd)
        data = 'abcde12345' * 100000
        fname_1 = os.path.basename(self.f1.name)
        self.f1.write(data)
        self.f1.close()

        ftp.voidcmd('TYPE I')
        conn = ftp.transfercmd('retr ' + fname_1)
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
        # by logging-in again we should be able to execute a file-system command
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
        self.failUnlessRaises(ftplib.error_perm, ftp.sendcmd, 'stru')
        self.failUnlessRaises(ftplib.error_perm, ftp.sendcmd, 'stru ?!?')

    def test_mode(self):
        ftp.sendcmd('mode s')
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
        self.tempfile = os.path.basename(open(tempfile.mktemp(dir=home), 'w+b').name)
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
        # ftplib.parse257 function is usually used for parsing the '257'
        # response for a MKD or PWD request returning the directory name
        # in the 257 reply.
        # Even if CDUP response code is different (250) we could use parse257
        # anyway for getting directory name.
        ftp.cwd(self.tempdir)
        dir = ftplib.parse257(ftp.sendcmd('cdup').replace('250', '257'))
        self.assertEqual(dir, '/')
        dir = ftplib.parse257(ftp.sendcmd('cdup').replace('250', '257'))
        self.assertEqual(dir, '/')

    def test_mkd(self):
        tempdir = os.path.basename(tempfile.mktemp(dir=home))
        ftp.mkd(tempdir)
        # make sure we can't create directories which already exist (probably
        # not really necessary);
        # let's use a try/except statement to avoid leaving behind orphaned
        # temporary directory in the event of a test failure.
        try:
            ftp.mkd(tempdir)
        except ftplib.error_perm, err:
            os.rmdir(tempdir) # ok
        else:
            self.fail('ftplib.error_perm not raised.')

    def test_rmd(self):
        ftp.rmd(self.tempdir)
        # make sure we can't use rmd against files
        self.assertRaises(ftplib.error_perm, ftp.rmd, self.tempfile)
        # make sure we can't remove root directory
        self.assertRaises(ftplib.error_perm, ftp.rmd, '/')

    def test_dele(self):
        ftp.delete(self.tempfile)
        # make sure we can't rename root directory, just to be safe,
        # maybe not really necessary...
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
        ftp.sendcmd('stat *')
        ftp.sendcmd('stat ' + self.tempfile)
        ftp.sendcmd('stat ' + self.tempdir)
        self.failUnless('Directory is empty' in ftp.sendcmd('stat '+ self.tempdir))
        self.failUnless('recursion not supported' in ftp.sendcmd('stat /*/*'))


class FtpRetrieveData(unittest.TestCase):
    "test: RETR, REST, LIST, NLST"

    def setUp(self):
        global ftp
        ftp = ftplib.FTP()
        ftp.connect(host=host, port=port)
        ftp.login(user=user, passwd=pwd)
        self.f1 = open(tempfile.mktemp(dir=home), 'w+b')
        self.f2 = open(tempfile.mktemp(dir=home), 'w+b')

    def tearDown(self):
        ftp.close()
        if not self.f1.closed:
            self.f1.close()
        if not self.f2.closed:
            self.f2.close()
        os.remove(self.f1.name)
        os.remove(self.f2.name)

    def test_retr(self):
        data = 'abcde12345' * 100000
        self.f1.write(data)
        self.f1.close()
        remote_fname = os.path.basename(self.f1.name)
        ftp.retrbinary("retr " + remote_fname, self.f2.write)
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

    def test_list(self):
        l = []
        ftp.retrlines('LIST ' + os.path.basename(self.f1.name), l.append)
        self.assertEqual(len(l), 1)
        l = []
        l1, l2, l3, l4 = [], [], [], []
        ftp.retrlines('LIST', l.append)
        ftp.retrlines('LIST -a', l1.append)
        ftp.retrlines('LIST -l', l2.append)
        ftp.retrlines('LIST -al', l3.append)
        ftp.retrlines('LIST -la', l4.append)
        x = [l, l1, l2, l3, l4]
        for i in range(0,4):
            self.assertEqual(x[i], x[i+1])

    def test_nlst(self):
        noop = lambda x: x
        ftp.retrlines('NLST', noop)
        ftp.retrlines('NLST ' + os.path.basename(self.f1.name), noop)


class FtpAbort(unittest.TestCase):
    "test: ABOR"

    def setUp(self):
        global ftp
        ftp = ftplib.FTP()
        ftp.connect(host=host, port=port)
        ftp.login(user=user, passwd=pwd)
        self.f1 = open(tempfile.mktemp(dir=home), 'w+b')
        self.f2 = open(tempfile.mktemp(dir=home), 'w+b')

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
        # Case 2: user sends a PASV, a data-channel socket is listening but not
        # connected, and ABOR is sent: close listening data socket, respond
        # with 225.
        ftp.sendcmd('PASV')
        respcode = ftp.sendcmd('ABOR')[:3]
        self.failUnlessEqual('225', respcode)

    def test_abor_port(self):
        # Case 3: data channel opened with PASV or PORT, but ABOR sent before
        # a data transfer has been started: close data channel, respond with 225
        ftp.makeport()
        respcode = ftp.sendcmd('ABOR')[:3]
        self.failUnlessEqual('225', respcode)

    def test_abor(self):
        # Case 4: ABOR while a data transfer on DTP channel is in progress:
        # close data channel, respond with 426, respond with 226.
        data = 'abcde12345' * 100000
        self.f1.write(data)
        self.f1.close()

        # this ugly loop construct is to simulate an interrupted transfer since
        # ftplib doesn't like running storbinary() in a separate thread
        ftp.voidcmd('TYPE I')
        conn = ftp.transfercmd('retr ' + os.path.basename(self.f1.name))
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
        self.f1 = open(tempfile.mktemp(dir=home), 'w+b')
        self.f2 = open(tempfile.mktemp(dir=home), 'w+b')

    def tearDown(self):
        ftp.close()
        if not self.f1.closed:
            self.f1.close()
        if not self.f2.closed:
            self.f2.close()
        os.remove(self.f1.name)
        os.remove(self.f2.name)

    def test_stor(self):
        data = 'abcde12345' * 100000
        self.f1.write(data)
        self.f1.seek(0)
        remote_fname = os.path.basename(tempfile.mktemp(dir=home))
        ftp.storbinary('stor ' + remote_fname, self.f1)
        ftp.retrbinary('retr ' + remote_fname, self.f2.write)
        self.f2.seek(0)
        self.assertEqual(hash(data), hash (self.f2.read()))
        # we do not use os.remove because file could be still locked by ftpd thread
        ftp.delete(remote_fname)

    def test_stou(self):
        data = 'abcde12345' * 100000
        self.f1.write(data)
        self.f1.seek(0)

        ftp.voidcmd('TYPE I')
        # filename comes in as 1xx FILE: <filename>
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
        # we do not use os.remove because file could be
        # still locked by ftpd thread
        ftp.delete(filename)

    def test_stou_rest(self):
        # watch for STOU preceded by REST, which makes no sense.
        ftp.sendcmd('rest 10')
        self.assertRaises(ftplib.error_perm, ftp.sendcmd, 'stou')

    def test_appe(self):
        fname_1 = os.path.basename(self.f1.name)
        fname_2 = os.path.basename(self.f2.name)
        remote_fname = os.path.basename(tempfile.mktemp(dir=home))

        data1 = 'abcde12345' * 100000
        self.f1.write(data1)
        self.f1.seek(0)
        ftp.storbinary('stor ' + remote_fname, self.f1)

        data2 = 'fghil67890' * 100000
        self.f1.write(data2)
        self.f1.seek(ftp.size(remote_fname))
        ftp.storbinary('appe ' + remote_fname, self.f1)

        ftp.retrbinary("retr " + remote_fname, self.f2.write)
        self.f2.seek(0)
        self.assertEqual(hash(data1 + data2), hash (self.f2.read()))
        ftp.delete(remote_fname)

    def test_appe_rest(self):
        # watch for APPE preceded by REST, which makes no sense.
        ftp.sendcmd('rest 10')
        self.assertRaises(ftplib.error_perm, ftp.sendcmd, 'appe x')

    def test_rest_on_stor(self):
        fname_1 = os.path.basename(self.f1.name)
        fname_2 = os.path.basename(self.f2.name)
        remote_fname = os.path.basename(tempfile.mktemp(dir=home))

        data = 'abcde12345' * 100000
        self.f1.write(data)
        self.f1.seek(0)

        ftp.voidcmd('TYPE I')
        conn = ftp.transfercmd('stor ' + remote_fname)
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
        file_size = ftp.size(remote_fname)
        self.assertEqual(file_size, bytes_sent)
        ftp.sendcmd('rest %s' %((file_size + 1)))
        self.assertRaises(ftplib.error_perm, ftp.sendcmd, 'stor ' + remote_fname)

        ftp.sendcmd('rest %s' %bytes_sent)
        ftp.storbinary('stor ' + remote_fname, self.f1)

        ftp.retrbinary('retr ' + remote_fname, self.f2.write)
        self.f1.seek(0)
        self.f2.seek(0)
        self.assertEqual(hash(self.f1.read()), hash(self.f2.read()))
        ftp.delete(remote_fname)


def run():
    class ftpd(threading.Thread):
        def __init__(self):
            threading.Thread.__init__(self)

        def run(self):
            def devnull(msg):
                pass
            ftpserver.log = devnull
            ftpserver.logline = devnull
            ftpserver.debug = devnull
            authorizer = ftpserver.DummyAuthorizer()
            authorizer.add_user(user, pwd, home, perm=('r', 'w'))
            authorizer.add_anonymous(home)
            ftp_handler = ftpserver.FTPHandler
            ftp_handler.authorizer = authorizer
            address = (host, port)
            ftpd = ftpserver.FTPServer(address, ftp_handler)
            ftpd.serve_forever()

    def exit_fun():
        os._exit(0)
    atexit.register(exit_fun)

    f = ftpd()
    f.start()
    time.sleep(0.3)
    unittest.main()


host = '127.0.0.1'
port = 54321
user = 'user'
pwd = '12345'
home = os.getcwd()

if __name__ == '__main__':
    run()
