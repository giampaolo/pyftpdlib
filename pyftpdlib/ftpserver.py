#!/usr/bin/env python
# $Id$
#
#  pyftpdlib is released under the MIT license, reproduced below:
#  ======================================================================
#  Copyright (C) 2007-2010 Giampaolo Rodola' <g.rodola@gmail.com>
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
#  ======================================================================


"""pyftpdlib: RFC-959 asynchronous FTP server.

pyftpdlib implements a fully functioning asynchronous FTP server as
defined in RFC-959.  A hierarchy of classes outlined below implement
the backend functionality for the FTPd:

    [FTPServer] - the base class for the backend.

    [FTPHandler] - a class representing the server-protocol-interpreter
    (server-PI, see RFC-959). Each time a new connection occurs
    FTPServer will create a new FTPHandler instance to handle the
    current PI session.

    [ActiveDTP], [PassiveDTP] - base classes for active/passive-DTP
    backends.

    [DTPHandler] - this class handles processing of data transfer
    operations (server-DTP, see RFC-959).

    [ThrottledDTPHandler] - a DTPHandler subclass implementing transfer
    rates limits.

    [DummyAuthorizer] - an "authorizer" is a class handling FTPd
    authentications and permissions. It is used inside FTPHandler class
    to verify user passwords, to get user's home directory and to get
    permissions when a filesystem read/write occurs. "DummyAuthorizer"
    is the base authorizer class providing a platform independent
    interface for managing virtual users.

    [AbstractedFS] - class used to interact with the file system,
    providing a high level, cross-platform interface compatible
    with both Windows and UNIX style filesystems.

    [CallLater] - calls a function at a later time whithin the polling
    loop asynchronously.

    [AuthorizerError] - base class for authorizers exceptions.


pyftpdlib also provides 3 different logging streams through 3 functions
which can be overridden to allow for custom logging.

    [log] - the main logger that logs the most important messages for
    the end user regarding the FTPd.

    [logline] - this function is used to log commands and responses
    passing through the control FTP channel.

    [logerror] - log traceback outputs occurring in case of errors.


Usage example:

>>> from pyftpdlib import ftpserver
>>> authorizer = ftpserver.DummyAuthorizer()
>>> authorizer.add_user('user', 'password', '/home/user', perm='elradfmw')
>>> authorizer.add_anonymous('/home/nobody')
>>> ftp_handler = ftpserver.FTPHandler
>>> ftp_handler.authorizer = authorizer
>>> address = ("127.0.0.1", 21)
>>> ftpd = ftpserver.FTPServer(address, ftp_handler)
>>> ftpd.serve_forever()
Serving FTP on 127.0.0.1:21
[]127.0.0.1:2503 connected.
127.0.0.1:2503 ==> 220 Ready.
127.0.0.1:2503 <== USER anonymous
127.0.0.1:2503 ==> 331 Username ok, send password.
127.0.0.1:2503 <== PASS ******
127.0.0.1:2503 ==> 230 Login successful.
[anonymous]@127.0.0.1:2503 User anonymous logged in.
127.0.0.1:2503 <== TYPE A
127.0.0.1:2503 ==> 200 Type set to: ASCII.
127.0.0.1:2503 <== PASV
127.0.0.1:2503 ==> 227 Entering passive mode (127,0,0,1,9,201).
127.0.0.1:2503 <== LIST
127.0.0.1:2503 ==> 150 File status okay. About to open data connection.
[anonymous]@127.0.0.1:2503 OK LIST "/". Transfer starting.
127.0.0.1:2503 ==> 226 Transfer complete.
[anonymous]@127.0.0.1:2503 Transfer complete. 706 bytes transmitted.
127.0.0.1:2503 <== QUIT
127.0.0.1:2503 ==> 221 Goodbye.
[anonymous]@127.0.0.1:2503 Disconnected.
"""


import asyncore
import asynchat
import socket
import os
import sys
import traceback
import errno
import time
import glob
import tempfile
import warnings
import random
import stat
import heapq
import optparse
from tarfile import filemode as _filemode

try:
    import pwd
    import grp
except ImportError:
    pwd = grp = None


__all__ = ['proto_cmds', 'Error', 'log', 'logline', 'logerror', 'DummyAuthorizer',
           'AuthorizerError', 'FTPHandler', 'FTPServer', 'PassiveDTP',
           'ActiveDTP', 'DTPHandler', 'ThrottledDTPHandler', 'FileProducer',
           'BufferedIteratorProducer', 'AbstractedFS', 'CallLater']


__pname__   = 'Python FTP server library (pyftpdlib)'
__ver__     = '0.6.0'
__date__    = 'XXXX-XX-XX'
__author__  = "Giampaolo Rodola' <g.rodola@gmail.com>"
__web__     = 'http://code.google.com/p/pyftpdlib/'


proto_cmds = {
    # cmd : (perm, auth,  arg,   path,  help)
    'ABOR': (None, True,  False, False, 'Syntax: ABOR (abort transfer).'),
    'ALLO': (None, True,  True,  False, 'Syntax: ALLO <SP> bytes (noop; allocate storage).'),
    'APPE': ('a',  True,  True,  True,  'Syntax: APPE <SP> file-name (append data to an existent file).'),
    'CDUP': ('e',  True,  False, True,  'Syntax: CDUP (go to parent directory).'),
    'CWD' : ('e',  True,  None,  True,  'Syntax: CWD [<SP> dir-name] (change current working directory).'),
    'DELE': ('d',  True,  True,  True,  'Syntax: DELE <SP> file-name (delete file).'),
    'EPRT': (None, True,  True,  False, 'Syntax: EPRT <SP> |proto|ip|port| (set server in extended active mode).'),
    'EPSV': (None, True,  None,  False, 'Syntax: EPSV [<SP> proto/"ALL"] (set server in extended passive mode).'),
    'FEAT': (None, False, False, False, 'Syntax: FEAT (list all new features supported).'),
    'HELP': (None, False, None,  False, 'Syntax: HELP [<SP> cmd] (show help).'),
    'LIST': ('l',  True,  None,  True,  'Syntax: LIST [<SP> path-name] (list files).'),
    'MDTM': ('l', True,  True,  True,   'Syntax: MDTM [<SP> file-name] (get last modification time).'),
    'MLSD': ('l',  True,  None,  True,  'Syntax: MLSD [<SP> dir-name] (list files in a machine-processable form)'),
    'MLST': ('l',  True,  None,  True,  'Syntax: MLST [<SP> path-name] (show a path in a machine-processable form)'),
    'MODE': (None, True,  True,  False, 'Syntax: MODE <SP> mode (noop; set data transfer mode).'),
    'MKD' : ('m',  True,  True,  True,  'Syntax: MDK <SP> dir-name (create directory).'),
    'NLST': ('l',  True,  None,  True,  'Syntax: NLST [<SP> path-name] (list files in a compact form).'),
    'NOOP': (None, False, False, False, 'Syntax: NOOP (just do nothing).'),
    'OPTS': (None, True,  True,  False, 'Syntax: OPTS <SP> ftp-command [<SP> option] (specify options for FTP commands)'),
    'PASS': (None, False, True,  False, 'Syntax: PASS <SP> user-name (set user password).'),
    'PASV': (None, True,  False, False, 'Syntax: PASV (set server in passive mode).'),
    'PORT': (None, True,  True,  False, 'Syntax: PORT <sp> h1,h2,h3,h4,p1,p2 (set server in active mode).'),
    'PWD' : (None, True,  False, False, 'Syntax: PWD (get current working directory).'),
    'QUIT': (None, False, False, False, 'Syntax: QUIT (quit current session).'),
    'REIN': (None, True,  False, False, 'Syntax: REIN (reinitialize / flush account).'),
    'REST': (None, True,  True,  False, 'Syntax: REST <SP> marker (restart file position).'),
    'RETR': ('r',  True,  True,  True,  'Syntax: RETR <SP> file-name (retrieve a file).'),
    'RMD' : ('d',  True,  True,  True,  'Syntax: RMD <SP> dir-name (remove directory).'),
    'RNFR': ('f',  True,  True,  True,  'Syntax: RNFR <SP> file-name (file renaming (source name)).'),
    'RNTO': (None, True,  True,  True,  'Syntax: RNTO <SP> file-name (file renaming (destination name)).'),
    'SITE': (None, False, True, False,  'Syntax: SITE <SP> site-command (execute the specified SITE command).'),
    'SITE HELP' : (None, False, None, False, 'Syntax: SITE HELP [<SP> site-command] (show SITE command help).'),
    'SIZE': ('l', True,  True,  True,   'Syntax: HELP <SP> file-name (get file size).'),
    'STAT': ('l',  False, None,  True,  'Syntax: STAT [<SP> path name] (status information [list files]).'),
    'STOR': ('w',  True,  True,  True,  'Syntax: STOR <SP> file-name (store a file).'),
    'STOU': ('w',  True,  None,  True,  'Syntax: STOU [<SP> file-name] (store a file with a unique name).'),
    'STRU': (None, True,  True,  False, 'Syntax: STRU <SP> type (noop; set file structure).'),
    'SYST': (None, False, False, False, 'Syntax: SYST (get operating system type).'),
    'TYPE': (None, True,  True,  False, 'Syntax: TYPE <SP> [A | I] (set transfer type).'),
    'USER': (None, False, True,  False, 'Syntax: USER <SP> user-name (set username).'),
    'XCUP': ('e',  True,  False, True,  'Syntax: XCUP (obsolete; go to parent directory).'),
    'XCWD': ('e',  True,  None,  True,  'Syntax: XCWD [<SP> dir-name] (obsolete; change current directory).'),
    'XMKD': ('m',  True,  True,  True,  'Syntax: XMDK <SP> dir-name (obsolete; create directory).'),
    'XPWD': (None, True,  False, False, 'Syntax: XPWD (obsolete; get current dir).'),
    'XRMD': ('d',  True,  True,  True,  'Syntax: XRMD <SP> dir-name (obsolete; remove directory).'),
    }

class _CommandProperty:
    def __init__(self, perm, auth_needed, arg_needed, check_path, help):
        self.perm = perm
        self.auth_needed = auth_needed
        self.arg_needed = arg_needed
        self.check_path = check_path
        self.help = help

for cmd, properties in proto_cmds.iteritems():
    proto_cmds[cmd] = _CommandProperty(*properties)
del cmd, properties

def _strerror(err):
    """A wrap around os.strerror() which may be not available on all
    platforms (e.g. pythonCE).

     - (instance) err: an EnvironmentError or derived class instance.
    """
    if hasattr(os, 'strerror'):
        return os.strerror(err.errno)
    else:
        return err.strerror

# the heap used for the scheduled tasks
_tasks = []

def _scheduler():
    """Run the scheduled functions due to expire soonest (if any)."""
    now = time.time()
    while _tasks and now >= _tasks[0].timeout:
        call = heapq.heappop(_tasks)
        if call.repush:
            heapq.heappush(_tasks, call)
            call.repush = False
            continue
        try:
            call.call()
        finally:
            if not call.cancelled:
                call.cancel()


class CallLater(object):
    """Calls a function at a later time.

    It can be used to asynchronously schedule a call within the polling
    loop without blocking it. The instance returned is an object that
    can be used to cancel or reschedule the call.
    """

    def __init__(self, seconds, target, *args, **kwargs):
        """
         - (int) seconds: the number of seconds to wait
         - (obj) target: the callable object to call later
         - args: the arguments to call it with
         - kwargs: the keyword arguments to call it with
        """
        assert callable(target), "%s is not callable" % target
        assert sys.maxint >= seconds >= 0, "%s is not greater than or equal " \
                                           "to 0 seconds" % seconds
        self.__delay = seconds
        self.__target = target
        self.__args = args
        self.__kwargs = kwargs
        # seconds from the epoch at which to call the function
        self.timeout = time.time() + self.__delay
        self.repush = False
        self.cancelled = False
        heapq.heappush(_tasks, self)

    def __le__(self, other):
        return self.timeout <= other.timeout

    def call(self):
        """Call this scheduled function."""
        assert not self.cancelled, "Already cancelled"
        self.__target(*self.__args, **self.__kwargs)

    def reset(self):
        """Reschedule this call resetting the current countdown."""
        assert not self.cancelled, "Already cancelled"
        self.timeout = time.time() + self.__delay
        self.repush = True

    def delay(self, seconds):
        """Reschedule this call for a later time."""
        assert not self.cancelled, "Already cancelled."
        assert sys.maxint >= seconds >= 0, "%s is not greater than or equal " \
                                           "to 0 seconds" % seconds
        self.__delay = seconds
        newtime = time.time() + self.__delay
        if newtime > self.timeout:
            self.timeout = newtime
            self.repush = True
        else:
            # XXX - slow, can be improved
            self.timeout = newtime
            heapq.heapify(_tasks)

    def cancel(self):
        """Unschedule this call."""
        assert not self.cancelled, "Already cancelled"
        self.cancelled = True
        del self.__target, self.__args, self.__kwargs
        if self in _tasks:
            pos = _tasks.index(self)
            if pos == 0:
                heapq.heappop(_tasks)
            elif pos == len(_tasks) - 1:
                _tasks.pop(pos)
            else:
                _tasks[pos] = _tasks.pop()
                heapq._siftup(_tasks, pos)


# --- library defined exceptions

class Error(Exception):
    """Base class for module exceptions."""

class AuthorizerError(Error):
    """Base class for authorizer exceptions."""


# --- loggers

def log(msg):
    """Log messages intended for the end user."""
    print msg

def logline(msg):
    """Log commands and responses passing through the command channel."""
    print msg

def logerror(msg):
    """Log traceback outputs occurring in case of errors."""
    sys.stderr.write(str(msg) + '\n')
    sys.stderr.flush()


# --- authorizers

