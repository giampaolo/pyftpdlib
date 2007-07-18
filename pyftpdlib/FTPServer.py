#!/usr/bin/env python
# FTPServer.py

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
  

"""
RFC959 asynchronous FTP server.

Usage:
>>> from pyftpdlib import FTPServer
>>> authorizer = FTPServer.dummy_authorizer()
>>> authorizer.add_user('user', '12345', '/home/user', perm=('r', 'w', 'wd'))
>>> authorizer.add_anonymous('/home/nobody')
>>> ftp_handler = FTPServer.ftp_handler
>>> ftp_handler.authorizer = authorizer
>>> address = ("", 21)
>>> ftpd = FTPServer.ftp_server(address, ftp_handler)
>>> ftpd.serve_forever()
Serving FTP on 0.0.0.0:21.
[]10.0.0.1:1089 connected.
10.0.0.1:1089 ==> 220 Ready.
10.0.0.1:1089 <== USER anonymous
10.0.0.1:1089 ==> 331 Username ok, send passowrd.
10.0.0.1:1089 <== PASS ******
10.0.0.1:1089 ==> 230 User anonymous logged in.
[anonymous]@10.0.0.1:1089 User anonymous logged in.
10.0.0.1:1089 <== CWD /
[anonymous]@10.0.0.1:1089 OK CWD "/"
10.0.0.1:1089 ==> 250 "/" is the current directory.
10.0.0.1:1089 <== TYPE A
10.0.0.1:1089 ==> 200 Type set to: ASCII.
10.0.0.1:1089 <== PASV
10.0.0.1:1089 ==> 227 Entering passive mode (10,0,0,1,4,0)
10.0.0.1:1089 <== LIST
10.0.0.1:1089 ==> 125 Data connection already open; Transfer starting.
[anonymous]@10.0.0.1:1089 OK LIST. Transfer starting.
10.0.0.1:1089 ==> 226 Transfer complete.
[anonymous]@10.0.0.1:1089 Trasfer complete. 548 bytes transmitted.
10.0.0.1:1089 <== QUIT
10.0.0.1:1089 ==> 221 Goodbye.
[anonymous]@10.0.0.1:1089 Disconnected.
"""

# Overview:
#
# This file implements a fully functioning asynchronous FTP server as defined in RFC 959.
# It has a hierarchy of classes which implement the backend functionality for the
# ftpd.
#
# A number of classes are provided:
#
#   [ftp_server] - the base class for the backend. 
# 
#   [ftp_handler] - a class representing the server-protocol-interpreter (server-PI, see RFC 959).
#       Every time a new connection occurs ftp_server class will create a new ftp_handler instance
#       that will handle the current PI session.
#
#   [active_dtp], [passive_dtp] - base classes for active/passive-DTP backend.
#
#   [dtp_handler] - class handling server-data-transfer-process (server-DTP, see RFC 959)
#       managing data-transfer operations.
#
#   [dummy_authorizer] - an "authorizer" is a class handling authentication and permissions of ftpd.
#       It is used inside ftp_handler class to verify user passwords, to get user's home-directory
#       and to get permissions when a r/w I/O filesystem event occurs.
#       "dummy_authorizer" is the base authorizer class providing a platform independent interface
#       for managing "virtual-users".
#
#   [abstracted_fs] - class used to interact with file-system providing an high-level platform-independent
#       interface able to work on both DOS/UNIX-like file systems.
#
#   [error] - base class for module exceptions.
#
#
# Moreover, FTPServer provides 3 different logging streams trough 3 functions:
#
#   [log] - the main logger that notifies the most important messages for the end-user regarding the FTPd.
#
#   [logline] - that notifies commands and responses passing through the control FTP channel.
#
#   [debug] - used for debugging messages (function/method calls, traceback outputs,
#       low-level informational messages and so on...). Disabled by default. 
#
#
#
# Tested under Windows XP sp2, Linux Fedora 6, Linux Debian Sarge, Linux Ubuntu Breezy.
#
# Author: billiejoex < billiejoex@gmail.com >


# -----------------
# TODO:
# -----------------
#
# - LIST/NLST commands are currently the mostly CPU-intensive blocking operations.
#   A sort of cache could be implemented (take a look at dircache module).
#
# - brute force protection: 'freeze'/'sleep' (without blocking the main loop)
#   PI session for a certain amount of time if authentication fails.
#
# - check MDTM command's specifications (RFC959 doesn't talk about it).


# -----------------
# OPEN PROBLEMS:
# -----------------
#
# - I didn't well understood when and why asyncore.handle_expt() is called.
#   Out Of Band data? How do I have to manage that?
#
# - actually RNFR/RNTO commands could also be used to *move* a file/directory
#   instead of just renaming them. RFC959 doesn't tell if this must be allowed or not
#   (I believe not).
#
# - What to do if more than one PASV/PORT cmds are received? And what if they're received
#   during a transfer? RFC959 doesn't tell anything about it.
#   Actually data-channel is just restarted.
#
# - DoS/asyncore vulnerability: select() supports only a limited variable number of socket
#   descriptors (aka simultaneous connections). When this number is reached select()
#   raises a ValueError exception but asyncore doesn't handle it (a crash occurs).


# -----------------
# INTERFACE
# (discussions/problems about the interface to provide to the end user)
# -----------------
#
# - [winNT_authorizer] and [unix_authorizer] classes - would it be a good idea adding them
#   inside the module or would be enough just showing them in documentation/advanced usages?
#
# - higher authorizers customization: actually authorizers understand only read and write
#   permissions and they make no difference if objects are files or directories.
#   Would it be a good idea providing additional permission levels? For example:
#                                         
#                                                 / files 
#   (permit? (y/n)) renaming / creation / deletion 
#                                                 \ directories


# --------
# TIMELINE
# --------
# 0.1.1 : 2007-03-07
# 0.1.0 : 2007-02-22


__pname__   = 'Python FTP server library (pyftpdlib)'
__ver__     = '0.1.1'
__state__   = 'beta'
__date__    = '2007-03-07'
__author__  = 'billiejoex (ITA)'
__mail__    = 'billiejoex@gmail.com'
__web__     = 'http://billiejoex.altervista.org'
__license__ = 'see LICENSE file'


import asyncore
import asynchat
import socket
import os
import sys
import traceback
import time
try: 
    import cStringIO as StringIO
except ImportError:
    import StringIO


