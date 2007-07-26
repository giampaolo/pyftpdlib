#!/usr/bin/env python
# test_ftpd.py

#  ======================================================================
#  Copyright (C) 2007  billiejoex <billiejoex@gmail.com>
#
#                         All Rights Reserved
# 
#  Permission to use, copy, modify, and distribute this software and
#  its documentation for any purpose and without fee is hereby
#  granted, provided that the above copyright notice appear in all
#  copies and that both that copyright notice and this permission
#  notice appear in supporting documentation, and that the name of 
#  billiejoex not be used in advertising or publicity pertaining to
#  distribution of the software without specific, written prior
#  permission.
# 
#  billiejoex DISCLAIMS ALL WARRANTIES WITH REGARD TO THIS SOFTWARE,
#  INCLUDING ALL IMPLIED WARRANTIES OF MERCHANTABILITY AND FITNESS, IN
#  NO EVENT billiejoex BE LIABLE FOR ANY SPECIAL, INDIRECT OR
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

from pyftpdlib import FTPServer

__revision__ = '2 (pyftpdlib 0.1.1)'

# TODO:
# - test ABOR
# - test QUIT while a transfer is in progress
# - test data transfer in ASCII and binary MODE

class test_classes(unittest.TestCase):

    def test_abstracetd_fs(self):
        ae = self.assertEquals
        fs = FTPServer.AbstractedFS()

        # normalize method
        fs.cwd = '/'
        ae(fs.normalize(''), '/')
        ae(fs.normalize('/'), '/')
        ae(fs.normalize('a'), '/a')
        ae(fs.normalize('/a'), '/a')
        ae(fs.normalize('a/b'), '/a/b')
        fs.cwd = '/sub'      
        ae(fs.normalize(''), '/sub')
        ae(fs.normalize('a'), '/sub/a')
        ae(fs.normalize('a/b'), '/sub/a/b')
        ae(fs.normalize('//'), '/')
        ae(fs.normalize('/a/'), '/a')

        # translate method
        if os.sep == '/':
            fs.root = '/home/user'
            fs.cwd = '/'
            ae(fs.translate('/'), '/home/user')
            ae(fs.translate('a'), '/home/user/a')
            ae(fs.translate('/a'), '/home/user/a')
            ae(fs.translate('a/b'), '/home/user/a/b')
            ae(fs.translate('/a/b'), '/home/user/a/b')
            fs.cwd = '/sub'
            ae(fs.translate('a'), '/home/user/sub/a')
            ae(fs.translate('a/b'), '/home/user/sub/a/b')
            ae(fs.translate('/a'), '/home/user/a')
            ae(fs.translate('/'), '/home/user')

        elif os.sep == '\\':
            fs.root = r'C:\dir'
            fs.cwd = '/'
            ae(fs.translate('/'), r'C:\dir')
            ae(fs.translate('a'), r'C:\dir\a')
            ae(fs.translate('/a'), r'C:\dir\a')
            ae(fs.translate('a/b'), r'C:\dir\a\b')
            ae(fs.translate('/a/b'), r'C:\dir\a\b')
            fs.cwd = '/sub'
            ae(fs.translate('a'), r'C:\dir\sub\a')
            ae(fs.translate('a/b'), r'C:\dir\sub\a\b')
            ae(fs.translate('/a'), r'C:\dir\a')
            ae(fs.translate('/'), r'C:\dir')

    def test_dummy_authorizer(self):
        auth = FTPServer.DummyAuthorizer()
        auth.user_table = {}
        if os.sep == '\\':
            home = 'C:\\'
        elif os.sep == '/':
            home = '/tmp'
        else:
            raise Exception, 'Not supported system'
        # raise exc if path does not exist
        self.assertRaises(AssertionError, auth.add_user, 'ftpuser', '12345', 'ox:\\?', perm=('r', 'w'))
        self.assertRaises(AssertionError, auth.add_anonymous, 'ox:\\?')
        # raise exc if user already exists
        auth.add_user('ftpuser', '12345', home, perm=('r', 'w'))
        self.assertRaises(FTPServer.Error, auth.add_user, 'ftpuser', '12345', home, perm=('r', 'w'))
        # ...even anonymous
        auth.add_anonymous(home)
        self.assertRaises(FTPServer.Error, auth.add_anonymous, home)
        # raise on wrong permission
        self.assertRaises(FTPServer.Error, auth.add_user, 'ftpuser2', '12345', home, perm=('x'))
        del auth.user_table['anonymous']
        self.assertRaises(FTPServer.Error, auth.add_anonymous, home, perm=('w'))
        self.assertRaises(FTPServer.Error, auth.add_anonymous, home, perm=('%&'))
        self.assertRaises(FTPServer.Error, auth.add_anonymous, home, perm=(None))
        auth.add_anonymous(home, perm=(''))
        # raise on 'w' permission given to anonymous user
        self.assertRaises(FTPServer.Error, auth.add_anonymous, home, perm=('w'))