class DummyAuthorizer(object):
    """Basic "dummy" authorizer class, suitable for subclassing to
    create your own custom authorizers.

    An "authorizer" is a class handling authentications and permissions
    of the FTP server.  It is used inside FTPHandler class for verifying
    user's password, getting users home directory, checking user
    permissions when a file read/write event occurs and changing user
    before accessing the filesystem.

    DummyAuthorizer is the base authorizer, providing a platform
    independent interface for managing "virtual" FTP users. System
    dependent authorizers can by written by subclassing this base
    class and overriding appropriate methods as necessary.
    """

    read_perms = "elr"
    write_perms = "adfmw"

    def __init__(self):
        self.user_table = {}

    def add_user(self, username, password, homedir, perm='elr',
                    msg_login="Login successful.", msg_quit="Goodbye."):
        """Add a user to the virtual users table.

        AuthorizerError exceptions raised on error conditions such as
        invalid permissions, missing home directory or duplicate usernames.

        Optional perm argument is a string referencing the user's
        permissions explained below:

        Read permissions:
         - "e" = change directory (CWD command)
         - "l" = list files (LIST, NLST, STAT, MLSD, MLST, SIZE, MDTM commands)
         - "r" = retrieve file from the server (RETR command)

        Write permissions:
         - "a" = append data to an existing file (APPE command)
         - "d" = delete file or directory (DELE, RMD commands)
         - "f" = rename file or directory (RNFR, RNTO commands)
         - "m" = create directory (MKD command)
         - "w" = store a file to the server (STOR, STOU commands)

        Optional msg_login and msg_quit arguments can be specified to
        provide customized response strings when user log-in and quit.
        """
        if self.has_user(username):
            raise ValueError('user "%s" already exists' % username)
        if not os.path.isdir(homedir):
            raise ValueError('no such directory: "%s"' % homedir)
        homedir = os.path.realpath(homedir)
        self._check_permissions(username, perm)
        dic = {'pwd': str(password),
               'home': homedir,
               'perm': perm,
               'operms': {},
               'msg_login': str(msg_login),
               'msg_quit': str(msg_quit)
               }
        self.user_table[username] = dic

    def add_anonymous(self, homedir, **kwargs):
        """Add an anonymous user to the virtual users table.

        AuthorizerError exception raised on error conditions such as
        invalid permissions, missing home directory, or duplicate
        anonymous users.

        The keyword arguments in kwargs are the same expected by
        add_user method: "perm", "msg_login" and "msg_quit".

        The optional "perm" keyword argument is a string defaulting to
        "elr" referencing "read-only" anonymous user's permissions.

        Using write permission values ("adfmw") results in a
        RuntimeWarning.
        """
        DummyAuthorizer.add_user(self, 'anonymous', '', homedir, **kwargs)

    def remove_user(self, username):
        """Remove a user from the virtual users table."""
        del self.user_table[username]

    def override_perm(self, username, directory, perm, recursive=False):
        """Override permissions for a given directory."""
        self._check_permissions(username, perm)
        if not os.path.isdir(directory):
            raise ValueError('no such directory: "%s"' % directory)
        directory = os.path.normcase(os.path.realpath(directory))
        home = os.path.normcase(self.get_home_dir(username))
        if directory == home:
            raise ValueError("can't override home directory permissions")
        if not self._issubpath(directory, home):
            raise ValueError("path escapes user home directory")
        self.user_table[username]['operms'][directory] = perm, recursive

    def validate_authentication(self, username, password):
        """Return True if the supplied username and password match the
        stored credentials."""
        if not self.has_user(username):
            return False
        if username == 'anonymous':
            return True
        return self.user_table[username]['pwd'] == password

    def impersonate_user(self, username, password):
        """Impersonate another user (noop).

        It is always called before accessing the filesystem.
        By default it does nothing.  The subclass overriding this
        method is expected to provide a mechanism to change the
        current user.
        """

    def terminate_impersonation(self, username):
        """Terminate impersonation (noop).

        It is always called after having accessed the filesystem.
        By default it does nothing.  The subclass overriding this
        method is expected to provide a mechanism to switch back
        to the original user.
        """

    def has_user(self, username):
        """Whether the username exists in the virtual users table."""
        return username in self.user_table

    def has_perm(self, username, perm, path=None):
        """Whether the user has permission over path (an absolute
        pathname of a file or a directory).

        Expected perm argument is one of the following letters:
        "elradfmw".
        """
        if path is None:
            return perm in self.user_table[username]['perm']

        path = os.path.normcase(path)
        for dir in self.user_table[username]['operms'].keys():
            operm, recursive = self.user_table[username]['operms'][dir]
            if self._issubpath(path, dir):
                if recursive:
                    return perm in operm
                if (path == dir) or (os.path.dirname(path) == dir \
                and not os.path.isdir(path)):
                    return perm in operm

        return perm in self.user_table[username]['perm']

    def get_perms(self, username):
        """Return current user permissions."""
        return self.user_table[username]['perm']

    def get_home_dir(self, username):
        """Return the user's home directory."""
        return self.user_table[username]['home']

    def get_msg_login(self, username):
        """Return the user's login message."""
        return self.user_table[username]['msg_login']

    def get_msg_quit(self, username):
        """Return the user's quitting message."""
        return self.user_table[username]['msg_quit']

    def _check_permissions(self, username, perm):
        warned = 0
        for p in perm:
            if p not in self.read_perms + self.write_perms:
                raise ValueError('no such permission "%s"' % p)
            if (username == 'anonymous') and (p in self.write_perms) and not warned:
                warnings.warn("write permissions assigned to anonymous user.",
                              RuntimeWarning)
                warned = 1

    def _issubpath(self, a, b):
        """Return True if a is a sub-path of b or if the paths are equal."""
        p1 = a.rstrip(os.sep).split(os.sep)
        p2 = b.rstrip(os.sep).split(os.sep)
        return p1[:len(p2)] == p2



# --- DTP classes

class PassiveDTP(object, asyncore.dispatcher):
    """This class is an asyncore.dispatcher subclass. It creates a
    socket listening on a local port, dispatching the resultant
    connection to DTPHandler.

     - (int) timeout: the timeout for a remote client to establish
       connection with the listening socket. Defaults to 30 seconds.
    """
    timeout = 30

    def __init__(self, cmd_channel, extmode=False):
        """Initialize the passive data server.

         - (instance) cmd_channel: the command channel class instance.
         - (bool) extmode: wheter use extended passive mode response type.
        """
        asyncore.dispatcher.__init__(self)
        self.cmd_channel = cmd_channel
        if self.timeout:
            self.idler = CallLater(self.timeout, self.handle_timeout)
        else:
            self.idler = None

        local_ip = self.cmd_channel.socket.getsockname()[0]
        if local_ip in self.cmd_channel.masquerade_address_map:
            masqueraded_ip = self.cmd_channel.masquerade_address_map[local_ip]
        elif self.cmd_channel.masquerade_address:
            masqueraded_ip = self.cmd_channel.masquerade_address
        else:
            masqueraded_ip = None

        self.create_socket(self.cmd_channel._af, socket.SOCK_STREAM)

        if self.cmd_channel.passive_ports is None:
            # By using 0 as port number value we let kernel choose a
            # free unprivileged random port.
            self.bind((local_ip, 0))
        else:
            ports = list(self.cmd_channel.passive_ports)
            while ports:
                port = ports.pop(random.randint(0, len(ports) -1))
                try:
                    self.bind((local_ip, port))
                except socket.error, why:
                    if why[0] == errno.EADDRINUSE:  # port already in use
                        if ports:
                            continue
                        # If cannot use one of the ports in the configured
                        # range we'll use a kernel-assigned port, and log
                        # a message reporting the issue.
                        # By using 0 as port number value we let kernel
                        # choose a free unprivileged random port.
                        else:
                            self.bind((local_ip, 0))
                            self.cmd_channel.log(
                                "Can't find a valid passive port in the "
                                "configured range. A random kernel-assigned "
                                "port will be used."
                                )
                    else:
                        raise
                else:
                    break
        self.listen(5)

        port = self.socket.getsockname()[1]
        if not extmode:
            ip = masqueraded_ip or local_ip
            if ip.startswith('::ffff:'):
                # In this scenario, the server has an IPv6 socket, but
                # the remote client is using IPv4 and its address is
                # represented as an IPv4-mapped IPv6 address which
                # looks like this ::ffff:151.12.5.65, see:
                # http://en.wikipedia.org/wiki/IPv6#IPv4-mapped_addresses
                # http://tools.ietf.org/html/rfc3493.html#section-3.7
                # We truncate the first bytes to make it look like a
                # common IPv4 address.
                ip = ip[7:]
            # The format of 227 response in not standardized.
            # This is the most expected:
            self.cmd_channel.respond('227 Entering passive mode (%s,%d,%d).' % (
                                ip.replace('.', ','), port / 256, port % 256))
        else:
            self.cmd_channel.respond('229 Entering extended passive mode '
                                     '(|||%d|).' % port)

    # --- connection / overridden

    def handle_accept(self):
        """Called when remote client initiates a connection."""
        try:
            sock, addr = self.accept()
        except TypeError:
            # sometimes accept() might return None (see issue 91)
            return
        except socket.error, err:
            # ECONNABORTED might be thrown on *BSD (see issue 105)
            if err[0] != errno.ECONNABORTED:
                logerror(traceback.format_exc())
            return
        else:
            # sometimes addr == None instead of (ip, port) (see issue 104)
            if addr == None:
                return

        # Check the origin of data connection.  If not expressively
        # configured we drop the incoming data connection if remote
        # IP address does not match the client's IP address.
        if (self.cmd_channel.remote_ip != addr[0]):
            if not self.cmd_channel.permit_foreign_addresses:
                try:
                    sock.close()
                except socket.error:
                    pass
                msg = 'Rejected data connection from foreign address %s:%s.' \
                        %(addr[0], addr[1])
                self.cmd_channel.respond("425 %s" % msg)
                self.cmd_channel.log(msg)
                # do not close listening socket: it couldn't be client's blame
                return
            else:
                # site-to-site FTP allowed
                msg = 'Established data connection with foreign address %s:%s.'\
                        % (addr[0], addr[1])
                self.cmd_channel.log(msg)
        # Immediately close the current channel (we accept only one
        # connection at time) and avoid running out of max connections
        # limit.
        self.close()
        # delegate such connection to DTP handler
        handler = self.cmd_channel.dtp_handler(sock, self.cmd_channel)
        if handler.connected:
            self.cmd_channel.data_channel = handler
            self.cmd_channel._on_dtp_connection()

    def handle_timeout(self):
        self.cmd_channel.respond("421 Passive data channel timed out.")
        self.close()

    def writable(self):
        return 0

    def handle_error(self):
        """Called to handle any uncaught exceptions."""
        try:
            raise
        except (KeyboardInterrupt, SystemExit, asyncore.ExitNow):
            raise
        except:
            logerror(traceback.format_exc())
        self.close()

    def close(self):
        asyncore.dispatcher.close(self)
        if self.idler is not None and not self.idler.cancelled:
            self.idler.cancel()


class ActiveDTP(object, asyncore.dispatcher):
    """This class is an asyncore.disptacher subclass. It creates a
    socket resulting from the connection to a remote user-port,
    dispatching it to DTPHandler.

     - (int) timeout: the timeout for us to establish connection with
       the client's listening data socket.
    """
    timeout = 30
    source_address = None

    def __init__(self, ip, port, cmd_channel):
        """Initialize the active data channel attemping to connect
        to remote data socket.

         - (str) ip: the remote IP address.
         - (int) port: the remote port.
         - (instance) cmd_channel: the command channel class instance.
        """
        asyncore.dispatcher.__init__(self)
        self.cmd_channel = cmd_channel
        if self.timeout:
            self.idler = CallLater(self.timeout, self.handle_timeout)
        else:
            self.idler = None
        self.create_socket(self.cmd_channel._af, socket.SOCK_STREAM)
        # Have the active connection come from the same IP address
        # as the command channel, see:
        # http://code.google.com/p/pyftpdlib/issues/detail?id=123
        source_ip = self.cmd_channel.socket.getsockname()[0]
        self.bind((source_ip, 0))
        try:
            self.connect((ip, port))
        except (socket.gaierror, socket.error), err:
            self.close()
            msg = "425 Can't connect to specified address."
            if hasattr(err, 'errno'):
                msg += " %s." % _strerror(err)
            self.cmd_channel.respond(msg)

    # overridden to prevent unhandled read/write event messages to
    # be printed by asyncore on Python < 2.6

    def handle_write(self):
        pass

    def handle_read(self):
        pass

    def handle_connect(self):
        """Called when connection is established."""
        if self.idler is not None and not self.idler.cancelled:
            self.idler.cancel()
        self.cmd_channel.respond('200 Active data connection established.')
        # delegate such connection to DTP handler
        handler = self.cmd_channel.dtp_handler(self.socket, self.cmd_channel)
        self.cmd_channel.data_channel = handler
        self.cmd_channel._on_dtp_connection()
        # Can't close right now as the handler would have the socket
        # object disconnected.  This class will be "closed" once the
        # data transfer is completed or the client disconnects.
        #self.close()

    def handle_timeout(self):
        self.cmd_channel.respond("421 Active data channel timed out.")
        self.close()

    def handle_expt(self):
        self.cmd_channel.respond("425 Can't connect to specified address.")
        self.close()

    def handle_error(self):
        """Called to handle any uncaught exceptions."""
        try:
            raise
        except (KeyboardInterrupt, SystemExit, asyncore.ExitNow):
            raise
        except:
            logerror(traceback.format_exc())
        self.cmd_channel.respond("425 Can't connect to specified address.")
        self.close()

    def close(self):
        asyncore.dispatcher.close(self)
        if self.idler is not None and not self.idler.cancelled:
            self.idler.cancel()