proto_cmds = {    
            'ABOR' : "abort data-channel transfer", 
            'ALLO' : "allocate space for file about to be sent (obsolete)",    
            'APPE' : "* resume upload",
            'CDUP' : "go to parent directory",
            'CWD'  : "[*] change current directory",
            'DELE' : "* remove file",  
            'HELP' : "print this help",
            'LIST' : "list files",
            'MDTM' : "* get last modification time",
            'MODE' : "* set data transfer mode (obsolete)",
            'MKD'  : "* create directory",
            'NLST' : "list file names",
            'NOOP' : "just do nothing",            
            'PASS' : "* user's password",
            'PASV' : "start passive data channel",
            'PORT' : "start active data channel",              
            'PWD'  : "get current dir",
            'QUIT' : "quit",
            'REIN' : "flush account informations",
            'REST' : "* restart file position (transfer resuming)",
            'RETR' : "* download file",
            'RMD'  : "* remove directory",              
            'RNFR' : "* file/directory renaming (source name)",
            'RNTO' : "* file/directory renaming (destination name)", 
            'SIZE' : "* get file size",
            'STAT' : "status information",
            'STOR' : "* upload file",
            'STOU' : 'store a file with a unique name',            
            'STRU' : "* set file transfer structure (obsolete)",
            'SYST' : "get system type",          
            'TYPE' : "* set transfer type (I=binary, A=ASCII)",
            'USER' : "* set username",
            # * argument required            
              }

deprecated_cmds = {
              'XCUP' : '== CDUP (deprecated)',
              'XCWD' : '== CWD  (deprecated)',
              'XMKD' : '== MKD  (deprecated)',
              'XPWD' : '== LIST (deprecated)',
              'XRMD' : '== RMD  (deprecated)'
              }
              
proto_cmds.update(deprecated_cmds)              

# Not implemented commands: I've not implemented (and a lot of other FTP server
# did the same) ACCT, SITE and SMNT because I find them useless.
not_implemented_cmds = {
              'ACCT' : 'account permissions',
              'SITE' : 'site specific server services',
              'SMNT' : 'structure mount'
              }              
            
type_map = {'a':'ASCII',
            'i':'Binary'}


class error(Exception):
    """Base class for module exceptions."""
    
    def __init__(self, msg=''):
        self.message = msg
        Exception.__init__(self, msg)

    def __repr__(self):
        return self.message


def __get_hs():
    s = ""
    l = proto_cmds.keys()
    l.sort()
    for cmd in l:
        s += '\t%-5s %s\r\n' %(cmd, proto_cmds[cmd])
    return s
helper_string = __get_hs()


# --- loggers

def log(msg):
    "FTPd logger: log messages about FTPd for the end user."
    print msg

def logline(msg):
    "Lines logger: log commands and responses passing through the control channel."
    print msg

def debug(msg):
    "Debugger: log debugging messages (function/method calls, traceback outputs and so on...)."
    pass
    #print "\t%s" %msg


# --- authorizers

class basic_authorizer:
    """This class exists just for documentation.
    If you want to write your own authorizer you must provide all
    the following methods.
    """
    def __init__(self):
        ""
    def add_user(self, username, password, homedir, perm=('r')):        
        ""        
    def add_anonymous(self, homedir, perm=('r')):
        ""
    def validate_authentication(self, username, password):
        ""        
    def has_user(self, username):
        ""
    def get_home_dir(self, username):
        ""
    def r_perm(self, username, obj):
        ""
    def w_perm(self, username, obj):
        ""        
   
class dummy_authorizer:    
    """Dummy authorizer base class providing a basic portable
    interface for handling "virtual" users.
    """
    
    user_table = {}

    def __init__(self):
        pass

    def add_user(self, username, password, homedir, perm=('r')):
        assert os.path.isdir(homedir), 'No such directory: "%s".' %homedir
        for i in perm:
            if i not in ('r', 'w'):
                raise error, 'No such permission "%s".' %i
        if self.has_user(username):
            raise error, 'User "%s" already exists.' %username
        dic = {'pwd'  : str(password),
               'home' : str(homedir),
               'perm' : perm
                }
        self.user_table[username] = dic
        
    def add_anonymous(self, homedir, perm=('r')):
        if perm not in ('', 'r'):
            if perm == 'w':
                raise error, "Anonymous aims to be a read-only user."
            else:
                raise error, 'No such permission "%s".' %perm
        assert os.path.isdir(homedir), 'No such directory: "%s".' %homedir        
        if self.has_user('anonymous'):
            raise error, 'User anonymous already exists.'
        dic = {'pwd'  : '',
               'home' : homedir,
               'perm' : perm
                }
        self.user_table['anonymous'] = dic

    def validate_authentication(self, username, password):
        return self.user_table[username]['pwd'] == password   

    def has_user(self, username):        
        return self.user_table.has_key(username)
        
    def get_home_dir(self, username):
        return self.user_table[username]['home']

    def r_perm (self, username, obj):
        return 'r' in self.user_table[username]['perm']

    def w_perm (self, username, obj):
        return 'w' in self.user_table[username]['perm']
    

# system dependent authorizers

##    if os.name == 'posix':
##        class unix_authorizer:
##            """Interface to UNIX user account and password database
##            (users must be created previously)."""
##
##            def __init__(self):
##                raise NotImplementedError
##
##            
##    if os.name == 'nt':
##        class winNT_authorizer:
##            """Interface to Windows NT user account and password
##            database (users must be created previously).
##            """
##
##            def __init__(self):
##                raise NotImplementedError


# --- FTP