class ftp_authentication(unittest.TestCase):
    "test: USER, PASS, REIN"

    def setUp(self):
        global ftp
        ftp = ftplib.FTP()
        ftp.connect(host=host, port=port)

    def tearDown(self):
        ftp.close()

    def test_auth_ok(self):
        ftp.login(user=user, passwd=pwd)

    def test_auth_failed(self):
        self.failUnlessRaises(ftplib.error_perm, ftp.login, user=user, passwd='wrong')

    def test_anon_auth(self):
        ftp.login(user='anonymous', passwd='anon@')
        ftp.login(user='AnonYmoUs', passwd='anon@')
        ftp.login(user='anonymous', passwd='')   

    def test_rein(self):
        self.failUnlessRaises(ftplib.error_perm, ftp.sendcmd, 'pwd')
        ftp.login(user='anonymous', passwd='anon@')
        ftp.sendcmd('pwd')
        ftp.sendcmd('rein')
        self.failUnlessRaises(ftplib.error_perm, ftp.sendcmd, 'pwd')

    def test_max_auth(self):
        # if authentication fails for 3 times ftpd disconnect us.
        # we can check if this happen by using ftp.sendcmd() on the 'dead' socket object.
        # If socket object is really dead it should be raised
        # socket.error exception (Windows) or EOFError exception (Linux).
        self.failUnlessRaises(ftplib.error_perm, ftp.login, user=user, passwd='wrong')
        self.failUnlessRaises(ftplib.error_perm, ftp.login, user=user, passwd='wrong')
        self.failUnlessRaises(ftplib.error_perm, ftp.login, user=user, passwd='wrong')
        self.failUnlessRaises((socket.error, EOFError), ftp.sendcmd, '')


class ftp_dummy_cmds(unittest.TestCase):
    "test: TYPE, STRU, MODE, STAT, NOOP, SYST, ALLO, HELP"

    def setUp(self):
        global ftp
        ftp = ftplib.FTP()
        ftp.connect(host=host, port=port)
        ftp.login(user=user, passwd=pwd)

    def tearDown(self):
        ftp.close()

    def test_type(self):
##	for _type in ('a', 'i'):
##	    ftp.sendcmd('type %s' %_type)
##	    ftp.sendcmd('type %s' %_type.upper())
        self.failUnlessRaises(ftplib.error_perm, ftp.sendcmd, 'type')
        self.failUnlessRaises(ftplib.error_perm, ftp.sendcmd, 'type x')

    def test_stru(self):
        ftp.sendcmd('stru f')
        ftp.sendcmd('stru F')
        self.failUnlessRaises(ftplib.error_perm, ftp.sendcmd, 'stru')
        self.failUnlessRaises(ftplib.error_perm, ftp.sendcmd, 'stru x')

    def test_mode(self):
        ftp.sendcmd('mode s')
        ftp.sendcmd('mode S')
        self.failUnlessRaises(ftplib.error_perm, ftp.sendcmd, 'mode')
        self.failUnlessRaises(ftplib.error_perm, ftp.sendcmd, 'mode x')

    def test_stat(self):
        ftp.sendcmd('stat')

    def test_noop(self):
        ftp.sendcmd('noop')

    def test_syst(self):
        ftp.sendcmd('syst')

    def test_allo(self):
        ftp.sendcmd('allo')

    def test_help(self):
        ftp.sendcmd('help')
        cmd = random.choice(FTPServer.proto_cmds.keys())
        ftp.sendcmd('help %s' %cmd)
        self.failUnlessRaises(ftplib.error_perm, ftp.sendcmd, 'help ?!?')

    def test_quit(self):
        ftp.sendcmd('quit')