class DTPHandler(object, asynchat.async_chat):
    """Class handling server-data-transfer-process (server-DTP, see
    RFC-959) managing data-transfer operations involving sending
    and receiving data.

    Class attributes:

     - (int) timeout: the timeout which roughly is the maximum time we
       permit data transfers to stall for with no progress. If the
       timeout triggers, the remote client will be kicked off
       (defaults 300).

     - (int) ac_in_buffer_size: incoming data buffer size (defaults 65536)

     - (int) ac_out_buffer_size: outgoing data buffer size (defaults 65536)
    """

    timeout = 300
    ac_in_buffer_size = 65536
    ac_out_buffer_size = 65536

    def __init__(self, sock_obj, cmd_channel):
        """Initialize the command channel.

         - (instance) sock_obj: the socket object instance of the newly
            established connection.
         - (instance) cmd_channel: the command channel class instance.
        """
        self.cmd_channel = cmd_channel
        self.file_obj = None
        self.receive = False
        self.transfer_finished = False
        self.tot_bytes_sent = 0
        self.tot_bytes_received = 0
        self.data_wrapper = lambda x: x
        self._lastdata = 0
        self._closed = False
        self._had_cr = False
        self._start_time = time.time()
        if self.timeout:
            self.idler = CallLater(self.timeout, self.handle_timeout)
        else:
            self.idler = None
        try:
            asynchat.async_chat.__init__(self, sock_obj)
        except socket.error, err:
            # http://code.google.com/p/pyftpdlib/issues/detail?id=143
            self.close()
            if err[0] == errno.EINVAL:
                return
            return self.handle_error()
        # remove this instance from asyncore socket map
        if not self.connected:
            self.close()

    # --- utility methods

    def _posix_ascii_data_wrapper(self, chunk):
        """The data wrapper used for receiving data in ASCII mode on
        systems using a single line terminator, handling those cases
        where CRLF ('\r\n') gets delivered in two chunks.
        """
        if self._had_cr:
            chunk = '\r' + chunk

        if chunk.endswith('\r'):
            self._had_cr = True
            chunk = chunk[:-1]
        else:
            self._had_cr = False

        return chunk.replace('\r\n', os.linesep)

    def enable_receiving(self, type):
        """Enable receiving of data over the channel. Depending on the
        TYPE currently in use it creates an appropriate wrapper for the
        incoming data.

         - (str) type: current transfer type, 'a' (ASCII) or 'i' (binary).
        """
        if type == 'a':
            if os.linesep == '\r\n':
                self.data_wrapper = lambda x: x
            else:
                self.data_wrapper = self._posix_ascii_data_wrapper
        elif type == 'i':
            self.data_wrapper = lambda x: x
        else:
            raise TypeError("unsupported type")
        self.receive = True

    def get_transmitted_bytes(self):
        "Return the number of transmitted bytes."
        return self.tot_bytes_sent + self.tot_bytes_received

    def get_elapsed_time(self):
        "Return the transfer elapsed time in seconds."
        return time.time() - self._start_time

    def transfer_in_progress(self):
        "Return True if a transfer is in progress, else False."
        return self.get_transmitted_bytes() != 0

    # --- connection

    def send(self, data):
        result = asyncore.dispatcher.send(self, data)
        self.tot_bytes_sent += result
        return result

    def refill_buffer (self):
        """Overridden as a fix around http://bugs.python.org/issue1740572
        (when the producer is consumed, close() was called instead of
        handle_close()).
        """
        while 1:
            if len(self.producer_fifo):
                p = self.producer_fifo.first()
                # a 'None' in the producer fifo is a sentinel,
                # telling us to close the channel.
                if p is None:
                    if not self.ac_out_buffer:
                        self.producer_fifo.pop()
                        #self.close()
                        self.handle_close()
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

    def handle_read(self):
        """Called when there is data waiting to be read."""
        try:
            chunk = self.recv(self.ac_in_buffer_size)
        except socket.error:
            self.handle_error()
        else:
            self.tot_bytes_received += len(chunk)
            if not chunk:
                self.transfer_finished = True
                #self.close()  # <-- asyncore.recv() already do that...
                return
            # while we're writing on the file an exception could occur
            # in case  that filesystem gets full;  if this happens we
            # let handle_error() method handle this exception, providing
            # a detailed error message.
            self.file_obj.write(self.data_wrapper(chunk))

    def readable(self):
        """Predicate for inclusion in the readable for select()."""
        # we don't use asynchat's find terminator feature so we can
        # freely avoid to call the original implementation
        return self.receive

    def writable(self):
        """Predicate for inclusion in the writable for select()."""
        return not self.receive and asynchat.async_chat.writable(self)

    def handle_timeout(self):
        """Called cyclically to check if data trasfer is stalling with
        no progress in which case the client is kicked off.
        """
        if self.get_transmitted_bytes() > self._lastdata:
            self._lastdata = self.get_transmitted_bytes()
            self.idler = CallLater(self.timeout, self.handle_timeout)
        else:
            msg = "Data connection timed out."
            self.cmd_channel.log(msg)
            self.cmd_channel.respond("421 " + msg)
            self.cmd_channel.close_when_done()
            self.close()

    def handle_expt(self):
        """Called on "exceptional" data events."""
        self.cmd_channel.respond("426 Connection error; transfer aborted.")
        self.close()

    def handle_error(self):
        """Called when an exception is raised and not otherwise handled."""
        try:
            raise
        except (KeyboardInterrupt, SystemExit, asyncore.ExitNow):
            raise
        except socket.error, err:
            # fixes around various bugs:
            # - http://bugs.python.org/issue1736101
            # - http://code.google.com/p/pyftpdlib/issues/detail?id=104
            # - http://code.google.com/p/pyftpdlib/issues/detail?id=109
            if err[0] in (errno.ECONNRESET, errno.ENOTCONN, errno.ESHUTDOWN, \
                          errno.ECONNABORTED, errno.EPIPE, errno.EBADF):
                self.handle_close()
                return
            else:
                logerror(traceback.format_exc())
                error = str(err[1])
        # an error could occur in case we fail reading / writing
        # from / to file (e.g. file system gets full)
        except EnvironmentError, err:
            error = _strerror(err)
        except:
            # some other exception occurred;  we don't want to provide
            # confidential error messages
            logerror(traceback.format_exc())
            error = "Internal error"
        self.cmd_channel.respond("426 %s; transfer aborted." % error)
        self.close()

    def handle_close(self):
        """Called when the socket is closed."""
        # If we used channel for receiving we assume that transfer is
        # finished when client closes the connection, if we used channel
        # for sending we have to check that all data has been sent
        # (responding with 226) or not (responding with 426).
        # In both cases handle_close() is automatically called by the
        # underlying asynchat module.
        if self.receive:
            self.transfer_finished = True
        else:
            self.transfer_finished = len(self.producer_fifo) == 0
        if self.transfer_finished:
            self.cmd_channel.respond("226 Transfer complete.")
        else:
            tot_bytes = self.get_transmitted_bytes()
            msg = "Transfer aborted; %d bytes transmitted." % tot_bytes
            self.cmd_channel.respond("426 " + msg)
        self.close()

    def close(self):
        """Close the data channel, first attempting to close any remaining
        file handles."""
        if not self._closed:
            self._closed = True
            asyncore.dispatcher.close(self)
            if self.file_obj is not None and not self.file_obj.closed:
                self.file_obj.close()
            if self.idler is not None and not self.idler.cancelled:
                self.idler.cancel()
            if self.file_obj is not None:
                filename = self.file_obj.name
                elapsed_time = round(self.get_elapsed_time(), 3)
                self.cmd_channel.log_transfer(receive=self.receive,
                                              filename=self.file_obj.name,
                                              completed=self.transfer_finished,
                                              elapsed=elapsed_time,
                                              bytes=self.get_transmitted_bytes())
                if self.transfer_finished:
                    if self.receive:
                        self.cmd_channel.on_file_received(filename)
                    else:
                        self.cmd_channel.on_file_sent(filename)
                else:
                    if self.receive:
                        self.cmd_channel.on_incomplete_file_received(filename)
                    else:
                        self.cmd_channel.on_incomplete_file_sent(filename)
            self.cmd_channel._on_dtp_close()


class ThrottledDTPHandler(DTPHandler):
    """A DTPHandler subclass which wraps sending and receiving in a data
    counter and temporarily "sleeps" the channel so that you burst to no
    more than x Kb/sec average.

     - (int) read_limit: the maximum number of bytes to read (receive)
       in one second (defaults to 0 == no limit).

     - (int) write_limit: the maximum number of bytes to write (send)
       in one second (defaults to 0 == no limit).

     - (bool) auto_sized_buffers: this option only applies when read
       and/or write limits are specified. When enabled it bumps down
       the data buffer sizes so that they are never greater than read
       and write limits which results in a less bursty and smoother
       throughput (default: True).
    """
    read_limit = 0
    write_limit = 0
    auto_sized_buffers = True

    def __init__(self, sock_obj, cmd_channel):
        DTPHandler.__init__(self, sock_obj, cmd_channel)
        self._timenext = 0
        self._datacount = 0
        self.sleeping = False
        self._throttler = None

        if self.auto_sized_buffers:
            if self.read_limit:
                while self.ac_in_buffer_size > self.read_limit:
                    self.ac_in_buffer_size /= 2
            if self.write_limit:
                while self.ac_out_buffer_size > self.write_limit:
                    self.ac_out_buffer_size /= 2

    def readable(self):
        return not self.sleeping and DTPHandler.readable(self)

    def writable(self):
        return not self.sleeping and DTPHandler.writable(self)

    def recv(self, buffer_size):
        chunk = DTPHandler.recv(self, buffer_size)
        if self.read_limit:
            self._throttle_bandwidth(len(chunk), self.read_limit)
        return chunk

    def send(self, data):
        num_sent = DTPHandler.send(self, data)
        if self.write_limit:
            self._throttle_bandwidth(num_sent, self.write_limit)
        return num_sent

    def _throttle_bandwidth(self, len_chunk, max_speed):
        """A method which counts data transmitted so that you burst to
        no more than x Kb/sec average.
        """
        self._datacount += len_chunk
        if self._datacount >= max_speed:
            self._datacount = 0
            now = time.time()
            sleepfor = self._timenext - now
            if sleepfor > 0:
                # we've passed bandwidth limits
                def unsleep():
                    self.sleeping = False
                self.sleeping = True
                self._throttler = CallLater(sleepfor * 2, unsleep)
            self._timenext = now + 1

    def close(self):
        if self._throttler is not None and not self._throttler.cancelled:
            self._throttler.cancel()
        DTPHandler.close(self)


# --- producers

class FileProducer(object):
    """Producer wrapper for file[-like] objects."""

    buffer_size = 65536

    def __init__(self, file, type):
        """Initialize the producer with a data_wrapper appropriate to TYPE.

         - (file) file: the file[-like] object.
         - (str) type: the current TYPE, 'a' (ASCII) or 'i' (binary).
        """
        self.done = False
        self.file = file
        if type == 'a':
            if os.linesep == '\r\n':
                self.data_wrapper = lambda x: x
            else:
                self.data_wrapper = lambda x: x.replace(os.linesep, '\r\n')
        elif type == 'i':
            self.data_wrapper = lambda x: x
        else:
            raise TypeError("unsupported type")

    def more(self):
        """Attempt a chunk of data of size self.buffer_size."""
        if self.done:
            return ''
        data = self.data_wrapper(self.file.read(self.buffer_size))
        if not data:
            self.done = True
            if not self.file.closed:
                self.file.close()
        return data


class BufferedIteratorProducer(object):
    """Producer for iterator objects with buffer capabilities."""
    # how many times iterator.next() will be called before
    # returning some data
    loops = 20

    def __init__(self, iterator):
        self.iterator = iterator

    def more(self):
        """Attempt a chunk of data from iterator by calling
        its next() method different times.
        """
        buffer = []
        for x in xrange(self.loops):
            try:
                buffer.append(self.iterator.next())
            except StopIteration:
                break
        return ''.join(buffer)


# --- filesystem