class ftp_handler(asynchat.async_chat):
    """A class representing the server-protocol-interpreter (server-PI, see RFC 959).
    Every time a new connection occurs ftp_server class will create a new  
    instance of this class that will handle the current PI session.
    """

    authorizer = dummy_authorizer()
    msg_connect = "Pyftpd %s" %__ver__
    msg_login = ""
    msg_quit = ""

    def __init__(self):

        # session attributes
        self.fs = abstracted_fs()        
        self.in_producer_queue = None
        self.out_producer_queue = None
        self.authenticated = False
        self.username = "" 
        self.max_login_attempts = [3, 0] # (value, counter)
        self.current_type = 'a'
        self.restart_position = 0
        self.quit_pending = False

        # dtp attributes
        self.dtp_ready = False
        self.dtp_server = None
        self.data_channel = None  

    def __del__(self):
        self.debug("ftp_handler.__del__()")

    def __str__(self):
        return "<ftp_handler listening on %s:%s (fd=%d)>" %(self.remote_ip,
                                                            self.remote_port,
                                                            self._fileno)

    def handle(self, socket_object):
        asynchat.async_chat.__init__(self, conn=socket_object)  
        self.remote_ip, self.remote_port = self.socket.getpeername()
        self.in_buffer = ""
        self.out_buffer = ""
        self.ac_in_buffer_size = 4096
        self.ac_out_buffer_size = 4096
        self.set_terminator("\r\n")
               
        self.push('220-%s.\r\n' %self.msg_connect)        
        self.respond("220 Ready.")

    # --- asynchat/asyncore overridden methods

    def readable (self):
        return (len(self.ac_in_buffer) <= self.ac_in_buffer_size)

    def writable(self):
        return len(self.ac_out_buffer) or len(self.producer_fifo) or (not self.connected)   

    def collect_incoming_data(self, data):        
        self.in_buffer = self.in_buffer + data

    def found_terminator(self):        
        line = self.in_buffer.strip()
        self.in_buffer = ""
        
        cmd = line.split(' ')[0].upper()        
        space = line.find(' ')
        if space != -1:
            arg = line[space + 1:]
        else:
            arg = ""

        if cmd != 'PASS':
            self.logline("<== %s" %line)
        else:
            self.logline("<== %s %s" %(cmd, '*'*6))

        if (not self.authenticated):
            if cmd in ('USER', 'PASS', 'HELP', 'QUIT'):
                method = getattr(self, 'ftp_'+cmd, None)          
                method(arg) # callback                    
            elif cmd in proto_cmds:
                self.respond("530 Log in with USER and PASS first")            
            else:
                self.cmd_not_understood(line)

        elif (self.authenticated) and (cmd in proto_cmds):
            method = getattr(self, 'ftp_'+cmd, None)          
            if not method:
                self.log('warning: not implemented method "ftp_%s"' %cmd)
                self.cmd_not_understood(line)
            else:
                method(arg) # callback

        else:
            # recognize "abor" command:            
            # ['\xff', '\xf4', '\xf2', 'A', 'B', 'O', 'R']                        
            # if map(ord, line.upper()) == [255, 244, 242, 65, 66, 79, 82]:
                # self.ftp_ABOR("")
                # return
            if line.upper().find('ABOR') != -1:
                self.ftp_ABOR("")
            else:
                self.cmd_not_understood(line)

    def handle_expt(self):
        # I didn't well understood when and why it is called and I'm not sure what
        # could I do here. asyncore documentation says:
        # > Called when there is out of band (OOB) data for a socket connection.
        # > This will almost never happen, as OOB is tenuously supported and rarely used.
        # OOB? How do I have to manage that?
        # I made a research but still can't know what to do. Even in SocketServer module
        # OOB is an open unsolved problem.       
        # Anyway, I assume this as a bad event, so I close the current session.
        self.debug("ftp_handler.handle_expt()")        
        self.close()

    def handle_error(self):
        self.debug("ftp_handler.handle_error()")        
        f = StringIO.StringIO()
        traceback.print_exc(file=f)
        self.debug(f.getvalue())

        asynchat.async_chat.close(self)

    def handle_close(self):
        self.debug("ftp_handler.handle_close()")
        self.close()

    def close(self):
        self.debug("ftp_handler.close()")
       
        if self.dtp_server:
            self.dtp_server.close()
            self.dtp_server = None
                
        if self.data_channel:
            self.data_channel.close()
            self.data_channel = None

        self.log("Disconnected.")
        asynchat.async_chat.close(self)


    # --- callbacks
    
    def on_dtp_connection(self):
        # Called every time data channel connects (does not matter
        # if active or passive). Here we check for data queues.
        # If we got data to send we just push it into data channel.
        # If we got data to receive we enable data channel for receiving it.
        
        self.debug("ftp_handler.on_dtp_connection()")
        
        if self.dtp_server:
            self.dtp_server.close()
        self.dtp_server = None
        
        if self.out_producer_queue:
            if self.out_producer_queue[1]:
                self.log(self.out_producer_queue[1])                             
            self.data_channel.push_with_producer(self.out_producer_queue[0])            
            self.out_producer_queue = None

        elif self.in_producer_queue:
            if self.in_producer_queue[1]:
                self.log(self.in_producer_queue[1])
            self.data_channel.file_obj = self.in_producer_queue[0]
            self.data_channel.enable_receiving()
            self.in_producer_queue = None
    
    def on_dtp_close(self):
        # called every time close() method of dtp_handler() class
        # is called.
        
        self.debug("ftp_handler.on_dtp_close()")
        if self.data_channel:
            self.data_channel = None
        if self.quit_pending:
            self.close_when_done()
    
    # --- utility
    
    def respond(self, resp):  
        self.push(resp + '\r\n')
        self.logline('==> %s' % resp)
    
    def push_dtp_data(self, file_obj, msg=''):
        # Called every time a RETR, LIST or NLST is received, push data into
        # data channel. If data channel does not exists yet we queue up data
        # to send later. Data will then be pushed into data channel when 
        # "on_dtp_connection()" method will be called. 
        
        if self.data_channel:            
            self.respond("125 Data connection already open. Transfer starting.")
            if msg:
                self.log(msg)
            self.data_channel.push_with_producer(file_obj)
        else:
            self.respond("150 File status okay. About to open data connection.")
            self.debug("info: new producer queue added")
            self.out_producer_queue = (file_obj, msg)

    def cmd_not_understood(self, line):
        self.respond('500 Command "%s" not understood.' %line)

    def cmd_missing_arg(self):
        self.respond("501 Syntax error: command needs an argument.")
      
    def log(self, msg):
        log("[%s]@%s:%s %s" %(self.username, self.remote_ip, self.remote_port, msg))
    
    def logline(self, msg):
        logline("%s:%s %s" %(self.remote_ip, self.remote_port, msg))
    
    def debug(self, msg):
        debug(msg)


    # --- ftp

        # --- connection

    def ftp_PORT(self, line):        
        try:
            line = line.split(',')
            ip = ".".join(line[:4]).replace(',','.')
            port = (int(line[4]) * 256) + int(line[5])
        except:
            self.respond("500 Invalid PORT format.")
            return

        # FTP bouncing protection: drop if IP address does not match
        # the client's IP address.            
        if ip != self.remote_ip:
            self.respond("500 No FTP bouncing allowed.")
            return
        
        # if more than one PORT is received we create a new data
        # channel instance closing the older one
        if self.data_channel:
            asynchat.async_chat.close(self.data_channel)
        active_dtp(ip, port, self)        

    def ftp_PASV(self, line):
        # if more than one PASV is received we create a new data 
        # channel instance closing the older one
        if self.data_channel:
            asynchat.async_chat.close(self.data_channel)
            self.dtp_server = passive_dtp(self)
            return
            
        if not self.dtp_ready:
            self.dtp_server = passive_dtp(self)
        else:
            asynchat.async_chat.close(self.dtp_server)
            self.dtp_server = passive_dtp(self)

    def ftp_QUIT(self, line):
        if not self.msg_quit:
            self.respond("221 Goodbye.")
        else:
            self.push("221-%s\r\n" %self.msg_quit)
            self.respond("221 Goodbye.")

        # From RFC959 about 'QUIT' command:
        # > This command terminates a USER and if file transfer is not
        # > in progress, the server closes the control connection.  If
        # > file transfer is in progress, the connection will remain
        # > open for result response and the server will then close it.           
        if not self.data_channel:
            self.close_when_done()
        else:
            self.quit_pending = True


        # --- data transferring
        
    def ftp_LIST(self, line):
        # TODO: LIST/NLST commands are currently the mostly CPU-intensive blocking operations.
        # A sort of cache could be implemented (take a look at dircache module).
        
        if line:
            # some FTP clients (like Konqueror or Nautilus) erroneously use
            # /bin/ls-like LIST formats (e.g. "LIST -l", "LIST -al" and so on...).
            # If this happens we LIST the current working directory.
           
            if line.lower() in ("-a", "-l", "-al", "-la"):
                path = self.fs.normalize(self.fs.cwd)
                line = self.fs.cwd
            else:
                path = self.fs.normalize(line)
                line = self.fs.translate(line)
        else:            
            path = self.fs.normalize(self.fs.cwd)
            line = self.fs.cwd

        if not self.fs.exists(path):
            self.log('FAIL LIST "%s". No such directory.' %line)
            self.respond('550 No such directory: "%s".' %line)
            return
        
        try:
            file_obj = self.fs.get_list_dir(path)
        except OSError, err:           
            self.log('FAIL LIST "%s". %s: "%s".' % (line, err.strerror, err.filename))
            self.respond ('550 I/O server side error: %s' %err.strerror)
            return
            
        self.push_dtp_data(file_obj, 'OK LIST "%s". Transfer starting.' %line)

    def ftp_NLST(self, line):       
        if line:
            path = self.fs.normalize(line)
            line = self.fs.translate(line)
        else:            
            path = self.fs.normalize(self.fs.cwd)
            line = self.fs.cwd

        if not self.fs.is_dir(path):
            self.log('FAIL NLST "%s". No such directory.' %line)
            self.respond('550 No such directory: "%s".' %line)
            return

        try:
            file_obj = self.fs.get_list_dir(path)
        except OSError, err:           
            self.log('FAIL NLST "%s". %s: "%s".' % (line, err.strerror, err.filename))
            self.respond ('550 I/O server side error: %s' %err.strerror)
            return                

        file_obj = self.fs.get_nlst_dir(path)
        self.push_dtp_data(file_obj, 'OK NLST "%s". Transfer starting.' %line)

    def ftp_RETR(self, line):
        if not line:
            self.cmd_missing_arg()
            return
                   
        file = self.fs.normalize(line)

        if not self.fs.is_file(file):
            self.log('FAIL RETR "%s". No such file.' %line)
            self.respond('550 No such file: "%s".' %line)
            return

        if not self.authorizer.r_perm(self.username, file):
            self.log('FAIL RETR "s". Not enough priviledges' %line)
            self.respond ("553 Can't RETR: not enough priviledges.")
            return
        
        try:
            file_obj = open(file, 'rb')
        except IOError, err:
            self.log('FAIL RETR "%s". I/O error: %s' %(line, err.strerror))
            self.respond ('553 I/O server side error: %s' %err.strerror)
            return
        
        if self.restart_position:
            try:
                file_obj.seek(self.restart_position)
            except:
                pass
            self.restart_position = 0
                    
        self.push_dtp_data(file_obj, 'OK RETR "%s". Download starting.' %self.fs.translate(line))        

    def ftp_STOR(self, line, rwa='w', mode='b'):
        if not line:
            self.cmd_missing_arg()
            return
        
        # A resume could occur in case of APPE or REST commands.
        # In that case we have to open file object in different ways:
        # STOR: rwa = 'w'
        # APPE: rwa = 'a'
        # REST: rwa = 'r+' (to permit seeking on file object)
        
        file = self.fs.normalize(line)

        if not self.authorizer.w_perm(self.username, os.path.split(file)[0]):
            self.log('FAIL STOR "%s". Not enough priviledges' %line)
            self.respond ("553 Can't STOR: not enough priviledges.")
            return

        if self.restart_position:
            rwa = 'r+'
        
        try:            
            file_obj = open(file, rwa + mode)
        except IOError, err:
            self.log('FAIL STOR "%s". I/O error: %s' %(line, err.strerror))
            self.respond ('553 I/O server side error: %s' %err.strerror)
            return
        
        if self.restart_position:
            try:
                file_obj.seek(self.restart_position)
            except:
                pass
            self.restart_position = 0
            
        if self.data_channel:
            self.respond("125 Data connection already open. Transfer starting.")
            self.log('OK STOR "%s". Upload starting.' %self.fs.translate(line))
            self.data_channel.file_obj = file_obj
            self.data_channel.enable_receiving()
        else:
            self.debug("info: new producer queue added.")
            self.respond("150 File status okay. About to open data connection.")
            self.in_producer_queue = (file_obj, 'OK STOR "%s". Upload starting.' %self.fs.translate(line))

    def ftp_STOU(self, line):
        "store a file with a unique name"
        # note: RFC 959 prohibited STOU parameters, but this prohibition is obsolete.
        # note2: RFC 959 wants ftpd to respond with code 250 but I've seen a
        # lot of FTP servers responding with 125 or 150, and this is a better choice, imho,
        # because STOU works just like STOR.
        
        # create file with a suggested name
        if line:
            file = (self.fs.normalize (line))
            if not self.fs.exists (file):
                resp = line
            else:
                x = 0
                while 1:                    
                    file = self.fs.normalize (line + '.' + str(x))
                    if not self.fs.exists(file):
                        resp = line + '.' + str(x)
                        break
                    else:
                        x += 1

        # create file with a brand new name
        else:
            x = 0
            while 1:                
                file = self.fs.normalize (self.fs.cwd + '.' + str(x))
                if not self.fs.exists(file):
                    resp = '.' + str(x)
                    break
                else:
                    x += 1            

        # now just acts like STOR excepting that restarting isn't allowed
        if not self.authorizer.w_perm(self.username, os.path.split(file)[0]):
            self.log('FAIL STOU "%s". Not enough priviledges' %line)
            self.respond ("553 Can't STOU: not enough priviledges.")
            return
        try:            
            file_obj = open(file, 'wb')
        except IOError, err:
            self.log('FAIL STOU "%s". I/O error: %s' %(line, err.strerror))
            self.respond ('553 I/O server side error: %s' %err.strerror)
            return

        if self.data_channel:
            self.respond("125 %s" %resp)
            self.log('OK STOU "%s". Upload starting.' %self.fs.translate(line))
            self.data_channel.file_obj = file_obj
            self.data_channel.enable_receiving()
        else:
            self.debug("info: new producer queue added.")
            self.respond("150 %s" %resp)
            self.in_producer_queue = (file_obj, 'OK STOU "%s". Upload starting.' %self.fs.translate(line))

            
    def ftp_APPE(self, line):
        if not line:
            self.cmd_missing_arg()
            return        
        self.ftp_STOR(line, rwa='a')
        
    def ftp_REST(self, line):
        if not line:
            self.cmd_missing_arg()
            return
        try:
            value = int(line)
            if value < 0:
                raise
            self.respond("350 Restarting at position %s. Now use RETR/STOR for resuming." %value)
            self.restart_position = value
        except:
            self.respond("501 Invalid number of parameters.")

    def ftp_ABOR(self, line):
        if self.dtp_server:
            self.dtp_server.close()
            self.dtp_server = None
            
        if self.data_channel:
            self.data_channel.close()
            self.data_channel = None
            
        self.log("ABOR received.")
        self.respond('226 ABOR command successful.')


        # --- authentication

    def ftp_USER(self, line):
        if not line:
            self.cmd_missing_arg()
            return
        # warning: we always treat anonymous user as lower-case string.
        if line.lower() == "anonymous":
            self.username = "anonymous"
        else:
            self.username = line
        self.respond('331 Username ok, send password.')        

    def ftp_PASS(self, line):
        # TODO - brute force protection: 'freeze'/'sleep' (without blocking the main loop)
        #   PI for a certain amount of time if authentication fails.
        
        if not self.username:
            self.respond("503 Login with USER first")
            return
        
        if self.username == 'anonymous':
            line = ''
            
        if self.authorizer.has_user(self.username):
            
            if self.authorizer.validate_authentication(self.username, line):
                if not self.msg_login:
                    self.respond("230 User %s logged in." %self.username)                    
                else:
                    self.push("230-%s\r\n" %self.msg_login)
                    self.respond("230 Welcome.")
                    
                self.authenticated = True
                self.max_login_attempts[1] = 0
                self.fs.root = self.authorizer.get_home_dir(self.username)
                self.log("User %s logged in." %self.username)
                
            else:              
                self.max_login_attempts[1] += 1
                
                if self.max_login_attempts[0] == self.max_login_attempts[1]:
                    self.log("Maximum login attempts. Disconnecting.")
                    self.respond("530 Maximum login attempts. Disconnecting.")
                    self.close()
                else:
                    self.respond("530 Authentication failed.")
                    self.username = ""
                
        else:
            if self.username.lower() == 'anonymous':
                self.respond("530 Anonymous access not allowed.")
                self.log('Authentication failed: anonymous access not allowed.')
            else:
                self.respond("530 Authentication failed.")
                self.log('Authentication failed: unknown username "%s".' %self.username)
                self.username = ""

    def ftp_REIN(self, line):
        self.authenticated = False
        self.username = ""
        self.max_login_attempts[1] = 0
        self.respond("230 Ready for new user.")
        self.log("REIN account information was flushed.")


        # --- filesystem operations

    def ftp_PWD(self, line):
        self.respond('257 "%s" is the current directory.' %self.fs.cwd)

    def ftp_CWD(self, line):
        if not line:
            line = '/'
        if self.fs.change_dir(line):
            self.log('OK CWD "%s"' %self.fs.cwd)
            self.respond('250 "%s" is the current directory.' %self.fs.cwd)
        else:           
            self.respond("550 No such directory.")            

    def ftp_CDUP(self, line):
        if self.fs.cwd == '/':
            self.respond('250 "/" is the current directory.')
        else:
            self.fs.cdup()
            self.respond('257 "%s" is the current directory.' %self.fs.cwd)
        self.log('OK CWD "%s"' %self.fs.cwd)

    def ftp_SIZE(self, line):
        if not line:
            self.cmd_missing_arg()
            return
           
        size = self.fs.get_size(self.fs.normalize(line))
        if size >= 0:
            self.log('OK SIZE "%s"' %self.fs.translate(line))
            self.respond("213 %s" %size)
        else:
            self.log('FAIL SIZE "%s". No such file.' %self.fs.translate(line))
            self.respond("550 No such file.")

    def ftp_MDTM(self, line):
        # get file's last modification time (not documented inside RFC959
        # but used in a lot of ftpd implementations)
        if not line:
            self.cmd_missing_arg()
            return
        path = self.fs.normalize(line)
        if not self.fs.is_file(path):
            self.respond("550 No such file.")
        else:
            lmt = time.strftime("%Y%m%d%H%M%S", time.localtime(self.fs.get_lastm_time (path)))
            self.respond("213 %s" %lmt)
    
    def ftp_MKD(self, line):
        if not line:
            self.cmd_missing_arg()
            return

        path = self.fs.normalize(line)
        
        if not self.authorizer.w_perm(self.username, os.path.split(path)[0]):
            self.log('FAIL MKD "%s". Not enough priviledges.' %line)
            self.respond ("553 Can't MKD: not enough priviledges.")
            return
       
        if self.fs.create_dir(path):
            self.log('OK MKD "%s".' %self.fs.translate(line))
            self.respond("257 Directory created.")            
        else:
            self.log('FAIL MKD "%s".' %self.fs.translate(line))
            self.respond("550 Can't create directory.")

    def ftp_RMD(self, line):   
        if not line:
            self.cmd_missing_arg()
            return

        path = self.fs.normalize(line)

        if path == self.fs.root:
            self.respond("550 Can't remove root directory.")
            return
                    
        if not self.authorizer.w_perm(self.username, path):
            self.log('FAIL RMD "%s". Not enough priviledges.' %line)
            self.respond ("553 Can't RMD: not enough priviledges.")
            return
       
        if self.fs.remove_dir(path):
            self.log('OK RMD "%s".' %self.fs.translate(line))
            self.respond("250 Directory removed.")
        else:
            self.log('FAIL RMD "%s".' %self.fs.translate(line))
            self.respond("550 Can't remove directory.")

    def ftp_DELE(self, line):
        if not line:
            self.cmd_missing_arg()
            return

        path = self.fs.normalize(line)
            
        if not self.authorizer.w_perm(self.username, path):
            self.log('FAIL DELE "%s". Not enough priviledges.' % self.fs.translate(line))
            self.respond ("553 Can't DELE: not enough priviledges.")            
            return
           
        if self.fs.remove_file(path):
            self.log('OK DELE "%s".' %self.fs.translate(line))
            self.respond("250 File removed.")
        else:
            self.log('FAIL DELE "%s".' %self.fs.translate(line))
            self.respond("550 Can't remove file.")

    def ftp_RNFR(self, line):
        if not line:
            self.cmd_missing_arg()
            return

        if self.fs.exists(self.fs.normalize(line)):
            self.fs.rnfr = self.fs.translate(line)
            self.respond("350 Ready for destination name")
        else:
            self.respond("550 No such file/directory.")

    def ftp_RNTO(self, line):
        # TODO - actually RNFR/RNTO commands could also be used to *move* a file/directory
        # instead of just renaming them. RFC959 doesn't tell if this must be allowed or not
        # (I believe not). Check about it.
        
        if not line:
            self.cmd_missing_arg()
            return

        if not self.fs.rnfr:
            self.respond("503 Bad sequence of commands: use RNFR first.")
            return
       
        if not self.authorizer.w_perm(self.username, self.fs.normalize(self.fs.rnfr)):
            self.log('FAIL RNFR/RNTO "%s ==> %s". Not enough priviledges for renaming.'
                     %(self.fs.rnfr, self.fs.translate(line)))
            self.respond ("553 Can't RNTO: not enough priviledges.")
            self.fs.rnfr = None
            return

        src = self.fs.normalize(self.fs.rnfr)
        dst = self.fs.normalize(line)
     
        if self.fs.rename(src, dst):
            self.log('OK RNFR/RNTO "%s ==> %s".' %(self.fs.rnfr, self.fs.translate(line)))
            self.respond("250 Renaming ok.")
        else:
            self.log('FAIL RNFR/RNTO "%s ==> %s".' %(self.fs.rnfr, self.fs.translate(line)))
            self.respond("550 Renaming failed.")
        self.fs.rnfr = None

        # --- others       

    def ftp_TYPE(self, line):
        if not line:
            self.cmd_missing_arg()
            return

        line = line.lower()        
        if line in type_map:
            self.respond("200 Type set to: %s." %type_map[line])
            self.current_type = line
        else:
            self.respond('550 Unknown / unsupported type "%s".' %line)
            
    def ftp_STRU(self, line):
        # obsolete (backward compatibility with older ftp clients)
        if not line:
            self.cmd_missing_arg()
            return        
        if line in ('f','F'):            
            self.respond ('200 File transfer structure set to: F.')
        else:
            self.respond ('504 Unimplemented STRU type.')
    
    def ftp_MODE(self, line):
        # obsolete (backward compatibility with older ftp clients)
        if not line:
            self.cmd_missing_arg()
            return        
        if line in ('s', 'S'):
            self.respond('200 Trasfer mode set to: S')
        else:
            self.respond('504 Unimplemented MODE type.')

    def ftp_STAT(self, line):
        self.push('211-%s %s status:\r\n' %(__pname__, __ver__))
        s = '\tConnected to: %s:%s\r\n' %(self.socket.getpeername()[0], self.socket.getpeername()[1])
        s+= '\tLogged in as: %s\r\n' %self.username
        s+= '\tCurrent type: %s\r\n' %type_map[self.current_type]
        s+= '\tCurrent STRUcture: File\r\n' 
        s+= '\tTransfer MODE: Stream\r\n'
        self.push(s)
        self.respond("211 End of status.")

    def ftp_NOOP(self, line):
        self.respond("250 I succesfully done nothin'.")

    def ftp_SYST(self, line):
        # we always assume that the running system is unix(like)
        # even if it's different because we always respond to LIST
        # command with a "/bin/ls -al" like output.
        self.respond("215 UNIX Type: L8")

    def ftp_ALLO(self, line):
        # obsolete (always respond with 202)
        self.respond("202 ALLO command succesful.")
           
    def ftp_HELP(self, line):
        self.push('214-The following commands are recognized:\r\n')
        self.push(helper_string)
        self.push("* argument required.\r\n")
        self.respond("214 Help command succesful.")       
    
        # --- support for deprecated cmds
    
    def ftp_XCUP(self, line):
        self.ftp_CDUP(line)
    
    def ftp_XCWD(self, line):
        self.ftp_CWD(line)
    
    def ftp_XMKD(self, line):
        self.ftp_MKD(line)
    
    def ftp_XPWD(self, line):
        self.ftp_PWD(line)

    def ftp_XRMD(self, line):
        self.ftp_RMD(line)

    