class ftp_fs_operations(unittest.TestCase):
    "test: PWD, CWD, CDUP, SIZE, RNFR, RNTO, DELE, MKD, RMD, MDTM"
    
    def test_it(self):
        ftp = ftplib.FTP()
        ftp.connect(host=host, port=port)
        ftp.login(user=user, passwd=pwd)        
        ftp.sendcmd('pwd')
        ftp.sendcmd('cwd')
        ftp.sendcmd('cdup')
        f = open(os.path.join(home, '1.tmp'), 'w+')
        f.write('x' * 123)
        f.close()
        self.assertEqual (ftp.sendcmd('size 1.tmp')[4:], '123')
        ftp.sendcmd('mdtm 1.tmp')
        ftp.sendcmd('rnfr 1.tmp')
        ftp.sendcmd('rnto 2.tmp')
        ftp.sendcmd('dele 2.tmp')
        ftp.sendcmd('mkd 1')
        ftp.sendcmd('mkd 1/2')
        self.assertRaises(ftplib.error_perm, ftp.sendcmd, 'rmd a')
        ftp.sendcmd('rmd 1/2')
        ftp.sendcmd('rmd 1')
        self.assertRaises(ftplib.error_perm, ftp.sendcmd, 'rmd /')        
        ftp.close()

class ftp_retrieve_data(unittest.TestCase):
    "test: RETR, REST, LIST, NLST"
    def setUp(self):
        global ftp
        ftp = ftplib.FTP()
        ftp.connect(host=host, port=port)
        ftp.login(user=user, passwd=pwd)

    def tearDown(self):        
        ftp.close()    

    def test_retr(self):
        data = 'abcde12345' * 100000        
        f1 = open(os.path.join(home, '1.tmp'), 'wb')
        f1.write(data)
        f1.close()       
        f2 = open(os.path.join(home, '2.tmp'), "w+b")
        ftp.retrbinary("retr 1.tmp", f2.write)
        f2.seek(0)
        self.assertEqual(hash(data), hash (f2.read()))
        f2.close()
        os.remove(os.path.join(home, '1.tmp'))
        os.remove(os.path.join(home, '2.tmp'))

    def test_restore_on_retr(self):
        data = 'abcde12345' * 100000
        f1 = open(os.path.join(home, '1.tmp'), 'wb')
        f1.write(data)
        f1.close()        
        f2 = open(os.path.join(home, '2.tmp'), "wb")

        # look at ftplib.FTP.retrbinary method to understand this mess
        ftp.voidcmd('TYPE I')
        conn = ftp.transfercmd('retr 1.tmp', rest=None)
        bytes_recv = 0
        while 1:
            chunk = conn.recv(8192)
            # stop transfer while it isn't finished yet
            if bytes_recv >= 524288: # 2^19
                break            
            elif not chunk:
                break
            f2.write(chunk)
            bytes_recv += len(chunk)
        conn.close()
        # trasnfer isn't finished yet so ftpd should respond with 426
        self.failUnlessRaises(ftplib.error_temp, ftp.voidresp)
        f2.close()        

        # resuming
        ftp.sendcmd('rest %s' %bytes_recv)
        f2 = open(os.path.join(home, '2.tmp'), 'a+')
        ftp.retrbinary("retr 1.tmp", f2.write)
        f2.seek(0)
        self.assertEqual(hash(data), hash (f2.read()))
        f2.close()
        os.remove(os.path.join(home, '1.tmp'))
        os.remove(os.path.join(home, '2.tmp'))

    def test_rest(self):
        # just test rest's semantic without using data-transfer
        ftp.sendcmd('rest 3123')
        self.failUnlessRaises(ftplib.error_perm, ftp.sendcmd, 'rest')        
        self.failUnlessRaises(ftplib.error_perm, ftp.sendcmd, 'rest str')       
        self.failUnlessRaises(ftplib.error_perm, ftp.sendcmd, 'rest -1')

    def test_list(self):
        l = []
        f = open(os.path.join(home, '1.tmp'), 'w')
        f.close()
        ftp.retrlines('LIST 1.tmp', l.append)
        self.assertEqual(len(l), 1)
        os.remove(os.path.join(home, '1.tmp'))        
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
        l = []
        ftp.retrlines('NLST', l.append)
        self.failUnlessRaises(ftplib.error_perm, ftp.retrlines, 'NLST 1.tmp', l.append)