class AbstractedFS(object):
    """A class used to interact with the file system, providing a
    cross-platform interface compatible with both Windows and
    UNIX style filesystems where all paths use "/" separator.

    AbstractedFS distinguishes between "real" filesystem paths and
    "virtual" ftp paths emulating a UNIX chroot jail where the user
    can not escape its home directory (example: real "/home/user"
    path will be seen as "/" by the client)

    It also provides some utility methods and wraps around all os.*
    calls involving operations against the filesystem like creating
    files or removing directories.
    """

    def __init__(self, root, cmd_channel):
        """
         - (str) root: the user "real" home directory (e.g. '/home/user')
         - (instance) cmd_channel: the FTPHandler class instance
        """
        # Set initial current working directory.
        # By default initial cwd is set to "/" to emulate a chroot jail.
        # If a different behavior is desired (e.g. initial cwd = root,
        # to reflect the real filesystem) users overriding this class
        # are responsible to set _cwd attribute as necessary.
        self._cwd = '/'
        self._root = root
        self.cmd_channel = cmd_channel

    @property
    def root(self):
        """The user home directory."""
        return self._root

    @property
    def cwd(self):
        """The user current working directory."""
        return self._cwd

    # --- Pathname / conversion utilities

    def ftpnorm(self, ftppath):
        """Normalize a "virtual" ftp pathname (tipically the raw string
        coming from client) depending on the current working directory.

        Example (having "/foo" as current working directory):
        >>> ftpnorm('bar')
        '/foo/bar'

        Note: directory separators are system independent ("/").
        Pathname returned is always absolutized.
        """
        if os.path.isabs(ftppath):
            p = os.path.normpath(ftppath)
        else:
            p = os.path.normpath(os.path.join(self.cwd, ftppath))
        # normalize string in a standard web-path notation having '/'
        # as separator.
        p = p.replace("\\", "/")
        # os.path.normpath supports UNC paths (e.g. "//a/b/c") but we
        # don't need them.  In case we get an UNC path we collapse
        # redundant separators appearing at the beginning of the string
        while p[:2] == '//':
            p = p[1:]
        # Anti path traversal: don't trust user input, in the event
        # that self.cwd is not absolute, return "/" as a safety measure.
        # This is for extra protection, maybe not really necessary.
        if not os.path.isabs(p):
            p = "/"
        return p

    def ftp2fs(self, ftppath):
        """Translate a "virtual" ftp pathname (tipically the raw string
        coming from client) into equivalent absolute "real" filesystem
        pathname.

        Example (having "/home/user" as root directory):
        >>> ftp2fs("foo")
        '/home/user/foo'

        Note: directory separators are system dependent.
        """
        # as far as I know, it should always be path traversal safe...
        if os.path.normpath(self.root) == os.sep:
            return os.path.normpath(self.ftpnorm(ftppath))
        else:
            p = self.ftpnorm(ftppath)[1:]
            return os.path.normpath(os.path.join(self.root, p))

    def fs2ftp(self, fspath):
        """Translate a "real" filesystem pathname into equivalent
        absolute "virtual" ftp pathname depending on the user's
        root directory.

        Example (having "/home/user" as root directory):
        >>> fs2ftp("/home/user/foo")
        '/foo'

        As for ftpnorm, directory separators are system independent
        ("/") and pathname returned is always absolutized.

        On invalid pathnames escaping from user's root directory
        (e.g. "/home" when root is "/home/user") always return "/".
        """
        if os.path.isabs(fspath):
            p = os.path.normpath(fspath)
        else:
            p = os.path.normpath(os.path.join(self.root, fspath))
        if not self.validpath(p):
            return '/'
        p = p.replace(os.sep, "/")
        p = p[len(self.root):]
        if not p.startswith('/'):
            p = '/' + p
        return p

    def validpath(self, path):
        """Check whether the path belongs to user's home directory.
        Expected argument is a "real" filesystem pathname.

        If path is a symbolic link it is resolved to check its real
        destination.

        Pathnames escaping from user's root directory are considered
        not valid.
        """
        root = self.realpath(self.root)
        path = self.realpath(path)
        if not root.endswith(os.sep):
            root = root + os.sep
        if not path.endswith(os.sep):
            path = path + os.sep
        if path[0:len(root)] == root:
            return True
        return False

    # --- Wrapper methods around open() and tempfile.mkstemp

    def open(self, filename, mode):
        """Open a file returning its handler."""
        return open(filename, mode)

    def mkstemp(self, suffix='', prefix='', dir=None, mode='wb'):
        """A wrap around tempfile.mkstemp creating a file with a unique
        name.  Unlike mkstemp it returns an object with a file-like
        interface.
        """
        class FileWrapper:
            def __init__(self, fd, name):
                self.file = fd
                self.name = name
            def __getattr__(self, attr):
                return getattr(self.file, attr)

        text = not 'b' in mode
        # max number of tries to find out a unique file name
        tempfile.TMP_MAX = 50
        fd, name = tempfile.mkstemp(suffix, prefix, dir, text=text)
        file = os.fdopen(fd, mode)
        return FileWrapper(file, name)

    # --- Wrapper methods around os.* calls

    def chdir(self, path):
        """Change the current directory."""
        # temporarily join the specified directory to see if we have
        # permissions to do so
        basedir = os.getcwd()
        try:
            os.chdir(path)
        except os.error:
            raise
        else:
            os.chdir(basedir)
            self._cwd = self.fs2ftp(path)

    def mkdir(self, path):
        """Create the specified directory."""
        os.mkdir(path)

    def listdir(self, path):
        """List the content of a directory."""
        return os.listdir(path)

    def rmdir(self, path):
        """Remove the specified directory."""
        os.rmdir(path)

    def remove(self, path):
        """Remove the specified file."""
        os.remove(path)

    def rename(self, src, dst):
        """Rename the specified src file to the dst filename."""
        os.rename(src, dst)

    def stat(self, path):
        """Perform a stat() system call on the given path."""
        return os.stat(path)

    def lstat(self, path):
        """Like stat but does not follow symbolic links."""
        return os.lstat(path)

    if not hasattr(os, 'lstat'):
        lstat = stat

    # --- Wrapper methods around os.path.* calls

    def isfile(self, path):
        """Return True if path is a file."""
        return os.path.isfile(path)

    def islink(self, path):
        """Return True if path is a symbolic link."""
        return os.path.islink(path)

    def isdir(self, path):
        """Return True if path is a directory."""
        return os.path.isdir(path)

    def getsize(self, path):
        """Return the size of the specified file in bytes."""
        return os.path.getsize(path)

    def getmtime(self, path):
        """Return the last modified time as a number of seconds since
        the epoch."""
        return os.path.getmtime(path)

    def realpath(self, path):
        """Return the canonical version of path eliminating any
        symbolic links encountered in the path (if they are
        supported by the operating system).
        """
        return os.path.realpath(path)

    def lexists(self, path):
        """Return True if path refers to an existing path, including
        a broken or circular symbolic link.
        """
        return os.path.lexists(path)

    def get_user_by_uid(self, uid):
        """Return the username associated with user id.
        If this can't be determined return raw uid instead.
        On Windows just return "owner".
        """
        if pwd is not None:
            try:
                return pwd.getpwuid(uid).pw_name
            except KeyError:
                return uid
        else:
            return "owner"

    def get_group_by_gid(self, gid):
        """Return the groupname associated with group id.
        If this can't be determined return raw gid instead.
        On Windows just return "group".
        """
        if grp is not None:
            try:
                return grp.getgrgid(gid).gr_name
            except KeyError:
                return gid
        else:
            return "group"

    if hasattr(os, 'readlink'):
        def readlink(self, path):
            """Return a string representing the path to which a
            symbolic link points.
            """
            return os.readlink(path)

    # --- Listing utilities

    def get_list_dir(self, path):
        """"Return an iterator object that yields a directory listing
        in a form suitable for LIST command.
        """
        if self.isdir(path):
            listing = self.listdir(path)
            listing.sort()
            return self.format_list(path, listing)
        # if path is a file or a symlink we return information about it
        else:
            basedir, filename = os.path.split(path)
            self.lstat(path)  # raise exc in case of problems
            return self.format_list(basedir, [filename])

    def format_list(self, basedir, listing, ignore_err=True):
        """Return an iterator object that yields the entries of given
        directory emulating the "/bin/ls -lA" UNIX command output.

         - (str) basedir: the absolute dirname.
         - (list) listing: the names of the entries in basedir
         - (bool) ignore_err: when False raise exception if os.lstat()
         call fails.

        On platforms which do not support the pwd and grp modules (such
        as Windows), ownership is printed as "owner" and "group" as a
        default, and number of hard links is always "1". On UNIX
        systems, the actual owner, group, and number of links are
        printed.

        This is how output appears to client:

        -rw-rw-rw-   1 owner   group    7045120 Sep 02  3:47 music.mp3
        drwxrwxrwx   1 owner   group          0 Aug 31 18:50 e-books
        -rw-rw-rw-   1 owner   group        380 Sep 02  3:40 module.py
        """
        if self.cmd_channel.use_gmt_times:
            timefunc = time.gmtime
        else:
            timefunc = time.localtime
        for basename in listing:
            file = os.path.join(basedir, basename)
            try:
                st = self.lstat(file)
            except os.error:
                if ignore_err:
                    continue
                raise
            perms = _filemode(st.st_mode)  # permissions
            nlinks = st.st_nlink  # number of links to inode
            if not nlinks:  # non-posix system, let's use a bogus value
                nlinks = 1
            size = st.st_size  # file size
            uname = self.get_user_by_uid(st.st_uid)
            gname = self.get_group_by_gid(st.st_gid)
            try:
                mtime = time.strftime("%b %d %H:%M", timefunc(st.st_mtime))
            except ValueError:
                # It could be raised if last mtime happens to be too
                # old (prior to year 1900) in which case we return
                # the current time as last mtime.
                mtime = time.strftime("%b %d %H:%M", timefunc())
            # if the file is a symlink, resolve it, e.g. "symlink -> realfile"
            if stat.S_ISLNK(st.st_mode) and hasattr(self, 'readlink'):
                basename = basename + " -> " + self.readlink(file)

            # formatting is matched with proftpd ls output
            yield "%s %3s %-8s %-8s %8s %s %s\r\n" % (perms, nlinks, uname, gname,
                                                      size, mtime, basename)

    def format_mlsx(self, basedir, listing, perms, facts, ignore_err=True):
        """Return an iterator object that yields the entries of a given
        directory or of a single file in a form suitable with MLSD and
        MLST commands.

        Every entry includes a list of "facts" referring the listed
        element.  See RFC-3659, chapter 7, to see what every single
        fact stands for.

         - (str) basedir: the absolute dirname.
         - (list) listing: the names of the entries in basedir
         - (str) perms: the string referencing the user permissions.
         - (str) facts: the list of "facts" to be returned.
         - (bool) ignore_err: when False raise exception if os.stat()
         call fails.

        Note that "facts" returned may change depending on the platform
        and on what user specified by using the OPTS command.

        This is how output could appear to the client issuing
        a MLSD request:

        type=file;size=156;perm=r;modify=20071029155301;unique=801cd2; music.mp3
        type=dir;size=0;perm=el;modify=20071127230206;unique=801e33; ebooks
        type=file;size=211;perm=r;modify=20071103093626;unique=801e32; module.py
        """
        if self.cmd_channel.use_gmt_times:
            timefunc = time.gmtime
        else:
            timefunc = time.localtime
        permdir = ''.join([x for x in perms if x not in 'arw'])
        permfile = ''.join([x for x in perms if x not in 'celmp'])
        if ('w' in perms) or ('a' in perms) or ('f' in perms):
            permdir += 'c'
        if 'd' in perms:
            permdir += 'p'
        type = size = perm = modify = create = unique = mode = uid = gid = ""
        for basename in listing:
            file = os.path.join(basedir, basename)
            # to properly implement 'unique' fact (RFC-3659, chapter
            # 7.5.2) we are supposed to follow symlinks, hence use
            # os.stat() instead of os.lstat()
            try:
                st = self.stat(file)
            except OSError:
                if ignore_err:
                    continue
                raise
            # type + perm
            if stat.S_ISDIR(st.st_mode):
                if 'type' in facts:
                    if basename == '.':
                        type = 'type=cdir;'
                    elif basename == '..':
                        type = 'type=pdir;'
                    else:
                        type = 'type=dir;'
                if 'perm' in facts:
                    perm = 'perm=%s;' % permdir
            else:
                if 'type' in facts:
                    type = 'type=file;'
                if 'perm' in facts:
                    perm = 'perm=%s;' % permfile
            if 'size' in facts:
                size = 'size=%s;' %st.st_size  # file size
            # last modification time
            if 'modify' in facts:
                try:
                    modify = 'modify=%s;' % time.strftime("%Y%m%d%H%M%S",
                                            timefunc(st.st_mtime))
                # it could be raised if last mtime happens to be too old
                # (prior to year 1900)
                except ValueError:
                    modify = ""
            if 'create' in facts:
                # on Windows we can provide also the creation time
                try:
                    create = 'create=%s;' % time.strftime("%Y%m%d%H%M%S",
                                            timefunc(st.st_ctime))
                except ValueError:
                    create = ""
            # UNIX only
            if 'unix.mode' in facts:
                mode = 'unix.mode=%s;' % oct(st.st_mode & 0777)
            if 'unix.uid' in facts:
                uid = 'unix.uid=%s;' % st.st_uid
            if 'unix.gid' in facts:
                gid = 'unix.gid=%s;' % st.st_gid

            # We provide unique fact (see RFC-3659, chapter 7.5.2) on
            # posix platforms only; we get it by mixing st_dev and
            # st_ino values which should be enough for granting an
            # uniqueness for the file listed.
            # The same approach is used by pure-ftpd.
            # Implementors who want to provide unique fact on other
            # platforms should use some platform-specific method (e.g.
            # on Windows NTFS filesystems MTF records could be used).
            if 'unique' in facts:
                unique = "unique=%x%x;" % (st.st_dev, st.st_ino)

            yield "%s%s%s%s%s%s%s%s%s %s\r\n" % (type, size, perm, modify,
                                                 create, mode, uid, gid, unique,
                                                 basename)


# --- FTP