class ftp_server(asynchat.async_chat):
    """The base class for the backend."""

    def __init__(self, address, handler):
        asynchat.async_chat.__init__(self)
        self.address = address
        self.handler = handler
        self.create_socket(socket.AF_INET, socket.SOCK_STREAM)    
        self.bind(self.address)
        self.listen(5)

    def __del__(self):
        debug("ftp_server.__del__()")        
        
    def serve_forever(self): 
        log("Serving FTP on %s:%s." %self.socket.getsockname())
        if os.name == 'posix':
            self.set_reuse_addr()
        # here we try to use poll(), if it exists, else we'll use select()
        asyncore.loop(timeout=1, use_poll=True)          
            
    def handle_accept(self):
        debug("handle_accept()")        
        sock_obj, addr = self.accept()
        log("[]%s:%s connected." %addr)
        handler = self.handler().handle(sock_obj)

    def writable(self):
        return 0

    def readable(self):        
        return self.accepting

    def handle_error(self):        
        debug("ftp_server.handle_error()")
        f = StringIO.StringIO()
        traceback.print_exc(file=f)
        debug(f.getvalue())
        self.close()


class passive_dtp(asynchat.async_chat):
    "Base class for passive-DTP backend"

    def __init__(self, cmd_channel):           
        asynchat.async_chat.__init__(self)
        
        self.cmd_channel = cmd_channel
        self.debug = self.cmd_channel.debug     

        ip = self.cmd_channel.getsockname()[0]
        self.create_socket(socket.AF_INET, socket.SOCK_STREAM)
        # by using 0 as port number value we let socket choose a free random port
        self.bind((ip, 0))
        self.listen(5)        
        self.cmd_channel.dtp_ready = True      
        port = self.socket.getsockname()[1]
        self.cmd_channel.respond('227 Entering passive mode (%s,%d,%d)' %(
                ip.replace('.', ','), 
                port / 256, 
                port % 256
                ))

    def __del__(self):
        debug("passive_dtp.__del__()")

   
    # --- connection / overridden
    
    def handle_accept(self):        
        sock_obj, addr = self.accept()
        
        # PASV connection theft protection: check the origin of data connection.
        # We have to drop the incoming data connection if remote IP address 
        # does not match the client's IP address.
        if self.cmd_channel.remote_ip != addr[0]:
            log("info: PASV connection theft attempt occurred from %s:%s." %(addr[0], addr[1]))
            try:
                # sock_obj.send('500 Go hack someone else, dude.')
                sock_obj.close()
            except:
                pass        
        else:
            debug("passive_dtp.handle_accept()")
            self.cmd_channel.dtp_ready = False
            handler = dtp_handler(sock_obj, self.cmd_channel)
            self.cmd_channel.data_channel = handler
            self.cmd_channel.on_dtp_connection()
            # self.close()                    
        
    def writable(self):
        return 0        

    def handle_expt(self):
        debug("passive_dtp.handle_expt()")
        self.close()

    def handle_error(self):
        debug("passive_dtp.handle_error()")
        f = StringIO.StringIO()
        traceback.print_exc(file=f)
        debug(f.getvalue())
        self.close()
            
    def handle_close(self):
        debug("passive_dtp.handle_close()")
        self.close()

    def close(self):
        debug("passive_dtp.close()")
        self.del_channel()
        self.socket.close()