class ftp_abor(unittest.TestCase):
    "test: ABOR"

    def setUp(self):
        global ftp
        ftp = ftplib.FTP()
        ftp.connect(host=host, port=port)
        ftp.login(user=user, passwd=pwd)

    def tearDown(self):        
        ftp.close()    
        tmpfile = os.path.join(home, 'abor.tmp')
        if os.path.exists(tmpfile):
            os.remove(tmpfile)
        
    def test_abor_no_data(self):
        # Case 1: ABOR while no data channel is opened: respond with 225.
        respcode = ftp.sendcmd('ABOR')[:3]
        self.failUnlessEqual('225', respcode, "ABOR while no data channel is open failed to return 225 response (returned %s)" % (respcode))

    def test_abor_pasv(self):
        # Case 2: user sends a PASV, a data-channel socket is listening but not
        # connected, and ABOR is sent: close listening data socket, respond 
        # with 225.
        ftp.sendcmd('PASV')
        respcode = ftp.sendcmd('ABOR')[:3]
        self.failUnlessEqual('225', respcode, "ABOR immediately following PASV failed to return 225 response (returned %s)" % (respcode))
        
    def test_abor_port(self):
        # Case 3: data channel opened with PASV or PORT, but ABOR sent before 
        # a data transfer has been started: close data channel, respond with 225
        ftp.makeport()
        respcode = ftp.sendcmd('ABOR')[:3]
        self.failUnlessEqual('225', respcode, "ABOR immediately following PORT failed to return 225 response (returned %s)" % (respcode))

    def test_abor(self):
        # Case 4: ABOR while a data transfer on DTP channel is in progress:
        # close data channel, respond with 426, respond with 226.
        data = 'abcde12345' * 100000
        f1 = tempfile.TemporaryFile(mode='w+b')
        f1.write(data)
        f1.seek(0)

        # this ugly loop construct is to simulate an interrupted transfer since
        # ftplib doesn't like running storbinary() in a separate thread
        conn = ftp.transfercmd('stor abor.tmp', rest=None)
        bytes_sent = 0
        while 1:
            chunk = f1.read(8192)
            bytes_sent += conn.send(chunk)
            # stop transfer while it isn't finished yet
            if bytes_sent >= 524288: # 2^19
                break
            elif not chunk:
                break
        ftp.putcmd('ABOR')
        conn.close()

        # transfer isn't finished yet so ftpd should respond with 426
        self.failUnlessRaises(ftplib.error_temp, ftp.voidresp)

        # transfer successfully aborted, so should now respond with a 226
        self.failUnlessEqual('226', ftp.voidresp()[:3])