class FTPHandler(object, asynchat.async_chat):
    """Implements the FTP server Protocol Interpreter (see RFC-959),
    handling commands received from the client on the control channel.

    All relevant session information is stored in class attributes
    reproduced below and can be modified before instantiating this
    class.

     - (int) timeout:
       The timeout which is the maximum time a remote client may spend
       between FTP commands. If the timeout triggers, the remote client
       will be kicked off.  Defaults to 300 seconds.

     - (str) banner: the string sent when client connects.

     - (int) max_login_attempts:
        the maximum number of wrong authentications before disconnecting
        the client (default 3).

     - (bool)permit_foreign_addresses:
        FTP site-to-site transfer feature: also referenced as "FXP" it
        permits for transferring a file between two remote FTP servers
        without the transfer going through the client's host (not
        recommended for security reasons as described in RFC-2577).
        Having this attribute set to False means that all data
        connections from/to remote IP addresses which do not match the
        client's IP address will be dropped (defualt False).

     - (bool) permit_privileged_ports:
        set to True if you want to permit active data connections (PORT)
        over privileged ports (not recommended, defaulting to False).

     - (str) masquerade_address:
        the "masqueraded" IP address to provide along PASV reply when
        pyftpdlib is running behind a NAT or other types of gateways.
        When configured pyftpdlib will hide its local address and
        instead use the public address of your NAT (default None).

     - (dict) masquerade_address_map:
        in case the server has multiple IP addresses which are all
        behind a NAT router, you may wish to specify individual
        masquerade_addresses for each of them. The map expects a
        dictionary containing private IP addresses as keys, and their
        corresponding public (masquerade) addresses as values.

     - (list) passive_ports:
        what ports the ftpd will use for its passive data transfers.
        Value expected is a list of integers (e.g. range(60000, 65535)).
        When configured pyftpdlib will no longer use kernel-assigned
        random ports (default None).

     - (bool) use_gmt_times:
        when True causes the server to report all ls and MDTM times in
        GMT and not local time (default True).

     - (bool) tcp_no_delay: controls the use of the TCP_NODELAY socket
        option which disables the Nagle algorithm resulting in
        significantly better performances (default True on all systems
        where it is supported).

    All relevant instance attributes initialized when client connects
    are reproduced below.  You may be interested in them in case you
    want to subclass the original FTPHandler.

     - (bool) authenticated: True if client authenticated himself.
     - (str) username: the name of the connected user (if any).
     - (int) attempted_logins: number of currently attempted logins.
     - (str) current_type: the current transfer type (default "a")
     - (int) af: the connection's address family (IPv4/IPv6)
     - (instance) server: the FTPServer class instance.
     - (instance) data_channel: the data channel instance (if any).
    """
    # these are overridable defaults

    # default classes
    authorizer = DummyAuthorizer()
    active_dtp = ActiveDTP
    passive_dtp = PassiveDTP
    dtp_handler = DTPHandler
    abstracted_fs = AbstractedFS
    proto_cmds = proto_cmds

    # session attributes (explained in the docstring)
    timeout = 300
    banner = "pyftpdlib %s ready." % __ver__
    max_login_attempts = 3
    permit_foreign_addresses = False
    permit_privileged_ports = False
    masquerade_address = None
    masquerade_address_map = {}
    passive_ports = None
    use_gmt_times = True
    tcp_no_delay = hasattr(socket, "TCP_NODELAY")

    def __init__(self, conn, server):
        """Initialize the command channel.

         - (instance) conn: the socket object instance of the newly
            established connection.
         - (instance) server: the ftp server class instance.
        """
        # public session attributes
        self.server = server
        self.fs = None
        self.authenticated = False
        self.username = ""
        self.password = ""
        self.attempted_logins = 0
        self.sleeping = False
        self.data_channel = None
        self.remote_ip = ""
        self.remote_port = ""
        if self.timeout:
            self.idler = CallLater(self.timeout, self.handle_timeout)
        else:
            self.idler = None

        # private session attributes
        self._current_type = 'a'
        self._restart_position = 0
        self._quit_pending = False
        self._af = -1
        self._in_buffer = []
        self._in_buffer_len = 0
        self._epsvall = False
        self._dtp_acceptor = None
        self._dtp_connector = None
        self._in_dtp_queue = None
        self._out_dtp_queue = None
        self._closed = False
        self._extra_feats = []
        self._current_facts = ['type', 'perm', 'size', 'modify']
        self._rnfr = None
        if os.name == 'posix':
            self._current_facts.append('unique')
        self._available_facts = self._current_facts[:]
        if pwd and grp:
            self._available_facts += ['unix.mode', 'unix.uid', 'unix.gid']
        if os.name == 'nt':
            self._available_facts.append('create')

        try:
            asynchat.async_chat.__init__(self, conn)
        except socket.error, err:
            if err[0] == errno.EINVAL:
                # http://code.google.com/p/pyftpdlib/issues/detail?id=143
                return
            self.handle_error()
            return
        self.set_terminator("\r\n")

        # connection properties
        try:
            self.remote_ip, self.remote_port = self.socket.getpeername()[:2]
        except socket.error, err:
            # A race condition  may occur if the other end is closing
            # before we can get the peername, hence ENOTCONN (see issue
            # #100) while EINVAL can occur on OSX (see issue #143).
            self.connected = False
            if err[0] in (errno.ENOTCONN, errno.EINVAL):
                self.close()
            else:
                self.handle_error()
            return

        if hasattr(self.socket, 'family'):
            self._af = self.socket.family
        else:  # python < 2.5
            ip, port = self.socket.getsockname()[:2]
            self._af = socket.getaddrinfo(ip, port, socket.AF_UNSPEC,
                                         socket.SOCK_STREAM)[0][0]

        # try to handle urgent data inline
        try:
            self.socket.setsockopt(socket.SOL_SOCKET, socket.SO_OOBINLINE, 1)
        except socket.error:
            pass

        # disable Nagle algorithm for the control socket only, resulting
        # in significantly better performances
        if self.tcp_no_delay:
            try:
                self.socket.setsockopt(socket.SOL_TCP, socket.TCP_NODELAY, 1)
            except socket.error:
                pass

        # remove this instance from asyncore socket_map
        if not self.connected:
            self.close()

    def handle(self):
        """Return a 220 'ready' response to the client over the command
        channel.
        """
        if len(self.banner) <= 75:
            self.respond("220 %s" % str(self.banner))
        else:
            self.push('220-%s\r\n' % str(self.banner))
            self.respond('220 ')

    def handle_max_cons(self):
        """Called when limit for maximum number of connections is reached."""
        msg = "Too many connections. Service temporary unavailable."
        self.respond("421 %s" % msg)
        self.log(msg)
        # If self.push is used, data could not be sent immediately in
        # which case a new "loop" will occur exposing us to the risk of
        # accepting new connections.  Since this could cause asyncore to
        # run out of fds (...and exposes the server to DoS attacks), we
        # immediately close the channel by using close() instead of
        # close_when_done(). If data has not been sent yet client will
        # be silently disconnected.
        self.close()

    def handle_max_cons_per_ip(self):
        """Called when too many clients are connected from the same IP."""
        msg = "Too many connections from the same IP address."
        self.respond("421 %s" % msg)
        self.log(msg)
        self.close_when_done()

    def handle_timeout(self):
        """Called when client does not send any command within the time
        specified in <timeout> attribute."""
        msg = "Control connection timed out."
        self.log(msg)
        self.respond("421 " + msg)
        self.close_when_done()

    # --- asyncore / asynchat overridden methods

    def readable(self):
        return not self.sleeping and asynchat.async_chat.readable(self)

    def writable(self):
        return not self.sleeping and asynchat.async_chat.writable(self)

    def collect_incoming_data(self, data):
        """Read incoming data and append to the input buffer."""
        self._in_buffer.append(data)
        self._in_buffer_len += len(data)
        # Flush buffer if it gets too long (possible DoS attacks).
        # RFC-959 specifies that a 500 response could be given in
        # such cases
        buflimit = 2048
        if self._in_buffer_len > buflimit:
            self.respond('500 Command too long.')
            self.log('Command received exceeded buffer limit of %s.' % (buflimit))
            self._in_buffer = []
            self._in_buffer_len = 0

    def found_terminator(self):
        r"""Called when the incoming data stream matches the \r\n
        terminator.
        """
        if self.idler is not None and not self.idler.cancelled:
            self.idler.reset()

        line = ''.join(self._in_buffer)
        self._in_buffer = []
        self._in_buffer_len = 0

        cmd = line.split(' ')[0].upper()
        arg = line[len(cmd)+1:]
        if cmd == "SITE" and arg:
            cmd = "SITE %s" % arg.split(' ')[0].upper()
            arg = line[len(cmd)+1:]

        if cmd != 'PASS':
            self.logline("<== %s" % line)
        else:
            self.logline("<== %s %s" % (line.split(' ')[0], '*' * 6))

        # Recognize those commands having a "special semantic". They
        # should be sent by following the RFC-959 procedure of sending
        # Telnet IP/Synch sequence (chr 242 and 255) as OOB data but
        # since many ftp clients don't do it correctly we check the
        # last 4 characters only.
        if not cmd in self.proto_cmds:
            if cmd[-4:] in ('ABOR', 'STAT', 'QUIT'):
                cmd = cmd[-4:]
            else:
                self.respond('500 Command "%s" not understood.' % cmd)
                return

        if not arg and self.proto_cmds[cmd].arg_needed is True:
            self.respond("501 Syntax error: command needs an argument.")
            return
        if arg and self.proto_cmds[cmd].arg_needed is False:
            self.respond("501 Syntax error: command does not accept arguments.")
            return

        if not self.authenticated:
            if self.proto_cmds[cmd].auth_needed or (cmd == 'STAT' and arg):
                self.respond("530 Log in with USER and PASS first.")
            else:
                # call the proper ftp_* method
                self.process_command(cmd, arg)
                return
        else:
            if (cmd == 'STAT') and not arg:
                self.ftp_STAT('')
                return

            # for file-system related commands check whether real path
            # destination is valid
            if self.proto_cmds[cmd].check_path and (cmd != 'STOU'):
                if cmd in ('CWD', 'XCWD'):
                    arg = self.fs.ftp2fs(arg or '/')
                elif cmd in ('CDUP', 'XCUP'):
                    arg = self.fs.ftp2fs('..')
                elif cmd == 'LIST':
                    if arg.lower() in ('-a', '-l', '-al', '-la'):
                        arg = self.fs.ftp2fs(self.fs.cwd)
                    else:
                        arg = self.fs.ftp2fs(arg or self.fs.cwd)
                elif cmd == 'STAT':
                    if glob.has_magic(arg):
                        self.respond('550 Globbing not supported.')
                        return
                    arg = self.fs.ftp2fs(arg or self.fs.cwd)
                else:  # LIST, NLST, MLSD, MLST
                    arg = self.fs.ftp2fs(arg or self.fs.cwd)

                if not self.fs.validpath(arg):
                    line = self.fs.fs2ftp(arg)
                    err = '"%s" points to a path which is outside ' \
                          "the user's root directory" % line
                    self.respond("550 %s." % err)
                    self.log_fs_cmd(cmd, arg, 550, "path escapes home dir")
                    return

            # check permission
            perm = self.proto_cmds[cmd].perm
            if perm is not None and cmd != 'STOU':
                if not self.authorizer.has_perm(self.username, perm, arg):
                    self.log_fs_cmd(cmd, arg, 550, "insufficient privileges")
                    self.respond("550 Can't %s. Not enough privileges." % cmd)
                    return

            # call the proper ftp_* method
            self.process_command(cmd, arg)

    def process_command(self, cmd, *args, **kwargs):
        """Process command by calling the corresponding ftp_* class
        method (e.g. for received command "MKD pathname", ftp_MKD()
        method is called with "pathname" as the argument).
        """
        method = getattr(self, 'ftp_' + cmd.replace(' ', '_'))
        method(*args, **kwargs)

    def handle_expt(self):
        """Called when there is out of band (OOB) data to be read.
        This might happen in case of such clients strictly following
        the RFC-959 directives of sending Telnet IP and Synch as OOB
        data before issuing ABOR, STAT and QUIT commands.
        It should never be called since the SO_OOBINLINE option is
        enabled except on some systems like FreeBSD where it doesn't
        seem to have effect.
        """
        if hasattr(socket, 'MSG_OOB'):
            try:
                data = self.socket.recv(1024, socket.MSG_OOB)
            except socket.error, why:
                if why[0] == errno.EINVAL:
                    return
            else:
                self._in_buffer.append(data)
                return
        self.log("Can't handle OOB data.")
        self.close()

    def handle_error(self):
        try:
            raise
        except (KeyboardInterrupt, SystemExit, asyncore.ExitNow):
            raise
        except socket.error, err:
            # fixes around various bugs:
            # - http://bugs.python.org/issue1736101
            # - http://code.google.com/p/pyftpdlib/issues/detail?id=104
            # - http://code.google.com/p/pyftpdlib/issues/detail?id=109
            if err[0] in (errno.ECONNRESET, errno.ENOTCONN, errno.ESHUTDOWN, \
                          errno.ECONNABORTED, errno.EPIPE, errno.EBADF):
                self.handle_close()
                return
            else:
                logerror(traceback.format_exc())
        except:
            logerror(traceback.format_exc())
        self.close()

    def handle_close(self):
        self.close()

    def close(self):
        """Close the current channel disconnecting the client."""
        if not self._closed:
            self._closed = True
            asynchat.async_chat.close(self)

            self._shutdown_connecting_dtp()

            if self.data_channel is not None:
                self.data_channel.close()
                del self.data_channel

            del self._out_dtp_queue
            del self._in_dtp_queue

            if self.idler is not None and not self.idler.cancelled:
                self.idler.cancel()

            # remove client IP address from ip map
            if self.remote_ip in self.server.ip_map:
                self.server.ip_map.remove(self.remote_ip)

            if self.fs is not None:
                self.fs.cmd_channel = None  # XXX - temporary
            self.log("Disconnected.")

    def _shutdown_connecting_dtp(self):
        """Close any ActiveDTP or PassiveDTP instance waiting to
        establish a connection (passive or active).
        """
        if self._dtp_acceptor is not None:
            self._dtp_acceptor.close()
            self._dtp_acceptor = None
        if self._dtp_connector is not None:
            self._dtp_connector.close()
            self._dtp_connector = None

    # --- public callbacks
    # Note: to run a time consuming task make sure to use a separate
    # process or thread (see FAQs).

    def on_file_sent(self, file):
        """Called every time a file has been succesfully sent.
        "file" is the absolute name of the file just being sent.
        """

    def on_file_received(self, file):
        """Called every time a file has been succesfully received.
        "file" is the absolute name of the file just being received.
        """

    def on_incomplete_file_sent(self, file):
        """Called every time a file has not been entirely sent.
        (e.g. ABOR during transfer or client disconnected).
        "file" is the absolute name of that file.
        """

    def on_incomplete_file_received(self, file):
        """Called every time a file has not been entirely received
        (e.g. ABOR during transfer or client disconnected).
        "file" is the absolute name of that file.
        """

    def on_login(self, username):
        """Called on user login."""

    def on_logout(self, username):
        """Called when user logs out due to QUIT or USER issued twice."""


    # --- internal callbacks

    def _on_dtp_connection(self):
        """Called every time data channel connects, either active or
        passive.

        Incoming and outgoing queues are checked for pending data.
        If outbound data is pending, it is pushed into the data channel.
        If awaiting inbound data, the data channel is enabled for
        receiving.
        """
        # Close accepting DTP only. By closing ActiveDTP DTPHandler
        # would receive a closed socket object.
        #self._shutdown_connecting_dtp()
        if self._dtp_acceptor is not None:
            self._dtp_acceptor.close()
            self._dtp_acceptor = None

        # stop the idle timer as long as the data transfer is not finished
        if self.idler is not None and not self.idler.cancelled:
            self.idler.cancel()

        # check for data to send
        if self._out_dtp_queue is not None:
            data, isproducer, file = self._out_dtp_queue
            self._out_dtp_queue = None
            if file:
                self.data_channel.file_obj = file
            try:
                if not isproducer:
                    self.data_channel.push(data)
                else:
                    self.data_channel.push_with_producer(data)
                if self.data_channel is not None:
                    self.data_channel.close_when_done()
            except:
                # dealing with this exception is up to DTP (see bug #84)
                self.data_channel.handle_error()

        # check for data to receive
        elif self._in_dtp_queue is not None:
            self.data_channel.file_obj = self._in_dtp_queue
            self.data_channel.enable_receiving(self._current_type)
            self._in_dtp_queue = None

    def _on_dtp_close(self):
        """Called every time the data channel is closed."""
        self.data_channel = None
        if self._quit_pending:
            self.close()
        elif self.timeout:
            # data transfer finished, restart the idle timer
            self.idler = CallLater(self.timeout, self.handle_timeout)

    # --- utility

    def respond(self, resp):
        """Send a response to the client using the command channel."""
        self.push(resp + '\r\n')
        self.logline('==> %s' % resp)

    def push_dtp_data(self, data, isproducer=False, file=None):
        """Pushes data into the data channel.

        It is usually called for those commands requiring some data to
        be sent over the data channel (e.g. RETR).
        If data channel does not exist yet, it queues the data to send
        later; data will then be pushed into data channel when
        _on_dtp_connection() will be called.

         - (str/classobj) data: the data to send which may be a string
            or a producer object).
         - (bool) isproducer: whether treat data as a producer.
         - (file) file: the file[-like] object to send (if any).
        """
        if self.data_channel is not None:
            self.respond("125 Data connection already open. Transfer starting.")
            if file:
                self.data_channel.file_obj = file
            try:
                if not isproducer:
                    self.data_channel.push(data)
                else:
                    self.data_channel.push_with_producer(data)
                if self.data_channel is not None:
                    self.data_channel.close_when_done()
            except:
                # dealing with this exception is up to DTP (see bug #84)
                self.data_channel.handle_error()
        else:
            self.respond("150 File status okay. About to open data connection.")
            self._out_dtp_queue = (data, isproducer, file)

    # --- logging wrappers

    def log(self, msg):
        """Log a message, including additional identifying session data."""
        log("[%s]@%s:%s %s" % (self.username, self.remote_ip,
                              self.remote_port, msg))

    def logline(self, msg):
        """Log a line including additional indentifying session data."""
        logline("%s:%s %s" % (self.remote_ip, self.remote_port, msg))

    def log_fs_cmd(self, cmd, path, respcode, respstr):
        """Log all command involving the filesystem (MKD, DELE, etc...)
        in a standardized format.
        """
        outcome = str(respcode)[0] in ("4", "5") and "FAIL" or "OK"
        msg = "%s %s %s %s" % (outcome, cmd, repr(path), respstr)
        self.log(msg)

    def log_transfer(self, receive, filename, completed, elapsed, bytes):
        """Log all transfers (RETR, STOR, STOU) in a standardized format."""
        action = receive and "receiving" or "sending"
        outcome = completed and "completed" or "aborted"
        self.log("Transfer %s (%s) file=%s bytes=%s seconds=%s" \
                 % (outcome, action, repr(filename), bytes, elapsed))

    def flush_account(self):
        """Flush account information by clearing attributes that need
        to be reset on a REIN or new USER command.
        """
        self._shutdown_connecting_dtp()
        # if there's a transfer in progress RFC-959 states we are
        # supposed to let it finish
        if self.data_channel is not None:
            if not self.data_channel.transfer_in_progress():
                self.data_channel.close()
                self.data_channel = None

        username = self.username
        self.authenticated = False
        self.username = ""
        self.password = ""
        self.attempted_logins = 0
        self._current_type = 'a'
        self._restart_position = 0
        self._quit_pending = False
        self.sleeping = False
        self._in_dtp_queue = None
        self._rnfr = None
        self._out_dtp_queue = None
        if username:
            self.on_logout(username)

    def run_as_current_user(self, function, *args, **kwargs):
        """Execute a function impersonating the current logged-in user."""
        self.authorizer.impersonate_user(self.username, self.password)
        try:
            return function(*args, **kwargs)
        finally:
            self.authorizer.terminate_impersonation(self.username)

    # --- connection

    def _make_eport(self, ip, port):
        """Establish an active data channel with remote client which
        issued a PORT or EPRT command.
        """
        # FTP bounce attacks protection: according to RFC-2577 it's
        # recommended to reject PORT if IP address specified in it
        # does not match client IP address.
        remote_ip = self.remote_ip
        if remote_ip.startswith('::ffff:'):
            # In this scenario, the server has an IPv6 socket, but
            # the remote client is using IPv4 and its address is
            # represented as an IPv4-mapped IPv6 address which
            # looks like this ::ffff:151.12.5.65, see:
            # http://en.wikipedia.org/wiki/IPv6#IPv4-mapped_addresses
            # http://tools.ietf.org/html/rfc3493.html#section-3.7
            # We truncate the first bytes to make it look like a
            # common IPv4 address.
            remote_ip = remote_ip[7:]
        if not self.permit_foreign_addresses and ip != remote_ip:
            self.log("Rejected data connection to foreign address %s:%s."
                     % (ip, port))
            self.respond("501 Can't connect to a foreign address.")
            return

        # ...another RFC-2577 recommendation is rejecting connections
        # to privileged ports (< 1024) for security reasons.
        if not self.permit_privileged_ports and port < 1024:
            self.log('PORT against the privileged port "%s" refused.' % port)
            self.respond("501 Can't connect over a privileged port.")
            return

        # close establishing DTP instances, if any
        self._shutdown_connecting_dtp()

        if self.data_channel is not None:
            self.data_channel.close()
            self.data_channel = None

        # make sure we are not hitting the max connections limit
        if self.server.max_cons and len(self._map) >= self.server.max_cons:
            msg = "Too many connections. Can't open data channel."
            self.respond("425 %s" %msg)
            self.log(msg)
            return

        # open data channel
        self._dtp_connector = self.active_dtp(ip, port, self)

    def _make_epasv(self, extmode=False):
        """Initialize a passive data channel with remote client which
        issued a PASV or EPSV command.
        If extmode argument is True we assume that client issued EPSV in
        which case extended passive mode will be used (see RFC-2428).
        """
        # close establishing DTP instances, if any
        self._shutdown_connecting_dtp()

        # close established data connections, if any
        if self.data_channel is not None:
            self.data_channel.close()
            self.data_channel = None

        # make sure we are not hitting the max connections limit
        if self.server.max_cons and len(self._map) >= self.server.max_cons:
            msg = "Too many connections. Can't open data channel."
            self.respond("425 %s" %msg)
            self.log(msg)
            return

        # open data channel
        self._dtp_acceptor = self.passive_dtp(self, extmode)

    def ftp_PORT(self, line):
        """Start an active data channel by using IPv4."""
        if self._epsvall:
            self.respond("501 PORT not allowed after EPSV ALL.")
            return
        # Parse PORT request for getting IP and PORT.
        # Request comes in as:
        # > h1,h2,h3,h4,p1,p2
        # ...where the client's IP address is h1.h2.h3.h4 and the TCP
        # port number is (p1 * 256) + p2.
        try:
            addr = map(int, line.split(','))
            if len(addr) != 6:
                raise ValueError
            for x in addr[:4]:
                if not 0 <= x <= 255:
                    raise ValueError
            ip = '%d.%d.%d.%d' % tuple(addr[:4])
            port = (addr[4] * 256) + addr[5]
            if not 0 <= port <= 65535:
                raise ValueError
        except (ValueError, OverflowError):
            self.respond("501 Invalid PORT format.")
            return
        self._make_eport(ip, port)

    def ftp_EPRT(self, line):
        """Start an active data channel by choosing the network protocol
        to use (IPv4/IPv6) as defined in RFC-2428.
        """
        if self._epsvall:
            self.respond("501 EPRT not allowed after EPSV ALL.")
            return
        # Parse EPRT request for getting protocol, IP and PORT.
        # Request comes in as:
        # <d>proto<d>ip<d>port<d>
        # ...where <d> is an arbitrary delimiter character (usually "|") and
        # <proto> is the network protocol to use (1 for IPv4, 2 for IPv6).
        try:
            af, ip, port = line.split(line[0])[1:-1]
            port = int(port)
            if not 0 <= port <= 65535:
                raise ValueError
        except (ValueError, IndexError, OverflowError):
            self.respond("501 Invalid EPRT format.")
            return

        if af == "1":
            if self._af != socket.AF_INET:
                self.respond('522 Network protocol not supported (use 2).')
            else:
                try:
                    octs = map(int, ip.split('.'))
                    if len(octs) != 4:
                        raise ValueError
                    for x in octs:
                        if not 0 <= x <= 255:
                            raise ValueError
                except (ValueError, OverflowError):
                    self.respond("501 Invalid EPRT format.")
                else:
                    self._make_eport(ip, port)
        elif af == "2":
            if self._af == socket.AF_INET:
                self.respond('522 Network protocol not supported (use 1).')
            else:
                self._make_eport(ip, port)
        else:
            if self._af == socket.AF_INET:
                self.respond('501 Unknown network protocol (use 1).')
            else:
                self.respond('501 Unknown network protocol (use 2).')

    def ftp_PASV(self, line):
        """Start a passive data channel by using IPv4."""
        if self._epsvall:
            self.respond("501 PASV not allowed after EPSV ALL.")
            return
        self._make_epasv(extmode=False)

    def ftp_EPSV(self, line):
        """Start a passive data channel by using IPv4 or IPv6 as defined
        in RFC-2428.
        """
        # RFC-2428 specifies that if an optional parameter is given,
        # we have to determine the address family from that otherwise
        # use the same address family used on the control connection.
        # In such a scenario a client may use IPv4 on the control channel
        # and choose to use IPv6 for the data channel.
        # But how could we use IPv6 on the data channel without knowing
        # which IPv6 address to use for binding the socket?
        # Unfortunately RFC-2428 does not provide satisfing information
        # on how to do that.  The assumption is that we don't have any way
        # to know wich address to use, hence we just use the same address
        # family used on the control connection.
        if not line:
            self._make_epasv(extmode=True)
        # IPv4
        elif line == "1":
            if self._af != socket.AF_INET:
                self.respond('522 Network protocol not supported (use 2).')
            else:
                self._make_epasv(extmode=True)
        # IPv6
        elif line == "2":
            if self._af == socket.AF_INET:
                self.respond('522 Network protocol not supported (use 1).')
            else:
                self._make_epasv(extmode=True)
        elif line.lower() == 'all':
            self._epsvall = True
            self.respond('220 Other commands other than EPSV are now disabled.')
        else:
            if self._af == socket.AF_INET:
                self.respond('501 Unknown network protocol (use 1).')
            else:
                self.respond('501 Unknown network protocol (use 2).')

    def ftp_QUIT(self, line):
        """Quit the current session disconnecting the client."""
        if self.authenticated:
            msg_quit = self.authorizer.get_msg_quit(self.username)
        else:
            msg_quit = "Goodbye."
        if len(msg_quit) <= 75:
            self.respond("221 %s" % msg_quit)
        else:
            self.push("221-%s\r\n" % msg_quit)
            self.respond("221 ")

        # From RFC-959:
        # If file transfer is in progress, the connection must remain
        # open for result response and the server will then close it.
        # We also stop responding to any further command.
        if self.data_channel:
            self._quit_pending = True
            self.sleeping = True
        else:
            self._shutdown_connecting_dtp()
            self.close_when_done()
        if self.username:
            self.on_logout(self.username)

        # --- data transferring

    def ftp_LIST(self, path):
        """Return a list of files in the specified directory to the
        client.
        """
        # - If no argument, fall back on cwd as default.
        # - Some older FTP clients erroneously issue /bin/ls-like LIST
        #   formats in which case we fall back on cwd as default.
        line = self.fs.fs2ftp(path)
        try:
            iterator = self.run_as_current_user(self.fs.get_list_dir, path)
        except OSError, err:
            why = _strerror(err)
            self.log_fs_cmd("LIST", path, 550, why)
            self.respond('550 %s.' % why)
        else:
            self.log_fs_cmd("LIST", path, 125, "Transfer starting")
            producer = BufferedIteratorProducer(iterator)
            self.push_dtp_data(producer, isproducer=True)

    def ftp_NLST(self, path):
        """Return a list of files in the specified directory in a
        compact form to the client.
        """
        line = self.fs.fs2ftp(path)
        try:
            if self.fs.isdir(path):
                listing = self.run_as_current_user(self.fs.listdir, path)
            else:
                # if path is a file we just list its name
                self.fs.lstat(path)  # raise exc in case of problems
                listing = [os.path.basename(path)]
        except OSError, err:
            why = _strerror(err)
            self.log_fs_cmd("NLST", path, 550, why)
            self.respond('550 %s.' %why)
        else:
            data = ''
            if listing:
                listing.sort()
                data = '\r\n'.join(listing) + '\r\n'
            self.log_fs_cmd("NLST", path, 125, "Transfer starting")
            self.push_dtp_data(data)

        # --- MLST and MLSD commands

    # The MLST and MLSD commands are intended to standardize the file and
    # directory information returned by the server-FTP process.  These
    # commands differ from the LIST command in that the format of the
    # replies is strictly defined although extensible.

    def ftp_MLST(self, path):
        """Return information about a pathname in a machine-processable
        form as defined in RFC-3659.
        """
        line = self.fs.fs2ftp(path)
        basedir, basename = os.path.split(path)
        perms = self.authorizer.get_perms(self.username)
        try:
            iterator = self.run_as_current_user(self.fs.format_mlsx, basedir,
                       [basename], perms, self._current_facts, ignore_err=False)
            data = ''.join(iterator)
        except OSError, err:
            why = _strerror(err)
            self.log_fs_cmd("MLST", path, 550, why)
            self.respond('550 %s.' %why)
        else:
            # since TVFS is supported (see RFC-3659 chapter 6), a fully
            # qualified pathname should be returned
            data = data.split(' ')[0] + ' %s\r\n' % line
            # response is expected on the command channel
            self.push('250-Listing "%s":\r\n' % line)
            # the fact set must be preceded by a space
            self.push(' ' + data)
            self.respond('250 End MLST.')
            self.log_fs_cmd("MLST", path, 250, "File listed")

    def ftp_MLSD(self, path):
        """Return contents of a directory in a machine-processable form
        as defined in RFC-3659.
        """
        line = self.fs.fs2ftp(path)
        # RFC-3659 requires 501 response code if path is not a directory
        if not self.fs.isdir(path):
            err = 'No such directory'
            self.log_fs_cmd('MLSD', path, 501, err)
            self.respond("501 %s." %err)
            return
        try:
            listing = self.run_as_current_user(self.fs.listdir, path)
        except OSError, err:
            why = _strerror(err)
            self.log_fs_cmd("MLSD", path, 550, why)
            self.respond('550 %s.' %why)
        else:
            perms = self.authorizer.get_perms(self.username)
            iterator = self.fs.format_mlsx(path, listing, perms,
                       self._current_facts)
            producer = BufferedIteratorProducer(iterator)
            self.log_fs_cmd("MLSD", path, 125, "Transfer starting")
            self.push_dtp_data(producer, isproducer=True)

    def ftp_RETR(self, file):
        """Retrieve the specified file (transfer from the server to the
        client)
        """
        line = self.fs.fs2ftp(file)
        rest_pos = self._restart_position
        self._restart_position = 0
        try:
            fd = self.run_as_current_user(self.fs.open, file, 'rb')
        except IOError, err:
            why = _strerror(err)
            self.log_fs_cmd("RETR", file, 550, why)
            self.respond('550 %s.' %why)
            return

        if rest_pos:
            # Make sure that the requested offset is valid (within the
            # size of the file being resumed).
            # According to RFC-1123 a 554 reply may result in case that
            # the existing file cannot be repositioned as specified in
            # the REST.
            ok = 0
            try:
                if rest_pos > self.fs.getsize(file):
                    raise ValueError
                fd.seek(rest_pos)
                ok = 1
            except ValueError:
                why = "Invalid REST parameter"
            except IOError, err:
                why = _strerror(err)
            if not ok:
                self.respond('554 %s' %why)
                self.log_fs_cmd("RETR", file, 554, why)
                return
        producer = FileProducer(fd, self._current_type)
        self.push_dtp_data(producer, isproducer=True, file=fd)

    def ftp_STOR(self, file, mode='w'):
        """Store a file (transfer from the client to the server)."""
        # A resume could occur in case of APPE or REST commands.
        # In that case we have to open file object in different ways:
        # STOR: mode = 'w'
        # APPE: mode = 'a'
        # REST: mode = 'r+' (to permit seeking on file object)
        if 'a' in mode:
            cmd = 'APPE'
        else:
            cmd = 'STOR'
        line = self.fs.fs2ftp(file)
        rest_pos = self._restart_position
        self._restart_position = 0
        if rest_pos:
            mode = 'r+'
        try:
            fd = self.run_as_current_user(self.fs.open, file, mode + 'b')
        except IOError, err:
            why = _strerror(err)
            self.log_fs_cmd(cmd, file, 550, why)
            self.respond('550 %s.' %why)
            return

        if rest_pos:
            # Make sure that the requested offset is valid (within the
            # size of the file being resumed).
            # According to RFC-1123 a 554 reply may result in case
            # that the existing file cannot be repositioned as
            # specified in the REST.
            ok = 0
            try:
                if rest_pos > self.fs.getsize(file):
                    raise ValueError
                fd.seek(rest_pos)
                ok = 1
            except ValueError:
                why = "Invalid REST parameter"
            except IOError, err:
                why = _strerror(err)
            if not ok:
                self.log_fs_cmd(cmd, file, 554, why)
                self.respond('554 %s' %why)
                return

        if self.data_channel is not None:
            resp = "Data connection already open. Transfer starting."
            self.respond("125" + resp)
            self.data_channel.file_obj = fd
            self.data_channel.enable_receiving(self._current_type)
        else:
            resp = "File status okay. About to open data connection."
            self.respond("150 " + resp)
            self._in_dtp_queue = fd


    def ftp_STOU(self, line):
        """Store a file on the server with a unique name."""
        # Note 1: RFC-959 prohibited STOU parameters, but this
        # prohibition is obsolete.
        # Note 2: 250 response wanted by RFC-959 has been declared
        # incorrect in RFC-1123 that wants 125/150 instead.
        # Note 3: RFC-1123 also provided an exact output format
        # defined to be as follow:
        # > 125 FILE: pppp
        # ...where pppp represents the unique path name of the
        # file that will be written.

        # watch for STOU preceded by REST, which makes no sense.
        if self._restart_position:
            self.respond("450 Can't STOU while REST request is pending.")
            return

        if line:
            basedir, prefix = os.path.split(self.fs.ftp2fs(line))
            prefix = prefix + '.'
        else:
            basedir = self.fs.ftp2fs(self.fs.cwd)
            prefix = 'ftpd.'
        try:
            fd = self.run_as_current_user(self.fs.mkstemp, prefix=prefix,
                                          dir=basedir)
        except IOError, err:
            # hitted the max number of tries to find out file with
            # unique name
            if err.errno == errno.EEXIST:
                why = 'No usable unique file name found'
            # something else happened
            else:
                why = _strerror(err)
            self.respond("450 %s." % why)
            self.log_fs_cmd("STOU", self.fs.ftpnorm(line), 450, why)
            return

        if not self.authorizer.has_perm(self.username, 'w', fd.name):
            try:
                fd.close()
                self.run_as_current_user(self.fs.remove, fd.name)
            except os.error:
                pass
            self.log_fs_cmd("STOU", fd.name, 450, "not enough privileges")
            self.respond("550 Can't STOU: not enough privileges.")
            return

        # now just acts like STOR except that restarting isn't allowed
        filename = os.path.basename(fd.name)
        if self.data_channel is not None:
            self.respond("125 FILE: %s" % filename)
            self.data_channel.file_obj = fd
            self.data_channel.enable_receiving(self._current_type)
        else:
            self.respond("150 FILE: %s" % filename)
            self._in_dtp_queue = fd

    def ftp_APPE(self, file):
        """Append data to an existing file on the server."""
        # watch for APPE preceded by REST, which makes no sense.
        if self._restart_position:
            self.respond("450 Can't APPE while REST request is pending.")
        else:
            self.ftp_STOR(file, mode='a')

    def ftp_REST(self, line):
        """Restart a file transfer from a previous mark."""
        if self._current_type == 'a':
            self.respond('501 Resuming transfers not allowed in ASCII mode.')
            return
        try:
            marker = int(line)
            if marker < 0:
                raise ValueError
        except (ValueError, OverflowError):
            self.respond("501 Invalid parameter.")
        else:
            self.respond("350 Restarting at position %s." % marker)
            self._restart_position = marker

    def ftp_ABOR(self, line):
        """Abort the current data transfer."""
        # ABOR received while no data channel exists
        if (self._dtp_acceptor is None) and (self._dtp_connector is None) \
        and (self.data_channel is None):
            self.respond("225 No transfer to abort.")
            return
        else:
            # a PASV or PORT was received but connection wasn't made yet
            if self._dtp_acceptor is not None or self._dtp_connector is not None:
                self._shutdown_connecting_dtp()
                resp = "225 ABOR command successful; data channel closed."

            # If a data transfer is in progress the server must first
            # close the data connection, returning a 426 reply to
            # indicate that the transfer terminated abnormally, then it
            # must send a 226 reply, indicating that the abort command
            # was successfully processed.
            # If no data has been transmitted we just respond with 225
            # indicating that no transfer was in progress.
            if self.data_channel is not None:
                if self.data_channel.transfer_in_progress():
                    self.data_channel.close()
                    self.data_channel = None
                    self.respond("426 Connection closed; transfer aborted.")
                    self.log("OK ABOR. Transfer aborted, data channel closed.")
                    resp = "226 ABOR command successful."
                else:
                    self.data_channel.close()
                    self.data_channel = None
                    self.log("OK ABOR. Data channel closed.")
                    resp = "225 ABOR command successful; data channel closed."
        self.respond(resp)


        # --- authentication

    def ftp_USER(self, line):
        """Set the username for the current session."""
        # RFC-959 specifies a 530 response to the USER command if the
        # username is not valid.  If the username is valid is required
        # ftpd returns a 331 response instead.  In order to prevent a
        # malicious client from determining valid usernames on a server,
        # it is suggested by RFC-2577 that a server always return 331 to
        # the USER command and then reject the combination of username
        # and password for an invalid username when PASS is provided later.
        if not self.authenticated:
            self.respond('331 Username ok, send password.')
        else:
            # a new USER command could be entered at any point in order
            # to change the access control flushing any user, password,
            # and account information already supplied and beginning the
            # login sequence again.
            self.flush_account()
            msg = 'Previous account information was flushed'
            self.log(msg)
            self.respond('331 %s, send password.' % msg)
        self.username = line

    _auth_failed_timeout = 5

    def ftp_PASS(self, line):
        """Check username's password against the authorizer."""
        if self.authenticated:
            self.respond("503 User already authenticated.")
            return
        if not self.username:
            self.respond("503 Login with USER first.")
            return

        def auth_failed(msg="Authentication failed."):
            self.sleeping = False
            if hasattr(self, '_closed') and not self._closed:
                self.attempted_logins += 1
                if self.attempted_logins >= self.max_login_attempts:
                    msg = "530 " + msg + " Disconnecting."
                    self.respond(msg)
                    self.log(msg)
                    self.close_when_done()
                else:
                    self.respond("530 " + msg)
                    self.log(msg)

        if self.authorizer.validate_authentication(self.username, line):
            msg_login = self.authorizer.get_msg_login(self.username)
            if len(msg_login) <= 75:
                self.respond('230 %s' % msg_login)
            else:
                self.push("230-%s\r\n" % msg_login)
                self.respond("230 ")
            self.authenticated = True
            self.password = line
            self.attempted_logins = 0

            home = self.authorizer.get_home_dir(self.username)
            self.fs = self.abstracted_fs(home, self)
            self.log("User %s logged in." % repr(self.username))
            self.on_login(self.username)
        else:
            self.username = ""
            self.sleeping = True
            if self.username == 'anonymous':
                CallLater(self._auth_failed_timeout, auth_failed,
                          "Anonymous access not allowed.")
            else:
                CallLater(self._auth_failed_timeout, auth_failed)

    def ftp_REIN(self, line):
        """Reinitialize user's current session."""
        # From RFC-959:
        # REIN command terminates a USER, flushing all I/O and account
        # information, except to allow any transfer in progress to be
        # completed.  All parameters are reset to the default settings
        # and the control connection is left open.  This is identical
        # to the state in which a user finds himself immediately after
        # the control connection is opened.
        self.log("Flushing account information.")
        self.flush_account()
        # Note: RFC-959 erroneously mention "220" as the correct response
        # code to be given in this case, but this is wrong...
        self.respond("230 Ready for new user.")


        # --- filesystem operations

    def ftp_PWD(self, line):
        """Return the name of the current working directory to the client."""
        # The 257 response is supposed to include the directory
        # name and in case it contains embedded double-quotes
        # they must be doubled (see RFC-959, chapter 7, appendix 2).
        self.respond('257 "%s" is the current directory.'
                     % self.fs.cwd.replace('"', '""'))

    def ftp_CWD(self, path):
        """Change the current working directory."""
        line = self.fs.fs2ftp(path)
        try:
            self.run_as_current_user(self.fs.chdir, path)
        except OSError, err:
            why = _strerror(err)
            self.log_fs_cmd("CWD", path, 550, why)
            self.respond('550 %s.' % why)
        else:
            self.log_fs_cmd("CWD", path, 250, "Directory changed")
            self.respond('250 "%s" is the current directory.' % self.fs.cwd)

    def ftp_CDUP(self, path):
        """Change into the parent directory."""
        # Note: RFC-959 says that code 200 is required but it also says
        # that CDUP uses the same codes as CWD.
        self.ftp_CWD(path)

    def ftp_SIZE(self, path):
        """Return size of file in a format suitable for using with
        RESTart as defined in RFC-3659."""

        # Implementation note: properly handling the SIZE command when
        # TYPE ASCII is used would require to scan the entire file to
        # perform the ASCII translation logic
        # (file.read().replace(os.linesep, '\r\n')) and then calculating
        # the len of such data which may be different than the actual
        # size of the file on the server.  Considering that calculating
        # such result could be very resource-intensive and also dangerous
        # (DoS) we reject SIZE when the current TYPE is ASCII.
        # However, clients in general should not be resuming downloads
        # in ASCII mode.  Resuming downloads in binary mode is the
        # recommended way as specified in RFC-3659.

        line = self.fs.fs2ftp(path)
        if self._current_type == 'a':
            why = "SIZE not allowed in ASCII mode"
            self.log_fs_cmd("SIZE", path, 550, why)
            self.respond("550 %s." %why)
            return
        if not self.fs.isfile(self.fs.realpath(path)):
            why = "%s is not retrievable" % line
            self.log_fs_cmd("SIZE", path, 550, why)
            self.respond("550 %s." % why)
            return
        try:
            size = self.run_as_current_user(self.fs.getsize, path)
        except OSError, err:
            why = _strerror(err)
            self.log_fs_cmd("SIZE", path, 550, why)
            self.respond('550 %s.' % why)
        else:
            self.respond("213 %s" % size)
            self.log_fs_cmd("SIZE", path, 213, "Size retrieved")

    def ftp_MDTM(self, path):
        """Return last modification time of file to the client as an ISO
        3307 style timestamp (YYYYMMDDHHMMSS) as defined in RFC-3659.
        """
        line = self.fs.fs2ftp(path)
        if not self.fs.isfile(self.fs.realpath(path)):
            self.log_fs_cmd('MDTM', path, 550, "Not a file")
            self.respond("550 %s is not retrievable" % line)
            return
        if self.use_gmt_times:
            timefunc = time.gmtime
        else:
            timefunc = time.localtime
        try:
            secs = self.run_as_current_user(self.fs.getmtime, path)
            lmt = time.strftime("%Y%m%d%H%M%S", timefunc(secs))
        except (OSError, ValueError), err:
            if isinstance(err, OSError):
                why = _strerror(err)
            else:
                # It could happen if file's last modification time
                # happens to be too old (prior to year 1900)
                why = "Can't determine file's last modification time"
            self.log_fs_cmd('MDTM', path, 550, why)
            self.respond('550 %s.' % why)
        else:
            self.respond("213 %s" % lmt)
            self.log_fs_cmd('MDTM', path, 213, "Modification time retrieved")

    def ftp_MKD(self, path):
        """Create the specified directory."""
        line = self.fs.fs2ftp(path)
        try:
            self.run_as_current_user(self.fs.mkdir, path)
        except OSError, err:
            why = _strerror(err)
            self.log_fs_cmd('MKD', path, 550, why)
            self.respond('550 %s.' %why)
        else:
            self.log_fs_cmd('MKD', path, 257, "Directory created")
            # The 257 response is supposed to include the directory
            # name and in case it contains embedded double-quotes
            # they must be doubled (see RFC-959, chapter 7, appendix 2).
            self.respond('257 "%s" directory created.' % line.replace('"', '""'))

    def ftp_RMD(self, path):
        """Remove the specified directory."""
        line = self.fs.fs2ftp(path)
        if self.fs.realpath(path) == self.fs.realpath(self.fs.root):
            msg = "Can't remove root directory."
            self.respond("550 %s" % msg)
            self.log_fs_cmd('RMD', path, 550, msg)
            return
        try:
            self.run_as_current_user(self.fs.rmdir, path)
        except OSError, err:
            why = _strerror(err)
            self.log_fs_cmd('RMD', path, 550, why)
            self.respond('550 %s.' % why)
        else:
            self.log_fs_cmd('RMD', path, 250, "Directory removed")
            self.respond("250 Directory removed.")

    def ftp_DELE(self, path):
        """Delete the specified file."""
        line = self.fs.fs2ftp(path)
        try:
            self.run_as_current_user(self.fs.remove, path)
        except OSError, err:
            why = _strerror(err)
            self.log_fs_cmd('DELE', path, 550, why)
            self.respond('550 %s.' % why)
        else:
            self.log_fs_cmd('DELE', path, 250, "File removed")
            self.respond("250 File removed.")

    def ftp_RNFR(self, path):
        """Rename the specified (only the source name is specified
        here, see RNTO command)"""
        if not self.fs.lexists(path):
            self.log_fs_cmd('RNFR', path, 550, "No such file")
            self.respond("550 No such file or directory.")
        elif self.fs.realpath(path) == self.fs.realpath(self.fs.root):
            self.log_fs_cmd('RNFR', path, 550, "Can't rename home dir")
            self.respond("550 Can't rename the home directory.")
        else:
            self._rnfr = path
            self.log_fs_cmd('RNFR', path, 350, "Ready for destination name")
            self.respond("350 Ready for destination name.")

    def ftp_RNTO(self, path):
        """Rename file (destination name only, source is specified with
        RNFR).
        """
        if not self._rnfr:
            self.respond("503 Bad sequence of commands: use RNFR first.")
            return
        src = self._rnfr
        self._rnfr = None
        try:
            self.run_as_current_user(self.fs.rename, src, path)
        except OSError, err:
            why = _strerror(err)
            self.log_fs_cmd('RNTO', path, 550, why)
            self.respond('550 %s.' % why)
        else:
            self.log_fs_cmd('RNTO', path, 250, "Path renamed")
            self.respond("250 Renaming ok.")


        # --- others

    def ftp_TYPE(self, line):
        """Set current type data type to binary/ascii"""
        type = line.upper().replace(' ', '')
        if type in ("A", "L7"):
            self.respond("200 Type set to: ASCII.")
            self._current_type = 'a'
        elif type in ("I", "L8"):
            self.respond("200 Type set to: Binary.")
            self._current_type = 'i'
        else:
            self.respond('504 Unsupported type "%s".' % line)

    def ftp_STRU(self, line):
        """Set file structure ("F" is the only one supported (noop))."""
        stru = line.upper()
        if stru == 'F':
            self.respond('200 File transfer structure set to: F.')
        elif stru in ('P', 'R'):
           # R is required in minimum implementations by RFC-959, 5.1.
           # RFC-1123, 4.1.2.13, amends this to only apply to servers
           # whose file systems support record structures, but also
           # suggests that such a server "may still accept files with
           # STRU R, recording the byte stream literally".
           # Should we accept R but with no operational difference from
           # F? proftpd and wu-ftpd don't accept STRU R. We just do
           # the same.
           #
           # RFC-1123 recommends against implementing P.
            self.respond('504 Unimplemented STRU type.')
        else:
            self.respond('501 Unrecognized STRU type.')

    def ftp_MODE(self, line):
        """Set data transfer mode ("S" is the only one supported (noop))."""
        mode = line.upper()
        if mode == 'S':
            self.respond('200 Transfer mode set to: S')
        elif mode in ('B', 'C'):
            self.respond('504 Unimplemented MODE type.')
        else:
            self.respond('501 Unrecognized MODE type.')

    def ftp_STAT(self, path):
        """Return statistics about current ftp session. If an argument
        is provided return directory listing over command channel.

        Implementation note:

        RFC-959 does not explicitly mention globbing but many FTP
        servers do support it as a measure of convenience for FTP
        clients and users.

        In order to search for and match the given globbing expression,
        the code has to search (possibly) many directories, examine
        each contained filename, and build a list of matching files in
        memory.  Since this operation can be quite intensive, both CPU-
        and memory-wise, we do not support globbing.
        """
        # return STATus information about ftpd
        if not path:
            s = []
            s.append('Connected to: %s:%s' % self.socket.getsockname()[:2])
            if self.authenticated:
                s.append('Logged in as: %s' % self.username)
            else:
                if not self.username:
                    s.append("Waiting for username.")
                else:
                    s.append("Waiting for password.")
            if self._current_type == 'a':
                type = 'ASCII'
            else:
                type = 'Binary'
            s.append("TYPE: %s; STRUcture: File; MODE: Stream" % type)
            if self._dtp_acceptor is not None:
                s.append('Passive data channel waiting for connection.')
            elif self.data_channel is not None:
                bytes_sent = self.data_channel.tot_bytes_sent
                bytes_recv = self.data_channel.tot_bytes_received
                elapsed_time = self.data_channel.get_elapsed_time()
                s.append('Data connection open:')
                s.append('Total bytes sent: %s' % bytes_sent)
                s.append('Total bytes received: %s' % bytes_recv)
                s.append('Transfer elapsed time: %s secs' % elapsed_time)
            else:
                s.append('Data connection closed.')

            self.push('211-FTP server status:\r\n')
            self.push(''.join([' %s\r\n' % item for item in s]))
            self.respond('211 End of status.')
        # return directory LISTing over the command channel
        else:
            line = self.fs.fs2ftp(path)
            try:
                iterator = self.run_as_current_user(self.fs.get_list_dir, path)
            except OSError, err:
                why = _strerror(err)
                self.log_fs_cmd('STAT', path, 550, why)
                self.respond('550 %s.' %why)
            else:
                self.log_fs_cmd('STAT', path, 213, "Directory listed")
                self.push('213-Status of "%s":\r\n' % line)
                self.push_with_producer(BufferedIteratorProducer(iterator))
                self.respond('213 End of status.')

    def ftp_FEAT(self, line):
        """List all new features supported as defined in RFC-2398."""
        features = ['EPRT','EPSV','MDTM','MLSD','REST STREAM','SIZE','TVFS']
        features.extend(self._extra_feats)
        s = ''
        for fact in self._available_facts:
            if fact in self._current_facts:
                s += fact + '*;'
            else:
                s += fact + ';'
        features.append('MLST ' + s)
        features.sort()
        self.push("211-Features supported:\r\n")
        self.push("".join([" %s\r\n" % x for x in features]))

        self.respond('211 End FEAT.')

    def ftp_OPTS(self, line):
        """Specify options for FTP commands as specified in RFC-2389."""
        try:
            if line.count(' ') > 1:
                raise ValueError('Invalid number of arguments')
            if ' ' in line:
                cmd, arg = line.split(' ')
                if ';' not in arg:
                    raise ValueError('Invalid argument')
            else:
                cmd, arg = line, ''
            # actually the only command able to accept options is MLST
            if cmd.upper() != 'MLST':
                raise ValueError('Unsupported command "%s"' % cmd)
        except ValueError, err:
            self.respond('501 %s.' % err)
        else:
            facts = [x.lower() for x in arg.split(';')]
            self._current_facts = [x for x in facts if x in self._available_facts]
            f = ''.join([x + ';' for x in self._current_facts])
            self.respond('200 MLST OPTS ' + f)

    def ftp_NOOP(self, line):
        """Do nothing."""
        self.respond("200 I successfully done nothin'.")

    def ftp_SYST(self, line):
        """Return system type (always returns UNIX type: L8)."""
        # This command is used to find out the type of operating system
        # at the server.  The reply shall have as its first word one of
        # the system names listed in RFC-943.
        # Since that we always return a "/bin/ls -lA"-like output on
        # LIST we  prefer to respond as if we would on Unix in any case.
        self.respond("215 UNIX Type: L8")

    def ftp_ALLO(self, line):
        """Allocate bytes for storage (noop)."""
        # not necessary (always respond with 202)
        self.respond("202 No storage allocation necessary.")

    def ftp_HELP(self, line):
        """Return help text to the client."""
        if line:
            line = line.upper()
            if line in self.proto_cmds:
                self.respond("214 %s" % self.proto_cmds[line].help)
            else:
                self.respond("501 Unrecognized command.")
        else:
            # provide a compact list of recognized commands
            def formatted_help():
                cmds = []
                keys = [x for x in self.proto_cmds.keys() if not x.startswith('SITE ')]
                keys.sort()
                while keys:
                    elems = tuple((keys[0:8]))
                    cmds.append(' %-6s' * len(elems) % elems + '\r\n')
                    del keys[0:8]
                return ''.join(cmds)

            self.push("214-The following commands are recognized:\r\n")
            self.push(formatted_help())
            self.respond("214 Help command successful.")

        # --- site commands

    # No SITE commands aside from SITE HELP are implemented by default.
    # The user willing to add support for a specific SITE command must
    # update self.proto_cmds dictionary and define a new ftp_SITE_%CMD%
    # method in the subclass.

    def ftp_SITE_HELP(self, line):
        """Return help text to the client for a given SITE command."""
        if line:
            line = line.upper()
            if line in self.proto_cmds:
                self.respond("214 %s" % self.proto_cmds[line].help)
            else:
                self.respond("501 Unrecognized SITE command.")
        else:
            self.push("214-The following SITE commands are recognized:\r\n")
            site_cmds = []
            keys = self.proto_cmds.keys()
            keys.sort()
            for cmd in keys:
                if cmd.startswith('SITE '):
                    site_cmds.append(' %s\r\n' % cmd[5:])
            self.push(''.join(site_cmds))
            self.respond("214 Help SITE command successful.")

        # --- support for deprecated cmds

    # RFC-1123 requires that the server treat XCUP, XCWD, XMKD, XPWD
    # and XRMD commands as synonyms for CDUP, CWD, MKD, LIST and RMD.
    # Such commands are obsoleted but some ftp clients (e.g. Windows
    # ftp.exe) still use them.

    def ftp_XCUP(self, line):
        """Change to the parent directory. Synonym for CDUP. Deprecated."""
        self.ftp_CDUP(line)

    def ftp_XCWD(self, line):
        """Change the current working directory. Synonym for CWD. Deprecated."""
        self.ftp_CWD(line)

    def ftp_XMKD(self, line):
        """Create the specified directory. Synonym for MKD. Deprecated."""
        self.ftp_MKD(line)

    def ftp_XPWD(self, line):
        """Return the current working directory. Synonym for PWD. Deprecated."""
        self.ftp_PWD(line)

    def ftp_XRMD(self, line):
        """Remove the specified directory. Synonym for RMD. Deprecated."""
        self.ftp_RMD(line)


