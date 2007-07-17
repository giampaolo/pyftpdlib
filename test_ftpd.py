#!/usr/bin/env python
# test_ftpd.py


#  ======================================================================
#  Copyright 2007 by billiejoex
# 
#                          All Rights Reserved
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
from pyftpdlib import FTPServer

__ver__ = '0.1.0'

# TODO:
# - test ABOR
# - test QUIT while a transfer is in progress
# - test data transfer in ASCII and binary MODE

class test_classes(unittest.TestCase):

    def test_abstracetd_fs(self):
        ae = self.assertEquals
        fs = FTPServer.abstracted_fs()

        # translate method
        fs.cwd = '/'
        ae(fs.translate(''), '/')
        ae(fs.translate('/'), '/')
        ae(fs.translate('a'), '/a')
        ae(fs.translate('/a'), '/a')
        ae(fs.translate('a/b'), '/a/b')
        fs.cwd = '/sub'      
        ae(fs.translate(''), '/sub')
        ae(fs.translate('a'), '/sub/a')
        ae(fs.translate('a/b'), '/sub/a/b')
        ae(fs.translate('//'), '/')
        ae(fs.translate('/a/'), '/a')

        # normalize method
        if os.sep == '/':
            fs.root = '/home/user'
            fs.cwd = '/'
            ae(fs.normalize('/'), '/home/user')
            ae(fs.normalize('a'), '/home/user/a')
            ae(fs.normalize('/a'), '/home/user/a')
            ae(fs.normalize('a/b'), '/home/user/a/b')
            ae(fs.normalize('/a/b'), '/home/user/a/b')
            fs.cwd = '/sub'
            ae(fs.normalize('a'), '/home/user/sub/a')
            ae(fs.normalize('a/b'), '/home/user/sub/a/b')
            ae(fs.normalize('/a'), '/home/user/a')
            ae(fs.normalize('/'), '/home/user')            

        elif os.sep == '\\':
            fs.root = r'C:\dir'
            fs.cwd = '/'
            ae(fs.normalize('/'), r'C:\dir')
            ae(fs.normalize('a'), r'C:\dir\a')
            ae(fs.normalize('/a'), r'C:\dir\a')
            ae(fs.normalize('a/b'), r'C:\dir\a\b')
            ae(fs.normalize('/a/b'), r'C:\dir\a\b')    
            fs.cwd = '/sub'
            ae(fs.normalize('a'), r'C:\dir\sub\a')
            ae(fs.normalize('a/b'), r'C:\dir\sub\a\b')
            ae(fs.normalize('/a'), r'C:\dir\a')
            ae(fs.normalize('/'), r'C:\dir')

    def test_dummy_authorizer(self):
        auth = FTPServer.dummy_authorizer()      
        if os.sep == '\\':
            home = 'C:\\'
        elif os.sep == '/':
            home = '/tmp'
        else:
            raise 
        # raise exc if path does not exist
        self.assertRaises(AssertionError, auth.add_user, 'ftpuser', '12345', 'ox:\\?', perm=('r', 'w'))
        # raise exc if user already exists
        auth.add_user('ftpuser', '12345', home, perm=('r', 'w'))
        self.assertRaises(FTPServer.error, auth.add_user, 'ftpuser', '12345', home, perm=('r', 'w'))
        # raise on wrong permission
        self.assertRaises(FTPServer.error, auth.add_user, 'ftpuser2', '12345', home, perm=('x'))
        # raise on 'w' permission given to anonymous user
        self.assertRaises(FTPServer.error, auth.add_anonymous, home, perm=('w'))


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
        filename = ftp.sendcmd('stou')[4:]
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
            conn.send(chunk)
            bytes_sent += len(chunk)
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
            authorizer = FTPServer.dummy_authorizer()
            authorizer.add_user(user, pwd, home, perm=('r', 'w'))
            authorizer.add_anonymous(home)
            ftp_handler = FTPServer.ftp_handler    
            ftp_handler.authorizer = authorizer   
            address = (host, port)    
            ftpd = FTPServer.ftp_server(address, ftp_handler)
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