class active_dtp(asynchat.async_chat):
    "Base class for active-DTP backend"    
   
    def __init__(self, ip, port, cmd_channel):        
        asynchat.async_chat.__init__(self)        
        self.cmd_channel = cmd_channel       
        self.create_socket(socket.AF_INET, socket.SOCK_STREAM)
        try:
            self.connect((ip, port))
        except:
            self.cmd_channel.respond("500 Can't connect to %s:%s." %(ip, port))
            self.close()     

    def __del__(self):
        debug("active_dtp.__del__()")

    
    # --- connection / overridden            
        
    def handle_connect(self):        
        debug("active_dtp.handle_connect()")
        self.cmd_channel.respond('200 PORT command successful.')
        handler = dtp_handler(self.socket, self.cmd_channel)        
        self.cmd_channel.data_channel = handler        
        self.cmd_channel.on_dtp_connection()
        # self.close() --> (done automatically)
        

    def handle_expt(self):        
        debug("active_dtp.handle_expt()")        
        self.cmd_channel.respond ("425 Can't establish data connection.")
        self.close()

    def handle_error(self):        
        debug("active_dtp.handle_error()")             
        f = StringIO.StringIO()
        traceback.print_exc(file=f)
        debug(f.getvalue())
        self.close()
            
    def handle_close(self):
        debug("active_dtp.handle_close()")
        self.close()

    def close(self):
        debug("active_dtp.close()")
        self.del_channel()
        self.socket.close()