class FTPServer(object, asyncore.dispatcher):
    """This class is an asyncore.disptacher subclass.  It creates a FTP
    socket listening on <address>, dispatching the requests to a <handler>
    (typically FTPHandler class).

    Depending on the type of address specified IPv4 or IPv6 connections
    (or both, depending from the underlying system) will be accepted.

    All relevant session information is stored in class attributes
    described below.

     - (int) max_cons:
        number of maximum simultaneous connections accepted (defaults
        to 512). Can be set to 0 for unlimited but it is recommended
        to always have a limit to avoid running out of file descriptors
        (DoS).

     - (int) max_cons_per_ip:
        number of maximum connections accepted for the same IP address
        (defaults to 0 == unlimited).
    """

    max_cons = 512
    max_cons_per_ip = 0

    def __init__(self, address, handler):
        """Initiate the FTP server opening listening on address.

         - (tuple) address: the host:port pair on which the command
           channel will listen.

         - (classobj) handler: the handler class to use.
        """
        asyncore.dispatcher.__init__(self)
        self.handler = handler
        self.ip_map = []
        host, port = address
        # in case of FTPS class not properly configured we want errors
        # to be raised here rather than later, when client connects
        if hasattr(handler, 'get_ssl_context'):
            handler.get_ssl_context()

        # AF_INET or AF_INET6 socket
        # Get the correct address family for our host (allows IPv6 addresses)
        try:
            info = socket.getaddrinfo(host, port, socket.AF_UNSPEC,
                                      socket.SOCK_STREAM, 0, socket.AI_PASSIVE)
        except socket.gaierror:
            # Probably a DNS issue. Assume IPv4.
            self.create_socket(socket.AF_INET, socket.SOCK_STREAM)
            self.set_reuse_addr()
            self.bind((host, port))
        else:
            for res in info:
                af, socktype, proto, canonname, sa = res
                try:
                    self.create_socket(af, socktype)
                    self.set_reuse_addr()
                    self.bind(sa)
                except socket.error, msg:
                    if self.socket:
                        self.socket.close()
                    self.socket = None
                    continue
                break
            if not self.socket:
                raise socket.error(msg)
        self.listen(5)

    def set_reuse_addr(self):
        # Overridden for convenience. Avoid to reuse address on Windows.
        if (os.name in ('nt', 'ce')) or (sys.platform == 'cygwin'):
            return
        asyncore.dispatcher.set_reuse_addr(self)

    def serve_forever(self, timeout=1.0, use_poll=False, map=None, count=None):
        """A wrap around asyncore.loop(); starts the asyncore polling
        loop including running the scheduler.
        The arguments are the same expected by original asyncore.loop()
        function:

         - (float) timeout: the timeout passed to select() or poll()
           system calls expressed in seconds (default 1.0).

         - (bool) use_poll: when True use poll() instead of select()
           (default False).

         - (dict) map: a dictionary whose items are the channels to
           watch.

         - (int) count: how many times the polling loop gets called
           before returning.  If None loops forever (default None).
        """
        if map is None:
            map = asyncore.socket_map
        if use_poll and hasattr(asyncore.select, 'poll'):
            poll_fun = asyncore.poll2
        else:
            poll_fun = asyncore.poll

        if count is None:
            log("Serving FTP on %s:%s" % self.socket.getsockname()[:2])
            try:
                while map or _tasks:
                    if map:
                        poll_fun(timeout, map)
                    if _tasks:
                        _scheduler()
            except (KeyboardInterrupt, SystemExit, asyncore.ExitNow):
                log("Shutting down FTP server.")
                self.close_all()
        else:
            while (map or _tasks) and count > 0:
                if map:
                    poll_fun(timeout, map)
                if _tasks:
                    _scheduler()
                count = count - 1

    def handle_accept(self):
        """Called when remote client initiates a connection."""
        try:
            sock, addr = self.accept()
        except TypeError:
            # sometimes accept() might return None (see issue 91)
            return
        except socket.error, err:
            # ECONNABORTED might be thrown on *BSD (see issue 105)
            if err[0] != errno.ECONNABORTED:
                logerror(traceback.format_exc())
            return
        else:
            # sometimes addr == None instead of (ip, port) (see issue 104)
            if addr == None:
                return

        try:
            handler = self.handler(sock, self)
        except socket.error, err:
            # safety measure in case of undiscovered asyncore bugs, see:
            # http://code.google.com/p/pyftpdlib/issues/detail?id=143
            logerror(str(err))
            return
        if not handler.connected:
            return
        log("[]%s:%s Connected." % addr[:2])
        ip = addr[0]
        self.ip_map.append(ip)

        # For performance and security reasons we should always set a
        # limit for the number of file descriptors that socket_map
        # should contain.  When we're running out of such limit we'll
        # use the last available channel for sending a 421 response
        # to the client before disconnecting it.
        if self.max_cons and (len(self._map) > self.max_cons):
            handler.handle_max_cons()
            return

        # accept only a limited number of connections from the same
        # source address.
        if self.max_cons_per_ip and (self.ip_map.count(ip) > self.max_cons_per_ip):
            handler.handle_max_cons_per_ip()
            return

        handler.handle()

    def writable(self):
        return 0

    def handle_error(self):
        """Called to handle any uncaught exceptions."""
        try:
            raise
        except (KeyboardInterrupt, SystemExit, asyncore.ExitNow):
            raise
        except:
            logerror(traceback.format_exc())
        self.close()

    def close_all(self, map=None, ignore_all=False):
        """Stop serving and also disconnects all currently connected
        clients.

         - (dict) map:
            A dictionary whose items are the channels to close.
            If map is omitted, the default asyncore.socket_map is used.

         - (bool) ignore_all:
            having it set to False results in raising exception in case
            of unexpected errors.

        Implementation note:

        This is how asyncore.close_all() is implemented starting from
        Python 2.6.
        The previous versions of close_all() instead of iterating over
        all opened channels and calling close() method for each one
        of them only closed sockets generating memory leaks.
        """
        if map is None:
            map = self._map
        values = map.values()
        # We sort the list so that we close all FTP handler instances
        # first since FTPHandler.close() has the peculiarity of
        # automatically closing all its children (DTPHandler, ActiveDTP
        # and PassiveDTP).
        # This should minimize the possibility to incur in race
        # conditions or memory leaks caused by orphaned references
        # left behind in case of error.
        values.sort(key=lambda inst: isinstance(inst, FTPHandler), reverse=True)
        for x in values:
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

        for x in _tasks:
            try:
                x.cancel()
            except (asyncore.ExitNow, KeyboardInterrupt, SystemExit):
                raise
            except:
                if not ignore_all:
                    raise
        del _tasks[:]


