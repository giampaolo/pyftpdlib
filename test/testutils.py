#!/usr/bin/env python

#  ======================================================================
#  Copyright (C) 2007-2016 Giampaolo Rodola' <g.rodola@gmail.com>
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

import atexit
import contextlib
import errno
import functools
import logging
import os
import shutil
import socket
import sys
import tempfile
import threading
import warnings

from pyftpdlib._compat import callable
from pyftpdlib._compat import getcwdu
from pyftpdlib._compat import u
from pyftpdlib.authorizers import DummyAuthorizer
from pyftpdlib.handlers import FTPHandler
from pyftpdlib.ioloop import IOLoop
from pyftpdlib.servers import FTPServer

if sys.version_info < (2, 7):
    import unittest2 as unittest  # pip install unittest2
else:
    import unittest

if not hasattr(unittest.TestCase, "assertRaisesRegex"):
    unittest.TestCase.assertRaisesRegex = unittest.TestCase.assertRaisesRegexp

sendfile = None
if os.name == 'posix':
    try:
        import sendfile
    except ImportError:
        pass


# Attempt to use IP rather than hostname (test suite will run a lot faster)
try:
    HOST = socket.gethostbyname('localhost')
except socket.error:
    HOST = 'localhost'
USER = 'user'
PASSWD = '12345'
HOME = getcwdu()
TESTFN = 'tmp-pyftpdlib'
TESTFN_UNICODE = TESTFN + '-unicode-' + '\xe2\x98\x83'
TESTFN_UNICODE_2 = TESTFN_UNICODE + '-2'
TIMEOUT = 2
BUFSIZE = 1024
INTERRUPTED_TRANSF_SIZE = 32768
NO_RETRIES = 5
OSX = sys.platform.startswith("darwin")
WINDOWS = os.name == 'nt'
TRAVIS = bool(os.environ.get('TRAVIS'))
VERBOSITY = 2


def try_address(host, port=0, family=socket.AF_INET):
    """Try to bind a socket on the given host:port and return True
    if that has been possible."""
    try:
        with contextlib.closing(socket.socket(family)) as sock:
            sock.bind((host, port))
    except (socket.error, socket.gaierror):
        return False
    else:
        return True

SUPPORTS_IPV4 = try_address('127.0.0.1')
SUPPORTS_IPV6 = socket.has_ipv6 and try_address('::1', family=socket.AF_INET6)
SUPPORTS_SENDFILE = hasattr(os, 'sendfile') or sendfile is not None


def safe_remove(*files):
    "Convenience function for removing temporary test files"
    for file in files:
        try:
            os.remove(file)
        except OSError as err:
            if err.errno != errno.ENOENT:
                raise


def safe_rmdir(dir):
    "Convenience function for removing temporary test directories"
    try:
        os.rmdir(dir)
    except OSError as err:
        if err.errno != errno.ENOENT:
            raise


def safe_mkdir(dir):
    "Convenience function for creating a directory"
    try:
        os.mkdir(dir)
    except OSError as err:
        if err.errno != errno.EEXIST:
            raise


def touch(name):
    """Create a file and return its name."""
    with open(name, 'w') as f:
        return f.name


def remove_test_files():
    """Remove files and directores created during tests."""
    for name in os.listdir(u('.')):
        if name.startswith(tempfile.template):
            if os.path.isdir(name):
                shutil.rmtree(name)
            else:
                os.remove(name)


def warn(msg):
    """Add warning message to be executed on exit."""
    atexit.register(warnings.warn, str(msg) + " - tests have been skipped",
                    RuntimeWarning)


def configure_logging():
    """Set pyftpdlib logger to "WARNING" level."""
    channel = logging.StreamHandler()
    logger = logging.getLogger('pyftpdlib')
    logger.setLevel(logging.WARNING)
    logger.addHandler(channel)


def disable_log_warning(inst):
    """Temporarily set FTP server's logging level to ERROR."""

    def wrapper(self, *args, **kwargs):
        logger = logging.getLogger('pyftpdlib')
        level = logger.getEffectiveLevel()
        logger.setLevel(logging.ERROR)
        try:
            return callable(self, *args, **kwargs)
        finally:
            logger.setLevel(level)
    return wrapper


def cleanup():
    """Cleanup function executed on interpreter exit."""
    remove_test_files()
    map = IOLoop.instance().socket_map
    for x in list(map.values()):
        try:
            sys.stderr.write("garbage: %s\n" % repr(x))
            x.close()
        except Exception:
            pass
    map.clear()


def retry_before_failing(ntimes=None):
    """Decorator which runs a test function and retries N times before
    actually failing.
    """
    def decorator(fun):
        @functools.wraps(fun)
        def wrapper(*args, **kwargs):
            for x in range(ntimes or NO_RETRIES):
                try:
                    return fun(*args, **kwargs)
                except AssertionError as _:
                    err = _
            raise err
        return wrapper
    return decorator


# commented out as per bug http://bugs.python.org/issue10354
# tempfile.template = 'tmp-pyftpdlib'


class FTPd(threading.Thread):
    """A threaded FTP server used for running tests.

    This is basically a modified version of the FTPServer class which
    wraps the polling loop into a thread.

    The instance returned can be used to start(), stop() and
    eventually re-start() the server.
    """
    handler = FTPHandler
    server_class = FTPServer

    def __init__(self, addr=None):
        threading.Thread.__init__(self)
        self.__serving = False
        self.__stopped = False
        self.__lock = threading.Lock()
        self.__flag = threading.Event()
        if addr is None:
            addr = (HOST, 0)

        authorizer = DummyAuthorizer()
        authorizer.add_user(USER, PASSWD, HOME, perm='elradfmwM')  # full perms
        authorizer.add_anonymous(HOME)
        self.handler.authorizer = authorizer
        # lower buffer sizes = more "loops" while transfering data
        # = less false positives
        self.handler.dtp_handler.ac_in_buffer_size = 4096
        self.handler.dtp_handler.ac_out_buffer_size = 4096
        self.server = self.server_class(addr, self.handler)
        self.host, self.port = self.server.socket.getsockname()[:2]

    def __repr__(self):
        status = [self.__class__.__module__ + "." + self.__class__.__name__]
        if self.__serving:
            status.append('active')
        else:
            status.append('inactive')
        status.append('%s:%s' % self.server.socket.getsockname()[:2])
        return '<%s at %#x>' % (' '.join(status), id(self))

    @property
    def running(self):
        return self.__serving

    def start(self, timeout=0.001):
        """Start serving until an explicit stop() request.
        Polls for shutdown every 'timeout' seconds.
        """
        if self.__serving:
            raise RuntimeError("Server already started")
        if self.__stopped:
            # ensure the server can be started again
            FTPd.__init__(self, self.server.socket.getsockname(), self.handler)
        self.__timeout = timeout
        threading.Thread.start(self)
        self.__flag.wait()

    def run(self):
        self.__serving = True
        self.__flag.set()
        while self.__serving:
            with self.__lock:
                self.server.serve_forever(timeout=self.__timeout,
                                          blocking=False)
        self.server.close_all()

    def stop(self):
        """Stop serving (also disconnecting all currently connected
        clients) by telling the serve_forever() loop to stop and
        waits until it does.
        """
        if not self.__serving:
            raise RuntimeError("Server not started yet")
        self.__serving = False
        self.__stopped = True
        self.join(timeout=3)
        if threading.activeCount() > 1:
            warn("test FTP server thread is still running")