class dtp_handler(asynchat.async_chat):
    """class handling server-data-transfer-process (server-DTP, see RFC 959)
    managing data-transfer operations.
    """
   
    def __init__(self, sock_obj, cmd_channel):        
        asynchat.async_chat.__init__(self, conn=sock_obj)
       
        self.cmd_channel = cmd_channel
                
        self.file_obj = None
        self.in_buffer_size = 8192
        self.out_buffer_size  = 8192
        
        self.enable_receive = False       
        self.transfer_finished = False
        self.tot_bytes_sent = 0
        self.tot_bytes_received = 0        
        self.data_wrapper = self.binary_data_wrapper
    
    def log(self, msg):
        log(msg)

    def debug(self, msg):
        debug(msg)

    def __del__(self):
        debug("dtp_handler.__del__()")       


    # --- utility methods
    
    def enable_receiving(self):          
        if self.cmd_channel.current_type == 'a':
            self.data_wrapper = self.ASCII_data_wrapper
        else:
            self.data_wrapper = self.binary_data_wrapper
        self.enable_receive = True
            
    def ASCII_data_wrapper(self, data):        
        return data.replace('\r\n', os.linesep)
    
    def binary_data_wrapper(self, data):
        return data

    # --- connection / overridden
    
    def readable (self):
        return (len(self.ac_in_buffer) <= self.ac_in_buffer_size) and self.enable_receive

    def writable(self):
        return len(self.ac_out_buffer) or len(self.producer_fifo) or (not self.connected)

    def push_with_producer (self, file_obj):
        self.file_obj = file_obj
        producer = file_producer (self.file_obj, self.cmd_channel.current_type)
        self.producer_fifo.push (producer)
        self.close_when_done()
        self.initiate_send()

    def initiate_send (self):
        obs = self.ac_out_buffer_size
        # try to refill the buffer
        if (len (self.ac_out_buffer) < obs):
            self.refill_buffer()

        if self.ac_out_buffer and self.connected:
            # try to send the buffer
            try:
                num_sent = self.send (self.ac_out_buffer[:obs])
                if num_sent:
                    self.ac_out_buffer = self.ac_out_buffer[num_sent:]
                    
                    # --- edit
                    self.tot_bytes_sent += num_sent
                    # --- /edit

            except socket.error, why:
                self.handle_error()
                return

    def refill_buffer (self):
        while 1:            
            if len(self.producer_fifo):
                p = self.producer_fifo.first()                
                if p is None:
                    if not self.ac_out_buffer:                        
                        self.producer_fifo.pop()
                        
                        # --- edit                                              
                        self.transfer_finished = True
                        # --- /edit
                        
                        self.close()
                    return
                elif isinstance(p, str):
                    self.producer_fifo.pop()
                    self.ac_out_buffer = self.ac_out_buffer + p
                    return
                data = p.more()
                if data:
                    self.ac_out_buffer = self.ac_out_buffer + data
                    return
                else:
                    self.producer_fifo.pop()
            else:
                return     
       
    def handle_read (self):    
        chunk = self.recv(self.in_buffer_size)  
        self.tot_bytes_received += len(chunk)
        if not chunk:
            self.transfer_finished = True                     
            # self.close()  <-- asyncore.recv() already do that...
            return
        
        # --- Writing on file
        # While we're writing on the file an exception could occur in case that
        # filesystem gets full but this rarely happens and a "try/except"
        # statement seems wasted to me.
        # Anyway if this happens we let handle_error() method handle this exception.
        # Remote client will just receive a generic 426 response then it will be
        # disconnected.
        self.file_obj.write(self.data_wrapper(chunk))           

    def handle_expt(self):
        debug("dtp_handler.handle_expt()")
        self.close()

    def handle_error(self):        
        debug("dtp_handler.handle_error()")        
        f = StringIO.StringIO()
        traceback.print_exc(file=f)
        debug(f.getvalue())
        self.close()
            
    def handle_close(self):
        debug("dtp_handler.handle_close()")
        self.transfer_finished = True
        self.close()
        
    def close(self):        
        debug("dtp_handler.close()")
        tot_bytes = self.tot_bytes_sent + self.tot_bytes_received

        # If we used channel for receiving we assume that transfer is finished
        # when client close connection, if we used channel for sending we have
        # to check that all data has been sent (responding with 226) or not
        # (responding with 426).
        if self.enable_receive:
            self.cmd_channel.respond("226 Transfer complete.")
            self.cmd_channel.log("Trasfer complete. %d bytes transmitted." %tot_bytes)
        else:            
            if self.transfer_finished:
                self.cmd_channel.respond("226 Transfer complete.")
                self.cmd_channel.log("Trasfer complete. %d bytes transmitted." %tot_bytes)
            else:
                self.cmd_channel.respond("426 Connection closed, transfer aborted.")
                self.cmd_channel.log("Trasfer aborted. %d bytes transmitted." %tot_bytes)

        try: self.file_obj.close()
        except: pass
        
        # to permit gc...
        del self.data_wrapper
        
        asynchat.async_chat.close(self)
        
        self.cmd_channel.data_channel = None
        self.cmd_channel.on_dtp_close()