def main():
    """Start a stand alone anonymous FTP server."""

    class CustomizedOptionFormatter(optparse.IndentedHelpFormatter):
        """Formats options shown in help in a prettier way."""

        def format_option(self, option):
            result = []
            opts = self.option_strings[option]
            result.append('  %s\n' % opts)
            if option.help:
                help_text = '     %s\n\n' % self.expand_default(option)
                result.append(help_text)
            return ''.join(result)

    usage = "python -m pyftpdlib.ftpserver [options]"
    parser = optparse.OptionParser(usage=usage, description=main.__doc__,
                                   formatter=CustomizedOptionFormatter())
    parser.add_option('-i', '--interface', default='', metavar="ADDRESS",
                      help="specify the interface to run on (default all "
                           "interfaces)")
    parser.add_option('-p', '--port', type="int", default=21, metavar="PORT",
                      help="specity port number to run on (default 21)")
    parser.add_option('-w', '--write', action="store_true", default=False,
                      help="grants write access for the anonymous user "
                           "(default read-only)")
    parser.add_option('-d', '--directory', default=os.getcwd(), metavar="FOLDER",
                      help="specify the directory to share (default current "
                           "directory)")
    parser.add_option('-n', '--nat-address', default=None, metavar="ADDRESS",
                      help="the NAT address to use for passive connections")
    parser.add_option('-r', '--range',  default=None, metavar="FROM-TO",
                      help="the range of TCP ports to use for passive "
                           "connections (e.g. -r 8000-9000)")
    parser.add_option('-v', '--version', action='store_true',
                      help="print pyftpdlib version and exit")

    options, args = parser.parse_args()
    if options.version:
        sys.exit("pyftpdlib %s" % __ver__)
    passive_ports = None
    if options.range:
        try:
            start, stop = options.range.split('-')
            start = int(start)
            stop = int(stop)
        except ValueError:
            parser.error('invalid argument passed to -r option')
        else:
            passive_ports = range(start, stop + 1)
    # On recent Windows versions, if address is not specified and IPv6
    # is installed the socket will listen on IPv6 by default; in this
    # case we force IPv4 instead.
    if os.name in ('nt', 'ce') and not options.interface:
        options.interface = '0.0.0.0'

    authorizer = DummyAuthorizer()
    perm = options.write and "elradfmw" or "elr"
    authorizer.add_anonymous(options.directory, perm=perm)
    handler = FTPHandler
    handler.authorizer = authorizer
    handler.masquerade_address = options.nat_address
    handler.passive_ports = passive_ports
    ftpd = FTPServer((options.interface, options.port), FTPHandler)
    ftpd.serve_forever()

if __name__ == '__main__':
    main()