class ftp_store_data(unittest.TestCase):
    "test: STOR, STOU, APPE, REST"

    def setUp(self):
        global ftp
        ftp = ftplib.FTP()
        ftp.connect(host=host, port=port)
        ftp.login(user=user, passwd=pwd)

    def tearDown(self):        
        ftp.close()    
        
    def test_stor(self):
        data = 'abcde12345' * 100000        
        f1 = tempfile.TemporaryFile(mode='w+b')
        f1.write(data)
        f1.seek(0)
        ftp.storbinary('stor 1.tmp', f1)
        f1.close()
        f2 = open(os.path.join(home, '2.tmp'), "w+b")
        ftp.retrbinary("retr 1.tmp", f2.write)
        f2.seek(0)
        self.assertEqual(hash(data), hash (f2.read()))
        f2.close()
        os.remove(os.path.join(home, '1.tmp'))        
        os.remove(os.path.join(home, '2.tmp'))

    def test_stou(self):        
        data = 'abcde12345' * 100000
        f1 = tempfile.TemporaryFile(mode='w+b')
        f1.write(data)
        f1.seek(0)

        ftp.voidcmd('TYPE I')
        # filename comes in as 1xx FILE: <filename>
        filename = ftp.sendcmd('stou').split('FILE: ')[1]
        sock = ftp.makeport()
        conn, sockaddr = sock.accept()
        while 1:
            buf = f1.read(8192)
            if not buf:
                break
            conn.sendall(buf)
        conn.close()
        ftp.voidresp()
        f1.close()
        os.remove (os.path.join(home, filename))

    def test_appe(self):
        data1 = 'abcde12345' * 100000     
        f1 = tempfile.TemporaryFile(mode='w+b')
        f1.write(data1)
        f1.seek(0)
        ftp.storbinary('stor 1.tmp', f1)

        data2 = 'fghil67890' * 100000
        f1.write(data2)
        size = ftp.sendcmd('size 1.tmp')[4:]
        f1.seek(int(size))
        ftp.storbinary('appe 1.tmp', f1)

        f2 = open(os.path.join(home, '2.tmp'), "w+b")
        ftp.retrbinary("retr 1.tmp", f2.write)
        f2.seek(0)
        self.assertEqual(hash(data1 + data2), hash (f2.read()))
        f1.close()
        f2.close()
        os.remove(os.path.join(home, '1.tmp'))        
        os.remove(os.path.join(home, '2.tmp'))

    def test_rest_on_stor(self):
        data = 'abcde12345' * 100000     
        f1 = tempfile.TemporaryFile(mode='w+b')
        f1.write(data)
        f1.seek(0)

        ftp.voidcmd('TYPE I')
        conn = ftp.transfercmd('stor 1.tmp', rest=None)
        bytes_sent = 0
        while 1:
            chunk = f1.read(8192)
            bytes_sent += conn.send(chunk)
            # stop transfer while it isn't finished yet
            if bytes_sent >= 524288: # 2^19
                break            
            elif not chunk:
                break
        conn.close()
        ftp.voidresp()        

        ftp.sendcmd('rest %s' %bytes_sent)
        ftp.storbinary('appe 1.tmp', f1)
        f2 = open(os.path.join(home, '2.tmp'), "w+b")
        ftp.retrbinary("retr 1.tmp", f2.write)
        f1.seek(0)
        f2.seek(0)
        self.assertEqual(hash(data), hash (f2.read()))
        f1.close()        
        f2.close()


def run():
    class ftpd(threading.Thread):
        def __init__(self):
            threading.Thread.__init__(self)

        def run(self):
            def logger(msg):
                pass
            def linelogger(msg):
                pass
            def debugger(msg):
                pass
            
            FTPServer.log = logger
            FTPServer.logline = linelogger
            FTPServer.debug = debugger
            authorizer = FTPServer.DummyAuthorizer()
            authorizer.add_user(user, pwd, home, perm=('r', 'w'))
            authorizer.add_anonymous(home)
            ftp_handler = FTPServer.FTPHandler    
            ftp_handler.authorizer = authorizer   
            address = (host, port)    
            ftpd = FTPServer.FTPServer(address, ftp_handler)
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