# --- file producer

# I get it from Sam Rushing's Medusa-framework.
# It's like asynchat.simple_producer class excepting that it works
# with file(-like) objects instead of strings.

class file_producer:
    "Producer wrapper for file[-like] objects."

    out_buffer_size = 65536

    def __init__ (self, file, type=''):
        self.done = 0
        self.file = file
        if type == 'a':
            self.data_wrapper = self.ASCII_data_wrapper
        else:
            self.data_wrapper = self.binary_data_wrapper
                       
    def more (self):        
        if self.done:
            return ''
        else:
            data = self.data_wrapper()
            if not data:              
                # to permit gc...
                self.file = self.data_wrapper = None                
                self.done = 1                
                return ''
            else:
                return data
                
    def binary_data_wrapper(self):
        return self.file.read (self.out_buffer_size)

    def ASCII_data_wrapper(self):        
        return self.file.read (self.out_buffer_size).replace(os.linesep, '\r\n')
        


# --- filesystem

def __test_compatibility():
    try:
        # Availability Macintosh, Unix, Windows.
        os.rmdir
        os.mkdir
        os.remove
        os.rename
        os.listdir
        os.stat
        # Availability Python >= 1.5.2       
        os.path.getsize
        os.path.getmtime
    except AttributeError:
        raise error, "Incompatible Python release."    
