#!/usr/bin/env python
# FTPServer.py
#
#  pyftpdlib is released under the MIT license, reproduced below:
#  ======================================================================
#  Copyright (C) 2007 billiejoex <billiejoex@gmail.com>
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
RFC 959 asynchronous FTP server.

Usage:
>>> from pyftpdlib import FTPServer
>>> authorizer = FTPServer.DummyAuthorizer()
>>> authorizer.add_user('user', '12345', '/home/user', perm=('r', 'w'))
>>> authorizer.add_anonymous('/home/nobody')
>>> ftp_handler = FTPServer.FTPHandler
>>> ftp_handler.authorizer = authorizer
>>> address = ("127.0.0.1", 21)
>>> ftpd = FTPServer.FTPServer(address, ftp_handler)
>>> ftpd.serve_forever()
Serving FTP on 127.0.0.1:21
[]127.0.0.1:2503 connected.
127.0.0.1:2503 ==> 220 Ready.
127.0.0.1:2503 <== USER anonymous
127.0.0.1:2503 ==> 331 Username ok, send password.
127.0.0.1:2503 <== PASS ******
127.0.0.1:2503 ==> 230 User anonymous logged in.
[anonymous]@127.0.0.1:2503 User anonymous logged in.
127.0.0.1:2503 <== TYPE A
127.0.0.1:2503 ==> 200 Type set to: ASCII.
127.0.0.1:2503 <== PASV
127.0.0.1:2503 ==> 227 Entering passive mode (127,0,0,1,9,201).
127.0.0.1:2503 <== LIST
127.0.0.1:2503 ==> 150 File status okay. About to open data connection.
[anonymous]@127.0.0.1:2503 OK LIST "/". Transfer starting.
127.0.0.1:2503 ==> 226 Transfer complete.
[anonymous]@127.0.0.1:2503 Trasfer complete. 706 bytes transmitted.
127.0.0.1:2503 <== QUIT
127.0.0.1:2503 ==> 221 Goodbye.
[anonymous]@127.0.0.1:2503 Disconnected.
"""

# TODO - rewrite this better
# Overview:
#
# This file implements a fully functioning asynchronous FTP server as defined in
# RFC 959.  It has a hierarchy of classes which implement the backend
# functionality for the ftpd.
#
# A number of classes are provided:
#
#   [FTPServer] - the base class for the backend.
#
#   [FTPHandler] - a class representing the server-protocol-interpreter (server-PI, see RFC 959).
#       Every time a new connection occurs FTPServer class will create a new FTPHandler instance
#       that will handle the current PI session.
#
#   [ActiveDTP], [PassiveDTP] - base classes for active/passive-DTP backend.
#
#   [DTPHandler] - class handling server-data-transfer-process (server-DTP, see RFC 959)
#       managing data-transfer operations.
#
#   [DummyAuthorizer] - an "authorizer" is a class handling ftpd authentications and permissions.
#       It is used inside FTPHandler class to verify user passwords, to get user's home-directory
#       and to get permissions when a r/w I/O filesystem event occurs.
#       DummyAuthorizer" is the base authorizer class providing a platform independent interface
#       for managing "virtual-users".
#
#   [AbstractedFS] - class used to interact with file-system providing an high-level platform-independent
#       interface able to work on both DOS/UNIX-like file systems.
#
#   [Error] - base class for module exceptions.
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

# -------------
# OPEN PROBLEMS
# -------------
# - OOB data



# --------
# TIMELINE
# --------
# TODO - modify data
# 0.2.0 : ????-??-??
# 0.1.1 : 2007-03-07
# 0.1.0 : 2007-02-22


import asyncore
import asynchat
import socket
import os
import sys
import traceback
import time
import glob
try:
    import cStringIO as StringIO
except ImportError:
    import StringIO


__all__ = ['proto_cmds', 'Error', 'log', 'logline', 'debug', 'DummyAuthorizer',
           'FTPHandler', 'FTPServer', 'PassiveDTP', 'ActiveDTP', 'DTPHandler',
           'FileProducer', 'AbstractedFS']

__pname__   = 'Python FTP server library (pyftpdlib)'
__ver__     = '0.x.x' # TODO: set version
__state__   = 'beta'
__date__    = '????-??-??' # TODO: set date
__author__  = 'billiejoex <billiejoex@gmail.com>'
__license__ = 'see LICENSE file'


proto_cmds = {
            'ABOR' : "abort transfer",
            'ALLO' : "allocate space for file about to be sent (obsolete)",
            'APPE' : "* resume upload",
            'CDUP' : "go to parent directory",
            'CWD'  : "[*] change current directory",
            'DELE' : "* remove file",
            'HELP' : "print this help",
            'LIST' : "return a list of files",
            'MDTM' : "* get last modification time",
            'MODE' : "* set data transfer mode (obsolete)",
            'MKD'  : "* create directory",
            'NLST' : "list file names",
            'NOOP' : "just do nothing",            
            'PASS' : "* user's password",
            'PASV' : "start passive data channel",
            'PORT' : "start active data channel",
            'PWD'  : "get current dir",
            'QUIT' : "quit current session",
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
            'XCWD' : '== CWD (deprecated)',
            'XMKD' : '== MKD (deprecated)',
            'XPWD' : '== PWD (deprecated)',
            'XRMD' : '== RMD (deprecated)'
              }

proto_cmds.update(deprecated_cmds)

# TODO - modify this comment
# Not implemented commands:
# I've not implemented (and a lot of other FTP server
# did the same) ACCT, SITE and SMNT.
not_implemented_cmds = {
              'ACCT' : 'account permissions',
              'SITE' : 'site specific server services',
              'SMNT' : 'structure mount'
              }


class Error(Exception):
    """Base class for module exceptions."""

# TODO - provide other types of exception?

def __get_hs():
    x = []
    l = proto_cmds.keys()
    l.sort()
    for cmd in l:
        x.append('\t%-5s %s\r\n' %(cmd, proto_cmds[cmd]))
    return ''.join(x)
helper_string = __get_hs()


# --- loggers

def log(msg):
    "Log messages about FTPd for the end user"
    print msg

def logline(msg):
    "Log commands and responses passing through the command channel"
    print msg

def debug(msg):
    "Log debugging messages (function/method calls, traceback outputs and so on...)"
    #pass
    print "\t%s" %msg


# --- authorizers

class BasicAuthorizer:
    """This class exists just for documentation.  If you want to write your own
    authorizer you must provide all the following methods.
    """
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
   
class DummyAuthorizer:
    """An "authorizer" is a class handling authentications and permissions of
    the ftp server. It is used inside FTPHandler class for verifying user's
    password, getting users home directory and checking user permissions
    when a r/w I/O filesystem event occurs.
    DummyAuthorizer is the base authorizer providing a platform independent
    interface for managing "virtual" FTP users. According to methods provided
    by this class different kind on system-dependent authorizers could
    be optionally written from scratch subclassing this base class.
    """
    
    user_table = {}

    def add_user(self, username, password, homedir, perm=('r')):
        assert os.path.isdir(homedir), 'No such directory: "%s".' %homedir
        for i in perm:
            if i not in ('r', 'w'):
                raise Error('No such permission "%s".' %i)
        if self.has_user(username):
            raise Error('User "%s" already exists.' %username)
        dic = {'pwd'  : str(password),
               'home' : str(homedir),
               'perm' : perm
                }
        self.user_table[username] = dic
        
    def add_anonymous(self, homedir, perm=('r')):
        if perm not in ('', 'r'):
            if perm == 'w':
                raise Error("Anonymous aims to be a read-only user.")
            else:
                raise Error('No such permission "%s".' %perm)
        assert os.path.isdir(homedir), 'No such directory: "%s".' %homedir        
        if self.has_user('anonymous'):
            raise Error('User anonymous already exists.')
        dic = {'pwd'  : '',
               'home' : homedir,
               'perm' : perm
                }
        self.user_table['anonymous'] = dic

    def validate_authentication(self, username, password):
        return self.user_table[username]['pwd'] == password

    def has_user(self, username):        
        return username in self.user_table

    def get_home_dir(self, username):
        return self.user_table[username]['home']

    def r_perm(self, username, obj):
        return 'r' in self.user_table[username]['perm']

    def w_perm(self, username, obj):
        return 'w' in self.user_table[username]['perm']
    

    # --- FTP

class FTPHandler(asynchat.async_chat):
    """This class, implementing the FTP server Protocol-Interpreter (server-PI,
    see RFC 959), handle the FTP commands received from the client on the
    control channel, then call a method specific to the command type (for
    example, if "MKD pathname" command is received the "ftp_MKD" method with
    "pathname" argument will be called).  All of the relevant information is
    stored in instance variables of the handler.
    """

    # these are overridable defaults:

    authorizer = DummyAuthorizer()

    # messages
    msg_connect = "pyftpdlib %s" %__ver__
    msg_login = ""
    msg_quit = ""

    # maximum login attempts
    max_login_attempts = 3

    # FTP proxying feature (see RFC 959 describing such feature and RFC 2577
    # which describes security considerations implied)
    permit_ftp_proxying = False

    # Set to True if you want to permit PORTing over
    # privileged ports (not rencommended)
    permit_privileged_port = False


    def __init__(self, conn, ftpd_instance):
        asynchat.async_chat.__init__(self, conn=conn)
        self.ftpd_instance = ftpd_instance
        self.remote_ip, self.remote_port = self.socket.getpeername()
        self.in_buffer = []
        self.in_buffer_len = 0
        self.set_terminator("\r\n")

        # session attributes
        self.fs = AbstractedFS()
        self.in_dtp_queue = None
        self.out_dtp_queue = None
        self.authenticated = False
        self.username = "" 
        self.attempted_logins = 0
        self.current_type = 'a'
        self.restart_position = 0
        self.quit_pending = False

        # dtp attributes
        self.dtp_server = None
        self.data_channel = None  

    def __del__(self):
        debug("FTPHandler.__del__()")

    def handle(self):
        self.push('220-%s.\r\n' %self.msg_connect)
        self.respond("220 Ready.")

    def handle_max_cons(self):
        "Called when we're running out of maximum accepted connections limit"
        msg = "Too many connections. Service temporary unavailable."
        self.respond("421 %s" %msg)
        self.log(msg)
        # By using self.push, data could not be sent immediately in which case a
        # new "loop" will occur exposing us to the risk of accepting new
        # connections.  Since that this could cause asyncore to run out of fds
        # (...and exposing the server to DoS attacks), we immediatly close the
        # channel by using close() instead of close_when_done().
        # If data has not been sent yet client will be silently disconnected.
        #self.close_when_done()
        self.close()

    def handle_max_cons_per_ip(self):
        "Called when too many clients are connected with same IP"
        msg = "Too many connections from the same IP."
        self.respond("421 %s" %msg)
        self.log(msg)
        self.close_when_done()

    # --- asyncore / asynchat overridden methods

    def readable(self):
        # if there's a quit pending we stop reading data from socket
        return not self.quit_pending

    def collect_incoming_data(self, data):
        self.in_buffer.append(data)
        self.in_buffer_len += len(data)
        # FIX #3
        # flush buffer if it gets too long (possible DoS attacks)
        # RFC959 specifies that a 500 response could be given in such cases
        buflimit = 2048
        if self.in_buffer_len > buflimit:
            self.respond('500 Command too long.')
            self.log('Command received exceeded buffer limit of %s.' % (buflimit))
            self.in_buffer = []
            self.in_buffer_len = 0

    # commands accepted before authentication
    unauth_cmds = ('USER','PASS','HELP','STAT','QUIT','NOOP','SYST')

    # commands needing an argument
    arg_cmds = ('APPE','DELE','MDTM','MODE','MKD','PORT','REST','RETR','RMD',
                'RNFR','RNTO','SIZE','STOR','STRU','TYPE','USER','XMKD','XRMD')

    # commands needing no argument
    unarg_cmds = ('ABOR','CDUP','PASV','PWD','QUIT','REIN','SYST','XCUP','XPWD')

    def found_terminator(self):
        """Called when the incoming data stream matches the \r\n terminator
        """
        line = ''.join(self.in_buffer).strip()
        self.in_buffer = []
        self.in_buffer_len = 0

        cmd = line.split(' ')[0].upper()
        space = line.find(' ')
        if space != -1:
            arg = line[space + 1:]
        else:
            arg = ""

        if cmd != 'PASS':
            self.logline("<== %s" %line)
        else:
            self.logline("<== %s %s" %(line.split(' ')[0], '*' * 6))

        # let's check if user provided an argument for those commands needing one
        if not arg and cmd in self.arg_cmds:
            self.cmd_missing_arg()
            return

        # let's do the same for those commands requiring no argument.
        elif arg and cmd in self.unarg_cmds:
            self.cmd_needs_no_arg()
            return

        # provide a limited set of commands if user isn't authenticated yet
        if (not self.authenticated):
            if cmd in self.unauth_cmds:
                # FIX #21
                # we permit STAT during this phase but we don't want STAT to 
                # return a directory LISTing if the user is not authenticated
                # yet (this could happen if STAT is used with an argument)
                if (cmd == 'STAT') and arg:
                    self.respond("530 Log in with USER and PASS first.")
                else:
                    method = getattr(self, 'ftp_'+cmd, None)
                    method(arg) # callback
            elif cmd in proto_cmds:
                self.respond("530 Log in with USER and PASS first.")
            else:
                self.cmd_not_understood(line)

        # provide full command set
        elif (self.authenticated) and (cmd in proto_cmds):
            method = getattr(self, 'ftp_'+cmd, None)
            method(arg) # callback

        else:
            # TODO - add a detailed comment here
            # TODO - provisional
            # recognize those commands having "special semantics"
            if 'ABOR' in cmd:
                self.ftp_ABOR("")
            elif 'STAT' in cmd:
                self.ftp_STAT("")
            # unknown command
            else:
                self.cmd_not_understood(line)

    def handle_expt(self):
        # Called when there is out of band (OOB) data for the socket connection.
        # This could happen in case of such commands needing "special action"
        # (typically STAT and ABOR) in which case we append OOB data to incoming
        # buffer.

        self.debug("FTPHandler.handle_expt()")
        # TODO - XXX provisional
        try:
            data = self.socket.recv(1024, socket.MSG_OOB)
            self.in_buffer.append(data)
        except:
            self.log("Can't handle OOB data.")
            self.handle_close()

    def handle_error(self):
        self.debug("FTPHandler.handle_error()")
        f = StringIO.StringIO()
        traceback.print_exc(file=f)
        self.debug(f.getvalue())
        asynchat.async_chat.close(self)

    def handle_close(self):
        self.debug("FTPHandler.handle_close()")
        self.close()

    def close(self):
        self.debug("FTPHandler.close()")
       
        if self.dtp_server:
            self.dtp_server.close()
            del self.dtp_server
                
        if self.data_channel:
            self.data_channel.close()
            del self.data_channel

        del self.out_dtp_queue
        del self.in_dtp_queue

        # remove client IP address from ip map
        self.ftpd_instance.ip_map.remove(self.remote_ip)
        asynchat.async_chat.close(self)
        self.log("Disconnected.")


    # --- callbacks
    
    def on_dtp_connection(self):
        """Called every time data channel connects (does not matter
        if active or passive).  Here we check for data queues.
        If we got data to send we just push it into data channel.
        If we got data to receive we enable data channel for receiving it.
        """
        self.debug("FTPHandler.on_dtp_connection()")
        if self.dtp_server:
            self.dtp_server.close()
        self.dtp_server = None

        # check for data to send
        if self.out_dtp_queue:
            data, isproducer, log = self.out_dtp_queue
            if log:
                self.log(log)
            if not isproducer:
                self.data_channel.push(data)
            else:
                self.data_channel.push_with_producer(data)
            if self.data_channel:
                self.data_channel.close_when_done()
            self.out_dtp_queue = None

        # check for data to receive
        elif self.in_dtp_queue:
            fd, log = self.in_dtp_queue
            if log:
                self.log(log)
            self.data_channel.file_obj = fd
            self.data_channel.enable_receiving(self.current_type)
            self.in_dtp_queue = None
    
    def on_dtp_close(self):
        """Called every time close() method of DTPHandler() class
        is called.
        """
        self.debug("FTPHandler.on_dtp_close()")
        self.data_channel = None
        if self.quit_pending:
            self.close_when_done()
    
    # --- utility
    
    def respond(self, resp):
        "Send a response to client"
        self.push(resp + '\r\n')
        self.logline('==> %s' % resp)

    def push_dtp_data(self, data, isproducer=False, log=''):
        """Called every time a RETR, LIST or NLST is received, push data into
        data channel.  If data channel does not exists yet we queue up data
        to send later.  Data will then be pushed into data channel when
        "on_dtp_connection()" method will be called.

        @param data: data to push (it could be a string or a producer)
        @param isproducer: if True we assume that is a producer
        @param log: log message
        """
        if self.data_channel:
            self.respond("125 Data connection already open. Transfer starting.")
            if log:
                self.log(log)
            if not isproducer:
                self.data_channel.push(data)
            else:
                self.data_channel.push_with_producer(data)
            if self.data_channel:
                self.data_channel.close_when_done()
        else:
            self.respond("150 File status okay. About to open data connection.")
            self.out_dtp_queue = (data, isproducer, log)

    def cmd_not_understood(self, line):
        self.respond('500 Command "%s" not understood.' %line)

    def cmd_missing_arg(self):
        self.respond("501 Syntax error: command needs an argument.")
        
    def cmd_needs_no_arg(self):
        self.respond("501 Syntax error: command needs no argument.")
      
    def log(self, msg):
        log("[%s]@%s:%s %s" %(self.username, self.remote_ip, self.remote_port, msg))
    
    def logline(self, msg):
        logline("%s:%s %s" %(self.remote_ip, self.remote_port, msg))
    
    def debug(self, msg):
        debug(msg)


    # --- ftp

        # --- connection

    def ftp_PORT(self, line):
        "Start an active data-channel"
        # parse PORT request getting IP and PORT
        # TODO - add a comment describing how the algorithm used to get such
        # values works (reference http://cr.yp.to/ftp/retr.html).
        try:
            line = line.split(',')
            ip = ".".join(line[:4]).replace(',','.')
            port = (int(line[4]) * 256) + int(line[5])
        except (ValueError, OverflowError):
            self.respond("500 Invalid PORT format.")
            return

        # FTP bounce attacks protection: according to RFC 2577 it's
        # rencommended rejecting PORT if IP address specified in it
        # does not match client IP address.
        if not self.permit_ftp_proxying:
            if ip != self.remote_ip:
                self.log("PORT %s refused (bounce attack protection)" %port)
                self.respond("500 FTP proxying feature not allowed.")
                return

        # FIX #11
        # ...another RFC 2577 rencommendation is rejecting connections to
        # privileged ports (< 1024) for security reasons.  Moreover, binding to
        # such ports could require root priviledges on some systems.
        if not self.permit_privileged_port:
            if port < 1024:
                self.respond("500 Can't connect over a privileged port.")
                return

        # close existent DTP-server instance, if any.
        if self.dtp_server:
            self.dtp_server.close()
            self.dtp_server = None

        if self.data_channel:
            self.data_channel.close()
            self.data_channel = None

        # make sure we are not running out of maximum connections limit
        if self.ftpd_instance.max_cons:
            if self.ftpd_instance.max_cons >= len(self._map):
                msg = "Too many connections. Can't open data channel."
                self.respond("425 %s" %msg)
                self.log(msg)
                return

        # finally, let's open DTP channel
        ActiveDTP(ip, port, self)


    def ftp_PASV(self, line):
        "Start a passive data-channel"
        # close existent DTP-server instance, if any.
        if self.dtp_server:
            self.dtp_server.close()
            self.dtp_server = None

        if self.data_channel:
            self.data_channel.close()
            self.data_channel = None

        # make sure we are not running out of maximum connections limit
        if self.ftpd_instance.max_cons:
            if self.ftpd_instance.max_cons >= len(self._map):
                msg = "Too many connections. Can't open data channel."
                self.respond("425 %s" %msg)
                self.log(msg)
                return

        # let's open DTP channel
        self.dtp_server = PassiveDTP(self)


    def ftp_QUIT(self, line):
        "Quit current session"
        # From RFC 959:
        # This command terminates a USER and if file transfer is not
        # in progress, the server closes the control connection.
        # If file transfer is in progress, the connection will remain
        # open for result response and the server will then close it.
        if not self.msg_quit:
            self.respond("221 Goodbye.")
        else:
            self.push("221-%s\r\n" %self.msg_quit)
            self.respond("221 Goodbye.")

        if not self.data_channel:
            self.close_when_done()
        else:
            # Once we enable quit_pending cmd-channel will stop responding to
            # further commands.
            self.quit_pending = True


        # --- data transferring
        
    def ftp_LIST(self, line):
        "Return a list of files"
        if line:
            # some FTP clients (like Konqueror or Nautilus) erroneously use
            # /bin/ls-like LIST formats (e.g. "LIST -l", "LIST -al" and so on...).
            # If this happens we LIST the current working directory.
            if line.lower() in ("-a", "-l", "-al", "-la"):
                path = self.fs.translate(self.fs.cwd)
                line = self.fs.cwd
            else:
                path = self.fs.translate(line)
                line = self.fs.normalize(line)
        else:            
            path = self.fs.translate(self.fs.cwd)
            line = self.fs.cwd

        try:
            data = self.fs.get_list_dir(path)
        except OSError, err:
            self.log('FAIL LIST "%s". %s.' %(line, os.strerror(err.errno)))
            self.respond ('550 %s.' %os.strerror(err.errno))
            return

        self.push_dtp_data(data, log='OK LIST "%s". Transfer starting.' %line)


    def ftp_NLST(self, line):
        "Return a list of files in a compact form"
        if line:
            path = self.fs.translate(line)
            line = self.fs.normalize(line)
        else:            
            path = self.fs.translate(self.fs.cwd)
            line = self.fs.cwd

        try:
            data = self.fs.get_nlst_dir(path)
        except OSError, err:
            self.log('FAIL NLST "%s". %s.' %(line, os.strerror(err.errno)))
            self.respond ('550 %s.' %os.strerror(err.errno))
            return

        self.push_dtp_data(data, log='OK NLST "%s". Transfer starting.' %line)


    def ftp_RETR(self, line):
        "Retrieve a file"
        file = self.fs.translate(line)

        if not self.fs.isfile(file):
            self.log('FAIL RETR "%s". No such file.' %line)
            self.respond('550 No such file: "%s".' %line)
            return

        if not self.authorizer.r_perm(self.username, file):
            self.log('FAIL RETR "s". Not enough priviledges' %line)
            self.respond ("550 Can't RETR: not enough priviledges.")
            return

        try:
            fd = self.fs.open(file, 'rb')
        except IOError, err:
            self.log('FAIL RETR "%s". %s.' %(line, os.strerror(err.errno)))
            self.respond ('550 %s.' %os.strerror(err.errno))
            return

        # FIX #12
        if self.restart_position:
            # Make sure that the requested offset is valid (within the
            # size of the file being resumed).
            # According to RFC 1123 a 554 reply may result in case that the
            # existing file cannot be repositioned as specified in the REST.
            ok = 0
            try:
                assert not self.restart_position > self.fs.getsize(file)
                fd.seek(self.restart_position)
                ok = 1
            except AssertionError:
                msg = "Invalid REST parameter."
            except IOError, err:
                msg = os.strerror(err.errno)
            self.restart_position = 0
            if not ok:
                self.respond('554 %s' %msg)
                self.log('FAIL RETR "%s". %s.' %(line, msg))
                return

        producer = FileProducer(fd, self.current_type)
        self.push_dtp_data(producer, isproducer=1,
            log='OK RETR "%s". Download starting.' %self.fs.normalize(line))


    def ftp_STOR(self, line, mode='w'):
        "Store a file"
        # A resume could occur in case of APPE or REST commands.
        # In that case we have to open file object in different ways:
        # STOR: mode = 'w'
        # APPE: mode = 'a'
        # REST: mode = 'r+' (to permit seeking on file object)
        file = self.fs.translate(line)

        if not self.authorizer.w_perm(self.username, os.path.split(file)[0]):
            self.log('FAIL STOR "%s". Not enough priviledges.' %line)
            self.respond ("550 Can't STOR: not enough priviledges.")
            return

        if self.restart_position:
            mode = 'r+'

        try:            
            fd = self.fs.open(file, mode + 'b')
        except IOError, err:
            self.log('FAIL STOR "%s". %s.' %(line, os.strerror(err.errno)))
            self.respond ('550 %s.' %os.strerror(err.errno))
            return

        # FIX #12
        if self.restart_position:
            # Make sure that the requested offset is valid (within the
            # size of the file being resumed).
            # According to RFC 1123 a 554 reply may result in case that the
            # existing file cannot be repositioned as specified in the REST.
            ok = 0
            try:
                assert not self.restart_position > self.fs.getsize(file)
                fd.seek(self.restart_position)
                ok = 1
            except AssertionError:
                msg = "Invalid REST parameter."
            except IOError, err:
                msg = os.strerror(err.errno)
            self.restart_position = 0
            if not ok:
                self.respond('554 %s' %msg)
                self.log('FAIL STOR "%s". %s.' %(line, msg))
                return

        log = 'OK STOR "%s". Upload starting.' %self.fs.normalize(line)
        if self.data_channel:
            self.respond("125 Data connection already open. Transfer starting.")
            self.log(log)
            self.data_channel.file_obj = fd
            self.data_channel.enable_receiving(self.current_type)
        else:
            self.debug("info: new producer queue added.")
            self.respond("150 File status okay. About to open data connection.")
            self.in_dtp_queue = (fd, log)


    def ftp_STOU(self, line):
        "Store a file with a unique name"
        # - Note 1: RFC 959 prohibited STOU parameters, but this prohibition is
        # obsolete.

        # TODO - should we really accept arguments? RFC959 does not talk about such
        # eventuality but Bernstein does: http://cr.yp.to/ftp/stor.html
        # Try to find 'official' references declaring such obsolescence.
        
        # - Note 2: 250 response wanted by RFC 959 has been declared incorrect
        # into RFC 1123 that wants 125/150 instead.
        # - Note 3: RFC 1123 also provided an exact output format defined to be
        # as follow:
        # > 125 FILE: pppp
        # ...where pppp represents the unique pathname of the file that will be
        # written.

        # FIX #19
        # watch for STOU preceded by REST, which makes no sense.
        if self.restart_position:
            self.respond("550 Can't STOU when REST is pending.")
            return

        # create file with a suggested name
        if line:
            file = self.fs.translate(line)
            if not self.fs.exists(file):
                resp = line
            else:
                x = 0
                while 1:
                    file = self.fs.translate(line + '.' + str(x))
                    if not self.fs.exists(file):
                        resp = line + '.' + str(x)
                        break
                    else:
                        # FIX #25
                        # set a max of 99 on the number of tries to create a
                        # unique filename, so that we decrease the chances of
                        # a DoS situation
                        if x > 99:
                            self.respond("450 Can't STOU other files with such name.")
                            self.log("Can't STOU other files with such name.")
                            return
                        else:
                            x += 1

        # create file with a brand new name
        else:
            x = 0
            while 1:
                file = self.fs.translate(self.fs.cwd + '.' + str(x))
                if not self.fs.exists(file):
                    resp = '.' + str(x)
                    break
                else:
                    # FIX #25
                    # set a max of 99 on the number of tries to create a unique
                    # filename, so that we decrease the chances of a DoS situation
                    if x > 99:
                        self.respond("450 Can't STOU other files with brand new name.")
                        self.log("Can't STOU other files with brand new name.")
                        return
                    else:
                        x += 1

        # now just acts like STOR excepting that restarting isn't allowed
        if not self.authorizer.w_perm(self.username, os.path.split(file)[0]):
            self.log('FAIL STOU "%s". Not enough priviledges' %line)
            self.respond ("550 Can't STOU: not enough priviledges.")
            return
        
        try:
            fd = self.fs.open(file, 'wb')
        except IOError, err:
            self.log('FAIL STOU "%s". %s.' %(line, os.strerror(err.errno)))
            self.respond ('550 %s.' %os.strerror(err.errno))
            return

        # FIX #8
        log = 'OK STOU "%s". Upload starting.' %resp
        if self.data_channel:
            self.respond("125 FILE: %s" %resp)
            self.log(log)
            self.data_channel.file_obj = fd
            self.data_channel.enable_receiving(self.current_type)
        else:
            self.debug("info: new producer queue added.")
            self.respond("150 FILE: %s" %resp)
            self.in_dtp_queue = (fd, log)


    def ftp_APPE(self, line):
        "Append data to an existent file"
        # TODO - Should we watch for REST like we already did in STOU?
        self.ftp_STOR(line, mode='a')


    def ftp_REST(self, line):
        "Restart from marker"
        try:
            marker = int(line)
            if marker < 0:
                raise ValueError
            self.respond("350 Restarting at position %s. Now use RETR/STOR for resuming." %marker)
            self.restart_position = marker
        except (ValueError, OverflowError):
            self.respond("501 Invalid number of parameters.")


    def ftp_ABOR(self, line):
        "Abort data transfer"
        if self.dtp_server:
            self.dtp_server.close()
            self.dtp_server = None
            
        if self.data_channel:
            self.data_channel.close()
            self.data_channel = None
        # TODO - implement FIX #18
        self.log("ABOR received.")
        self.respond('226 ABOR command successful.')


        # --- authentication

    def ftp_USER(self, line):
        "Set username"
        # TODO - see bug #7 (Change account if USER is received twice)
        # we always treat anonymous user as lower-case string.
        if line.lower() == "anonymous":
            self.username = "anonymous"
        else:
            self.username = line
        self.respond('331 Username ok, send password.')

    def ftp_PASS(self, line):
        "Check username's password"

        #FIX #23 (PASS should be rejected if user is already authenticated)
        # http://code.google.com/p/pyftpdlib/issues/detail?id=23
        if self.authenticated:
            self.respond("503 User already authenticated.")
            return

        if not self.username:
            self.respond("503 Login with USER first.")
            return

        if self.username == 'anonymous':
            line = ''

        # username ok
        if self.authorizer.has_user(self.username):

            if self.authorizer.validate_authentication(self.username, line):
                if not self.msg_login:
                    self.respond("230 User %s logged in." %self.username)
                else:
                    self.push("230-%s\r\n" %self.msg_login)
                    self.respond("230 Welcome.")

                self.authenticated = True
                self.attempted_logins = 0
                self.fs.root = self.authorizer.get_home_dir(self.username)
                self.log("User %s logged in." %self.username)

            else:              
                self.attempted_logins += 1
                if self.attempted_logins >= self.max_login_attempts:
                    self.log("Maximum login attempts. Disconnecting.")
                    self.respond("530 Maximum login attempts. Disconnecting.")
                    self.close()                   
                else:                    
                    self.respond("530 Authentication failed.")
                    self.username = ""

        # wrong username
        else:
            # FIX #20
            self.attempted_logins += 1
            if self.attempted_logins >= self.max_login_attempts:
                self.log("Maximum login attempts. Disconnecting.")
                self.respond("530 Maximum login attempts. Disconnecting.")
                self.close()               
            elif self.username.lower() == 'anonymous':
                self.respond("530 Anonymous access not allowed.")
                self.log('Authentication failed: anonymous access not allowed.')
            else:
                self.respond("530 Authentication failed.")
                self.log('Authentication failed: unknown username "%s".' %self.username)
                self.username = ""


    def ftp_REIN(self, line):
        "Reinitialize user"
        # TODO:

        # From RFC 959:
        # > REIN command terminates a USER, flushing all I/O and account
        # > information, except to allow any transfer in progress to be
        # > completed.  All parameters are reset to the default settings
        # > and the control connection is left open.  This is identical
        # > to the state in which a user finds himself immediately after
        # > the control connection is opened.

        # This command appears nonsense to me and RFC959 really lacks of details!
        # What exactly should I have to do if I receive REIN while a transfer
        # is in progress?
        # - Immediately respond with 331, reset account information and do not
        #   accept further commands until trasfer is finished.
        # - Do not accept further commands until data-trasfer is completed,
        #   then REINinizialite the session responding with 331.
        # - Respond with 311, flush account information, do not accept further
        #   commands and respond with 311 again when the transfer is finished.
        # - Other. (wtf!)
        # Moreover I'm wondering a question: if user "james" starts a transfer
        # and in the meanwhile he log-in again as "charles" by using REIN -> USER
        # -> PASS he could be able to abort the transfer that still belongs to
        # "james" by using PASV, PORT or ABOR.
        # imho, a new user shouldn't have control over a transfer belonging
        # to an older REINed one, but RFC959 just don't care about it!
        # Note that the same problem occurs when an authenticated client use USER.
        # Having said that I decided to accept REIN only if no data transfer is
        # actually in progress.

        if self.data_channel:
            if not self.data_channel.get_transmitted_bytes():
                self.data_channel.close()
                self.data_channel = None
            else:
                pass
        if self.dtp_server:
            self.dtp_server.close()
            self.dtp_server = None

        self.authenticated = False
        self.username = ""
        self.attempted_logins = 0
        self.current_type = 'a'
        self.restart_position = 0
        self.quit_pending = False
        self.in_dtp_queue = None
        self.out_dtp_queue = None
        self.respond("230 Ready for new user.")
        self.log("REIN account informations was flushed.")
##        def do_rein():
##            if self.dtp_server:
##                self.dtp_server.close()
##                self.dtp_server = None
##                
##            if self.data_channel:
##                self.data_channel.close()
##                self.data_channel = None
##
##            self.authenticated = False
##            self.username = ""
##            self.attempted_logins = 0
##            self.current_type = 'a'
##            self.restart_position = 0
##            self.quit_pending = False
##            self.in_dtp_queue = None
##            self.out_dtp_queue = None
##            self.respond("230 Ready for new user.")
##            self.log("REIN account informations was flushed.")
##
##        if not self.data_channel:
##            do_rein()
##        else:
##            # Let's check if a transfer is in progress or not.
##            # If it is we'll REIN the client after the transfer is
##            # finished.
##            if self.data_channel.get_transmitted_bytes():
##                # What should I have to do here? Do I have to respond
##                # with something or not? RFC 959 really lacks of
##                # specifications!
##                self.rein_pending = True
##            else:
##                do_rein()


        # --- filesystem operations

    def ftp_PWD(self, line):
        "Get current working directory"
        self.respond('257 "%s" is the current directory.' %self.fs.cwd)

    def ftp_CWD(self, line):
        "Change current working directory"
        # TODO: a lot of FTP servers go back to root directory if no arg is
        # provided but this is not specified into RFC959. Search for
        # official references about this behaviour.
        if not line:
            line = '/'

        # When CWD is received we temporarily join the specified directory
        # to see if we have permissions to do it.
        # A more elegant way to do that would be using os.access instead but I'm
        # not sure about its reliability on non-posix platforms (see, for
        # example, Python bug #1513646) or when specified paths are network
        # filesystems.
        ftp_path = self.fs.normalize(line)
        real_path = self.fs.translate(line)
        old_dir = os.getcwd()
        done = 0
        try:
            self.fs.chdir(real_path)
            self.fs.cwd = ftp_path
            done = 1
        except OSError, err:
            self.log('FAIL CWD "%s". %s.' \
                %(self.fs.normalize(line), os.strerror(err.errno)))
            self.respond ('550 %s.' %os.strerror(err.errno))
        if done:
            self.log('OK CWD "%s"' %self.fs.cwd)
            self.respond('250 "%s" is the current directory.' %self.fs.cwd)
            # let's use os.chdir instead of self.fs.chdir: we don't want to
            # go back to the original directory by using user's permissions.
            os.chdir(old_dir)


    def ftp_CDUP(self, line):
        "Go to parent directory"
        # Note: RFC 959 says that code 200 is required but it also says that
        # CDUP uses the same codes as CWD.
        # FIX #14
        self.ftp_CWD('..')


    def ftp_SIZE(self, line):
        """Return size of file in a format suitable for using with RESTart as
        defined into RFC 3659.

        Implementation note:
        properly handling the SIZE command when TYPE ASCII is used would require
        to scan the entire file to perform the ASCII translation logic
        (file.read(int).replace(os.linesp, '\r\n')) and then calculating the len
        of such data which may be different than the actual size of the file on
        the server.  Considering that the calculating such result could be very
        resource-intensive it could be easy for a malicious client to try a DoS
        attack, thus we do not perform the ASCII translation.

        However, clients in general should not be resuming downloads in ASCII
        mode.  Resuming downloads in binary mode is the recommended way as
        specified into RFC 3659.
	    """
        path = self.fs.translate(line)
        # FIX #17
        if self.fs.isdir(path):
	        self.respond ("550 Could not get a directory size.")
	        return
        try:
            size = self.fs.getsize(path)
            self.respond("213 %s" %size)
        except OSError, err:
            self.respond ('550 %s.' %os.strerror(err.errno))


    def ftp_MDTM(self, line):
        """Return last modification time of file as an ISO 3307 style time
        (YYYYMMDDHHMMSS) as defined into RFC 3659.
        """
        path = self.fs.translate(line)
        if not self.fs.isfile(path):
            self.respond("550 No such file.")
            return
        try:
            lmt = self.fs.getmtime(path)
            lmt = time.strftime("%Y%m%d%H%M%S", time.localtime(lmt))
            self.respond("213 %s" %lmt)
        except OSError, err:
            self.respond ('550 %s.' %os.strerror(err.errno))


    def ftp_MKD(self, line):
        "Create directory"
        path = self.fs.translate(line)

        if not self.authorizer.w_perm(self.username, os.path.split(path)[0]):
            self.log('FAIL MKD "%s". Not enough priviledges.' %line)
            self.respond ("550 Can't MKD: not enough priviledges.")
            return

        try:
            self.fs.mkdir(path)
            self.log('OK MKD "%s".' %self.fs.normalize(line))
            self.respond("257 Directory created.")
        except OSError, err:
            self.log('FAIL MKD "%s". %s.' %(line, os.strerror(err.errno)))
            self.respond ('550 %s.' %os.strerror(err.errno))


    def ftp_RMD(self, line):
        "Remove directory"
        if not line:
            self.cmd_missing_arg()
            return

        path = self.fs.translate(line)

        if path == self.fs.root:
            self.respond("550 Can't remove root directory.")
            return
                    
        if not self.authorizer.w_perm(self.username, path):
            self.log('FAIL RMD "%s". Not enough priviledges.' %line)
            self.respond ("550 Can't RMD: not enough priviledges.")
            return

        try:
            self.fs.rmdir(path)
            self.log('OK RMD "%s".' %self.fs.normalize(line))
            self.respond("250 Directory removed.")
        except OSError, err:
            self.log('FAIL RMD "%s". %s.' %(line, os.strerror(err.errno)))
            self.respond ('550 %s.' %os.strerror(err.errno))


    def ftp_DELE(self, line):
        "Delete file"
        path = self.fs.translate(line)
            
        if not self.authorizer.w_perm(self.username, path):
            self.log('FAIL DELE "%s". Not enough priviledges.' % self.fs.normalize(line))
            self.respond ("550 Can't DELE: not enough priviledges.")
            return

        try:
            self.fs.remove(path)
            self.log('OK DELE "%s".' %self.fs.normalize(line))
            self.respond("250 File removed.")
        except OSError, err:
            self.log('FAIL DELE "%s". %s.' %(line, os.strerror(err.errno)))
            self.respond ('550 %s.' %os.strerror(err.errno))


    def ftp_RNFR(self, line):
        "File renaming (source name)"
        path = self.fs.translate(line)
        if self.fs.exists(path):
            self.fs.rnfr = line
            self.respond("350 Ready for destination name")
        else:
            self.respond("550 No such file or directory.")


    def ftp_RNTO(self, line):
        "File renaming (destination name)"
        if not self.fs.rnfr:
            self.respond("503 Bad sequence of commands: use RNFR first.")
            return

        src = self.fs.translate(self.fs.rnfr)
        dst = self.fs.translate(line)
       
        if not self.authorizer.w_perm(self.username, self.fs.rnfr):
            self.log('FAIL RNFR/RNTO "%s ==> %s". Not enough priviledges for renaming.'
                     %(self.fs.rnfr, self.fs.normalize(line)))
            self.respond ("550 Can't RNTO: not enough priviledges.")
            self.fs.rnfr = None
            return

        try:
            self.fs.rename(src, dst)
            self.log('OK RNFR/RNTO "%s ==> %s".' %(self.fs.rnfr, self.fs.normalize(line)))
            self.respond("250 Renaming ok.")
        except OSError, err:
            self.log('FAIL RNTO "%s". %s.' %(line, os.strerror(err.errno)))
            self.respond ('550 %s.' %os.strerror(err.errno))
            self.fs.rnfr = None


        # --- others       

    def ftp_TYPE(self, line):
        "Set current type"
        line = line.upper()
        # FIX #6
        if line in ("A", "AN", "A N"):
            self.respond("200 Type set to: ASCII.")
            self.current_type = 'a'
        elif line in ("I", "L8", "L 8"):
            self.respond("200 Type set to: Binary.")
            self.current_type = 'i'
        else:
            self.respond('504 Unsupported type "%s".' %line)


    def ftp_STRU(self, line):
        "Set file structure (obsolete)"
        # obsolete (backward compatibility with older ftp clients)
        if line in ('f','F'):            
            self.respond ('200 File transfer structure set to: F.')
        else:
            self.respond ('504 Unimplemented STRU type.')


    def ftp_MODE(self, line):
        "Set data transfer mode (obsolete)"
        # obsolete (backward compatibility with older ftp clients)
        if line in ('s', 'S'):
            self.respond('200 Trasfer mode set to: S')
        else:
            self.respond('504 Unimplemented MODE type.')


    def ftp_STAT(self, line):
        """Return statistics about ftpd.  If argument is provided return
        directory listing over command channel.
        """
        # return STATus information about ftpd
        if not line:
            s = []
            s.append('211-%s %s status:\r\n' %(__pname__, __ver__))
            s.append('\tConnected to: %s:%s\r\n' %self.socket.getsockname())
            if self.authenticated:
                s.append('\tLogged in as: %s\r\n' %self.username)
            else:
                if not self.username:
                    s.append("\tWaiting for username\r\n")
                else:
                    s.append("\tWaiting for password\r\n")
            if self.current_type == 'a':
                type = 'ASCII'
            else:
                type = 'Binary'
            s.append("\tTYPE: %s; STRUcture: File; MODE: Stream\r\n" %type)
            if self.data_channel:
                s.append('\tData connection open:\r\n')
                s.append('\tTotal bytes sent: %s' %self.data_channel.tot_bytes_sent)
                s.append('\tTotal bytes received: %s' %self.data_channel.tot_bytes_received)
            else:
                s.append('\tData connection closed\r\n')
            self.push(''.join(s))
            self.respond("211 End of status.")

        else:
            
            # TODO - see also FIX #15
            # if arg is provided we should return directory LISTing over
            # the command channel. 
            # Note: we also must support globbing (*, [], ?, and so on....)
            # Still have to find a way to do that since that:
            # - user could send a 'normal' path (e.g. "dir", "/dir") in which
            #   case we should use os.listdir
            # - user could send a Unix style pathname pattern expansion
            #   (e.g. "*.txt", "/dir/*.txt") in which case we should use glob
            #   module but it could return absolute or relative listing depending
            #   on the input... :-\
            pass
##            pathname = self.fs.normalize(line)
##            if not glob.has_magic(pathname):
##                listing = self.fs.get_list_dir(pathname)
##            else:
##                dirname, basename = os.path.split(pathname)
##                if not dirname:
##                    listing = glob.glob1(self.fs.cwd, basename)
##                else:
##                    listing = glob.glob1(dirname, basename)


    def ftp_NOOP(self, line):
        "Do nothing"
        self.respond("250 I succesfully done nothin'.")


    def ftp_SYST(self, line):
        "Return system type"
        # This command is used to find out the type of operating system at the
        # server.  The reply shall have as its first word one of the system
        # names listed in RFC 943.
        # Since that we always return a "/bin/ls -lgA"-like output on LIST we
        # prefer to respond as if we would on Unix in any case.
        self.respond("215 UNIX Type: L8")


    def ftp_ALLO(self, line):
        "Allocate bytes (obsolete)"
        # obsolete (always respond with 202)
        self.respond("202 No storage allocation necessary.")


    def ftp_HELP(self, line):
        "Return help"
        # TODO - A lot of FTP servers return command names only while we
        # return cmd_name + description. I believe we should return the same.
        if line:
            # FIX #10
            if line.upper() in proto_cmds:
                self.respond("214 %s.\r\n" %proto_cmds[line.upper()])
            else:
                self.respond("500 Unrecognized command.")
        else:
            self.push("214-The following commands are recognized " + \
                    "(* == argument required):\r\n" + \
                    helper_string)
            self.respond("214 Help command succesful.")


        # --- support for deprecated cmds
    # RFC 1123 requires that the server treat XCUP, XCWD, XMKD, XPWD and
    # XRMD commands as synonyms for CDUP, CWD, MKD, LIST and RMD.
    # Such commands are obsoleted but some ftp clients (e.g. Windows ftp.exe)
    # still use them.

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


class FTPServer(asyncore.dispatcher):
    """This class is an asyncore.disptacher subclass.
    It creates a FTP socket listening on <address>, dispatching the requests
    to a <handler> (typically FTPHandler class).
    """
    # Overiddable defaults (overriding is strongly rencommended to avoid
    # running out of file descritors (DoS) !).

    # number of maximum simultaneous connections accepted
    # (0 == unlimited)
    max_cons = 0

    # number of maximum connections accepted for the same IP address
    # (0 == unlimited)
    max_cons_per_ip = 0

    def __init__(self, address, handler):
        asyncore.dispatcher.__init__(self)
        self.address = address
        self.handler = handler
        self.ip_map = []
        self.create_socket(socket.AF_INET, socket.SOCK_STREAM)
        if os.name == 'posix':
            # FIX #4
            self.set_reuse_addr()  
        self.bind(self.address)
        self.listen(5)

    def __del__(self):
        debug("FTPServer.__del__()")
        
    def serve_forever(self):
        """A wrap around asyncore.loop().
        Starts the asyncore polling loop by calling asyncore.loop() function;
        """
        log("Serving FTP on %s:%s" %self.socket.getsockname())
        try:
            # FIX #16
            # by default we try to use poll(), if it is available,
            # else we'll use select()
            asyncore.loop(timeout=1, use_poll=hasattr(asyncore.select, 'poll'))
        except (KeyboardInterrupt, SystemExit, asyncore.ExitNow):
            log("Shutting down FTPd.")
            # FIX #22
            self.close_all()

    def handle_accept(self):
        debug("handle_accept()")
        sock_obj, addr = self.accept()
        log("[]%s:%s connected." %addr)

        handler = self.handler(sock_obj, self)
        ip = addr[0]
        self.ip_map.append(ip)

        # FIX #5
        # For performance and security reasons we should always set a limit for
        # the number of file descriptors that socket_map should contain.
        # When we're running out of such limit we'll use the last available
        # channel for sending a 421 response to the client before disconnecting
        # it.
        if self.max_cons:
            if len(self._map) > self.max_cons:
                handler.handle_max_cons()
                return

        # accept only a limited number of connections from the same
        # source address.
        if self.max_cons_per_ip:
            if self.ip_map.count(ip) > self.max_cons_per_ip:
                handler.handle_max_cons_per_ip()
                return

        handler.handle()

    def writable(self):
        return 0

    def handle_error(self):        
        debug("FTPServer.handle_error()")
        f = StringIO.StringIO()
        traceback.print_exc(file=f)
        debug(f.getvalue())
        self.close()

    def close_all(self, map=None, ignore_all=False):
        """'clean' shutdown: instead of using the current asyncore.close_all()
        function which only close sockets, we iterates over all existent
        channels calling close() method for each one of them, avoiding memory
        leaks.  This is how close_all function will appear in the fixed version
        of asyncore that will be included into Python 2.6.
        """
        if map is None:
            map = self._map
        for x in map.values():
            try:
                x.close()
            except OSError, x:
                if x[0] == errno.EBADF:
                    pass
                elif not ignore_all:
                    raise
            except (asyncore.ExitNow, KeyboardInterrupt, SystemExit):
                raise
            except:
                if not ignore_all:
                    raise
        map.clear()


class PassiveDTP(asyncore.dispatcher):
    """This class is an asyncore.disptacher subclass.
    It creates a socket listening on a local port, dispatching the resultant
    connection DTPHandler.
    """

    # TODO - provide the possibility to define a certain range of ports
    # on which DTP should bind on

    def __init__(self, cmd_channel):           
        asyncore.dispatcher.__init__(self)
        self.cmd_channel = cmd_channel

        ip = self.cmd_channel.getsockname()[0]
        self.create_socket(socket.AF_INET, socket.SOCK_STREAM)
        # by using 0 as port number value we let socket choose a free
        # unprivileged random port.  This is also convenient on some systems
        # where root is the only user able to bind a socket on such ports.
        self.bind((ip, 0))
        self.listen(5)        
        port = self.socket.getsockname()[1]
        # The format of 227 response in not standardized.
        # This is the most expected:
        self.cmd_channel.respond('227 Entering passive mode (%s,%d,%d).' %(
                ip.replace('.', ','), port / 256, port % 256))

    def __del__(self):
        debug("PassiveDTP.__del__()")

   
    # --- connection / overridden
    
    def handle_accept(self):        
        sock_obj, addr = self.accept()
        
        # PASV connection theft protection: check the origin of data connection.
        # We have to drop the incoming data connection if remote IP address 
        # does not match the client's IP address.
        if self.cmd_channel.remote_ip != addr[0]:
            self.cmd_chanel.log("PASV connection theft attempt occurred from %s:%s."
                %(addr[0], addr[1]))
            try:
                #sock_obj.send('500 Go hack someone else, dude.\r\n')
                sock_obj.close()
            except socket.error:
                pass        
        else:
            debug("PassiveDTP.handle_accept()")
            # Immediately close the current channel (we accept only one
            # connection at time) to avoid running out of max connections limit.
            self.close()
            # delegate such connection to DTP handler
            handler = DTPHandler(sock_obj, self.cmd_channel)
            self.cmd_channel.data_channel = handler
            self.cmd_channel.on_dtp_connection()

    def writable(self):
        return 0

    def handle_error(self):
        debug("PassiveDTP.handle_error()")
        f = StringIO.StringIO()
        traceback.print_exc(file=f)
        debug(f.getvalue())
        self.close()
            
    def handle_close(self):
        debug("PassiveDTP.handle_close()")
        self.close()

    def close(self):
        debug("PassiveDTP.close()")
        asyncore.dispatcher.close(self)


class ActiveDTP(asyncore.dispatcher):
    """This class is an asyncore.disptacher subclass.
    It creates a socket resulting from the connection to a remote user-port,
    dispatching it to DTPHandler.
    """

    def __init__(self, ip, port, cmd_channel):
        asyncore.dispatcher.__init__(self)
        self.cmd_channel = cmd_channel       
        self.create_socket(socket.AF_INET, socket.SOCK_STREAM)
        try:
            self.connect((ip, port))
        except socket.error:
            self.cmd_channel.respond("500 Can't connect to %s:%s." %(ip, port))
            self.close()     

    def __del__(self):
        debug("ActiveDTP.__del__()")


    # --- connection / overridden

    def handle_write(self):
        # without overriding this we would get an "unhandled write event"
        # message from asyncore once connection occurs.
        pass

    def handle_connect(self):        
        debug("ActiveDTP.handle_connect()")
        self.cmd_channel.respond('200 PORT command successful.')
        # delegate such connection to DTP handler
        handler = DTPHandler(self.socket, self.cmd_channel)
        self.cmd_channel.data_channel = handler
        self.cmd_channel.on_dtp_connection()
        # self.close() --> (done automatically)

    def handle_error(self):
        debug("ActiveDTP.handle_error()")
        f = StringIO.StringIO()
        traceback.print_exc(file=f)
        debug(f.getvalue())
        self.close()
            
    def handle_close(self):
        debug("ActiveDTP.handle_close()")
        self.close()

    def close(self):
        debug("ActiveDTP.close()")
        asyncore.dispatcher.close(self)


# TODO - improve this comment
# DTPHandler implementation note
# When a producer is consumed and "close_when_done" has been previously
# used, "refill_buffer" erroneously calls "close" instead of "handle_cose"
# method (see also: http://python.org/sf/1740572)
# Having said that I decided to rewrite the entire class from scratch
# subclassing asyncore.dispatcher. This brand new implementation follows the
# same approach that asynchat module will use in Python 2.6.
# The most important change in such implementation is related to producer_fifo
# that will be a pure deque object instead of a "producer_fifo" instance.
# Since we don't want to break backward compatibily with older python versions
# (deque has been introduced in Python 2.4) if deque is not available we'll use
# a list instead.
# Event if this could seems somewhat tricky it's always better than having
# something buggy under the hoods...

try:
    from collections import deque
except ImportError:
    # backward compatibility with Python < 2.4.x
    class deque(list):
        def appendleft(self, obj):
            list.insert(self, 0, obj)


class DTPHandler(asyncore.dispatcher):
    # TODO - improve this docstring
    """Class handling server-data-transfer-process (server-DTP, see RFC 959)
    managing data-transfer operations.
    """

    ac_in_buffer_size = 8192
    ac_out_buffer_size  = 8192

    def __init__(self, sock_obj, cmd_channel):        
        asyncore.dispatcher.__init__(self, sock_obj)
        # we toss the use of the asynchat's "simple producer" and replace it with
        # a pure deque, which the original fifo was a wrapping of
        self.producer_fifo = deque()

        self.cmd_channel = cmd_channel
        self.file_obj = None
        self.receive = False
        self.transfer_finished = False
        self.tot_bytes_sent = 0
        self.tot_bytes_received = 0        

    def __del__(self):
        debug("DTPHandler.__del__()")

    # --- utility methods
    
    def enable_receiving(self, type):
        """Enable receiving data over the channel.
        Depending on the TYPE currently in use it creates an appropriate
        wrapper for the incoming data.
        """
        if type == 'a':
            self.data_wrapper = lambda x: x.replace('\r\n', os.linesep)
        else:
            self.data_wrapper = lambda x: x
        self.receive = True

    def get_transmitted_bytes(self):
        "Return the number of transmitted bytes"
        return self.tot_bytes_sent + self.tot_bytes_received

    def transfer_in_progress(self):
        "Return True if a transfer is in progress, else False"
        return self.get_transmitted_bytes != 0

    # --- connection

    def handle_read (self):
        try:
            chunk = self.recv(self.ac_in_buffer_size)
        except socket.error:
            self.handle_error()
            return
        self.tot_bytes_received += len(chunk)
        if not chunk:
            self.transfer_finished = True
            # self.close()  <-- asyncore.recv() already do that...
            return

        # Writing on file:
        # while we're writing on the file an exception could occur in case that
        # filesystem gets full but this rarely happens and a "try/except"
        # statement seems wasted to me.
        # Anyway if this happens we let handle_error() method handle this exception.
        # Remote client will just receive a generic 426 response then it will be
        # disconnected.
        self.file_obj.write(self.data_wrapper(chunk))

    def handle_write(self):
        self.initiate_send()

    def push(self, data):
        sabs = self.ac_out_buffer_size
        if len(data) > sabs:
            for i in xrange(0, len(data), sabs):
                self.producer_fifo.append(data[i:i+sabs])
        else:
            self.producer_fifo.append(data)
        self.initiate_send()

    def push_with_producer(self, producer):
        self.producer_fifo.append(producer)
        self.initiate_send()

    def readable(self):
        "Predicate for inclusion in the readable for select()"
        # cannot use the old predicate, it violates the claim of the
        # set_terminator method.
        #return (len(self.ac_in_buffer) <= self.ac_in_buffer_size)
        return self.receive

    def writable(self):
        "Predicate for inclusion in the writable for select()"
        return self.producer_fifo or (not self.connected)

    def close_when_done(self):
        "Automatically close this channel once the outgoing queue is empty"
        self.producer_fifo.append(None)

    def initiate_send (self):
        while self.producer_fifo and self.connected:
            first = self.producer_fifo[0]
            # handle empty string/buffer or None entry
            if not first:
                del self.producer_fifo[0]
                if first is None:
                    self.transfer_finished = True
                    self.handle_close()
                    return

            # handle classic producer behavior
            try:
                buffer(first)
            except TypeError:
                self.producer_fifo.appendleft(first.more())
                continue

            # send the data
            try:
                num_sent = self.send(first)
                self.tot_bytes_sent += num_sent
            except socket.error, why:
                self.handle_error()
                return

            if num_sent:
                if num_sent < len(first):
                    self.producer_fifo[0] = first[num_sent:]
                else:
                    del self.producer_fifo[0]

            # we tried to send some actual data
            return

    def handle_expt(self):
        debug("DTPHandler.handle_expt()")
        self.handle_close()

    def handle_error(self):        
        debug("DTPHandler.handle_error()")
        f = StringIO.StringIO()
        traceback.print_exc(file=f)
        debug(f.getvalue())
        self.handle_close()

    def handle_close(self):
        debug("DTPHandler.handle_close()")
        tot_bytes = self.get_transmitted_bytes()

        # If we used channel for receiving we assume that transfer is finished
        # when client close connection , if we used channel for sending we have
        # to check that all data has been sent (responding with 226) or not
        # (responding with 426).
        if self.receive:
            self.transfer_finished = True
        if self.transfer_finished:
            self.cmd_channel.respond("226 Transfer complete.")
            self.cmd_channel.log("Trasfer complete. %d bytes transmitted." %tot_bytes)
        else:
            self.cmd_channel.respond("426 Connection closed, transfer aborted.")
            self.cmd_channel.log("Trasfer aborted. %d bytes transmitted." %tot_bytes)
        self.close()

    def close(self):
        debug("DTPHandler.close()")

        if self.file_obj:
            if not self.file_obj.closed:
                self.file_obj.close()

        while self.producer_fifo:
            first = self.producer_fifo.pop()
            if isinstance(first, FileProducer):
                first.close()

        asyncore.dispatcher.close(self)
        self.cmd_channel.on_dtp_close()



# --- file producer

# I get it from Sam Rushing's Medusa-framework.
# It's like asynchat.simple_producer class excepting that it works
# with file(-like) objects instead of strings.

class FileProducer:
    "Producer wrapper for file[-like] objects."

    out_buffer_size = 65536

    def __init__ (self, file, type):
        self.done = 0
        self.file = file
        if type == 'a':
            self.data_wrapper = lambda x: x.replace(os.linesep, '\r\n')
        else:
            self.data_wrapper = lambda x: x

    def more(self):
        if self.done:
            return ''
        else:
            data = self.data_wrapper(
                self.file.read(self.out_buffer_size))
            if not data:
                self.done = 1
                self.close()
            else:
                return data

    def close(self):
        if not self.file.closed:
            self.file.close()


# --- filesystem


class AbstractedFS:
    "A wrap around all filesystem operations"

    def __init__(self):
        self.root = None
        self.cwd = '/'
        self.rnfr = None

    # --- Conversion utilities

    # FIX #9
    def normalize(self, path):
        """Translate a "virtual" FTP path into an absolute "virtual" FTP path.
        @param path: absolute or relative virtual path
        @return: absolute virtual path
        note: directory separators are system independent ("/")
        """

        # absolute path
        if os.path.isabs(path):
            p = os.path.normpath(path)
        # relative path
        else:
            p = os.path.normpath(os.path.join(self.cwd, path))

        # normalize string in a standard web-path notation having '/' as separator.
        p = p.replace("\\", "/")

        # os.path.normpath supports UNC paths (e.g. "//a/b/c") but we don't need
        # them.  In case we get an UNC path we collapse redundant separators
        # appearing at the beginning of the string
        while p[:2] == '//':
            p = p[1:]

        # Anti path traversal: don't trust user input nor programmer
        # only in case of, for some particular reason, self.cwd is not
        # absolute.  This is for extra protection, maybe not really necessary.
        if not os.path.isabs(p):
            p = "/"
        return p

    # FIX #9
    def translate(self, path):
        """Translate a 'virtual' FTP path into equivalent filesystem path.
        @param path: absolute or relative virtual path.
        @return: full absolute filesystem path.
        note: directory separators are system dependent.
        """
        # as far as i know, it should always be path traversal safe...
        return os.path.normpath(self.root + self.normalize(path))

    # --- Wrapper methods around os.*

    def open(self, filename, mode):
        return open(filename, mode)

    def exists(self, path):
        return os.path.exists(path)
        
    def isfile(self, path):
        return os.path.isfile(path)

    def isdir(self, path):
        return os.path.isdir(path)

    def chdir(self, path):
        os.chdir(path)

    # never used
    def cdup(self):
        parent = os.path.split(self.cwd)[0]
        self.cwd = parent
        
    def mkdir(self, path):
        os.mkdir(path)

    def rmdir(self, path):
        os.rmdir(path)
            
    def remove(self, path):
        os.remove(path)
    
    def getsize(self, path):
        return os.path.getsize(path)

    def getmtime(self, path):
        return os.path.getmtime(path)
           
    def rename(self, src, dst):
        os.rename(src, dst)

    def get_nlst_dir(self, path):
        """Return a directory listing in a compact form.

        Note that this is resource-intensive blocking operation so you may want
        to override it and move it into another process/thread in some way.
        """
        l = []
        listing = os.listdir(path)
        for elem in listing:
            l.append(elem + '\r\n')
        return ''.join(l)

    def get_list_dir(self, path):
        """Return a directory listing emulating "/bin/ls -lgA" UNIX command
        output.

        For portability reasons permissions, hard links numbers, owners and
        groups listed are static and unreliable but it shouldn't represent a
        problem for most ftp clients around.
        If you want reliable values on unix systems override this method and
        use other attributes provided by os.stat().
        This is how LIST appears to client:

        -rwxrwxrwx   1 owner    group         7045120 Sep 02  3:47 music.mp3
        drwxrwxrwx   1 owner    group               0 Aug 31 18:50 e-books
        -rwxrwxrwx   1 owner    group             380 Sep 02  3:40 module.py

        Note that this a resource-intensive blocking operation so you may want
        to override it and move it into another process/thread in some way.
        """
        # if path is a file we return information about it
        if os.path.isfile(path):
            root, filename = os.path.split(path)
            path = root
            listing = [filename]
        else:
            listing = os.listdir(path)

        l = []
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
                l.append("-rw-rw-rw-   1 owner    group %15s %s %s\r\n" %(
                    stat.st_size,
                    mtime,
                    obj))
            else:
                l.append("drwxrwxrwx   1 owner    group %15s %s %s\r\n" %(
                    '0', # no size
                    mtime,
                    obj))
        return ''.join(l)


def test():
    # cmd line usage (provide a read-only anonymous ftp server):
    # python -m pyftpdlib.FTPServer
    authorizer = DummyAuthorizer()
    authorizer.add_anonymous(os.getcwd())

    # TODO - Delete me (used for doing tests)
    authorizer.add_user('user', '12345', os.getcwd(), ('r','w'))
    # TODO - /Delete me (used for doing tests)

    FTPHandler.authorizer = authorizer
    address = ('', 21)
    ftpd = FTPServer(address, FTPHandler)
    ftpd.serve_forever()

# TODO - Delete me (used for doing tests)
import gc
gc.set_debug(gc.DEBUG_LEAK)
# TODO - /Delete me (used for doing tests)

if __name__ == '__main__':
    test()