# __test_compatibility()


class abstracted_fs:

    def __init__(self):
        self.root = None
        self.cwd = '/'
        self.rnfr = None
        
    # def __del__(self):
        # debug("abstracted_fs.__del__()")

    def normalize(self, path):
        if path == '':
            return ''
        # absolute pathname
        elif path.startswith('/'):
            if path == '/':
                return self.root
            else:
                return self.root + os.path.normpath(path)
        # relative pathname
        else:
            if self.cwd == '/':
                return self.root + os.path.normpath(self.cwd) + os.path.normpath(path)
            else:
                return self.root + os.path.normpath(self.cwd) + os.path.normpath('/' + path)
            
    def translate(self, path):
        if not path:
            return self.cwd       
        # absolute pathname
        elif path.startswith('/'):
            if path.endswith('/') and len(path) > 1:
                return path[:-1]
            else:
                return path            
        # relative pathname
        else:
            if self.cwd == '/':
                return self.cwd + path
            else:
                return self.cwd + '/' + path

    def exists(self, path):
        return os.path.exists(path)
        
    def is_file(self, file):
        if not self.exists(file):
            return 0
        return os.path.isfile(file)

    def is_dir(self, path):
        if not self.exists(path):
            return 0
        return os.path.isdir(path)

    def change_dir(self, line):
        if line == '/':
            self.cwd = '/'
            return 1
        else:
            path = self.normalize(line)
            if self.is_dir(path):
                self.cwd = self.translate(line)
                return 1
            else:            
                return 0
            
    def cdup(self):
        parent = os.path.split(self.cwd)[0]
        self.cwd = parent
        
    def create_dir(self, path):
        try:
            os.mkdir(path)
            return 1
        except:
            return 0
            
    def remove_dir(self, path):
        try:
            os.rmdir(path)
            return 1
        except:
            return 0
            
    def remove_file(self, path):
        try:
            os.remove(path)
            return 1
        except:
            return 0
    
    def get_size(self, path):
        try:
            return os.path.getsize(path)            
        except:
            return -1

    def get_lastm_time(self, path):
        try: 
            return os.path.getmtime(path)
        except:
            return 0
           
    def rename(self, src, dst):
        try:
            os.rename(src, dst)
            return 1
        except:
            return 0
    
    def get_nlst_dir(self, path):
        # ** warning: CPU-intensive blocking operation. You could want to override this method.

        f = StringIO.StringIO()
        # if this fails we handle exception in ftp_handler class
        listing = os.listdir(path)
        for elem in listing:
            f.write(elem + '\r\n')
        f.seek(0)
        return f
    
    def get_list_dir(self, path):
        'Emulates unix "ls" command'

        # ** warning: CPU-intensive blocking operation. You could want to override this method.
        
        # For portability reasons permissions, hard links numbers, owners and groups listed
        # by this method are static and unreliable but it shouldn't represent a problem for
        # most ftp clients around.
        # If you want reliable values on unix systems override this method and use other attributes
        # provided by os.stat()
        #
        # How LIST appears to client:
        # -rwxrwxrwx   1 owner    group         7045120 Sep 02  3:47 music.mp3
        # drwxrwxrwx   1 owner    group               0 Aug 31 18:50 e-books
        # -rwxrwxrwx   1 owner    group             380 Sep 02  3:40 module.py

        # if path is a file we return information about it
        if not self.is_dir(path):
            root, filename = os.path.split(path)
            path = root
            listing = [filename]
        else:
            # if this fails we handle exception in ftp_handler class
            listing = os.listdir(path)

        f = StringIO.StringIO()
        for obj in listing:
            name = os.path.join(path, obj)
            stat = os.stat(name)

            # stat.st_mtime could fail (-1) if file's last modification time is
            # too old, in that case we return local time as last modification time.
            try:
                mtime = time.strftime("%b %d %H:%M", time.localtime(stat.st_mtime))
            except ValueError:
                mtime = time.strftime("%b %d %H:%M")


            if os.path.isfile(name) or os.path.islink(name):
                f.write("-rw-rw-rw-   1 owner    group %15s %s %s\r\n" %(
                    stat.st_size,
                    mtime,
                    obj))
            else:
                f.write("drwxrwxrwx   1 owner    group %15s %s %s\r\n" %(
                    '0', # no size
                    mtime,
                    obj))
        f.seek(0)
        return f        


def test():
    # cmd line usage (provide a read-only anonymous ftp server):
    # python -m pyftpdlib.FTPServer
    authorizer = dummy_authorizer()   
    authorizer.add_anonymous(os.getcwd())    
    ftp_handler.authorizer = authorizer
    address = ('', 21)    
    ftpd = ftp_server(address, ftp_handler)
    ftpd.serve_forever()


if __name__ == '__main__':
    test()
