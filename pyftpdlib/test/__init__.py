# Copyright (C) 2007 Giampaolo Rodola' <g.rodola@gmail.com>.
# Use of this source code is governed by MIT license that can be
# found in the LICENSE file.

from __future__ import print_function
import contextlib
import errno
import functools
import logging
import multiprocessing
import os
import shutil
import socket
import sys
import tempfile
import threading
import time
try:
    from unittest import mock  # py3
except ImportError:
    import mock  # NOQA - requires "pip install mock"

from pyftpdlib._compat import getcwdu
from pyftpdlib._compat import u
from pyftpdlib.authorizers import DummyAuthorizer
from pyftpdlib.handlers import _import_sendfile
from pyftpdlib.handlers import FTPHandler
from pyftpdlib.ioloop import IOLoop
from pyftpdlib.servers import FTPServer

import psutil

if sys.version_info < (2, 7):
    import unittest2 as unittest  # pip install unittest2
else:
    import unittest

if not hasattr(unittest.TestCase, "assertRaisesRegex"):
    unittest.TestCase.assertRaisesRegex = unittest.TestCase.assertRaisesRegexp

sendfile = _import_sendfile()


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
POSIX = os.name == 'posix'
WINDOWS = os.name == 'nt'
TRAVIS = bool(os.environ.get('TRAVIS'))
VERBOSITY = 1 if os.getenv('SILENT') else 2


class TestCase(unittest.TestCase):

    def __str__(self):
        return "%s.%s.%s" % (
            self.__class__.__module__, self.__class__.__name__,
            self._testMethodName)


# Hack that overrides default unittest.TestCase in order to print
# a full path representation of the single unit tests being run.
unittest.TestCase = TestCase


def close_client(session):
    """Closes a ftplib.FTP client session."""
    try:
        if session.sock is not None:
            try:
                resp = session.quit()
            except Exception:
                pass
            else:
                # ...just to make sure the server isn't replying to some
                # pending command.
                assert resp.startswith('221'), resp
    finally:
        session.close()


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
            if os.name == 'nt':
                return
            if err.errno != errno.ENOENT:
                raise


def safe_rmdir(dir):
    "Convenience function for removing temporary test directories"
    try:
        os.rmdir(dir)
    except OSError as err:
        if os.name == 'nt':
            return
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
                safe_remove(name)


def configure_logging():
    """Set pyftpdlib logger to "WARNING" level."""
    channel = logging.StreamHandler()
    logger = logging.getLogger('pyftpdlib')
    logger.setLevel(logging.WARNING)
    logger.addHandler(channel)


def disable_log_warning(fun):
    """Temporarily set FTP server's logging level to ERROR."""
    @functools.wraps(fun)
    def wrapper(self, *args, **kwargs):
        logger = logging.getLogger('pyftpdlib')
        level = logger.getEffectiveLevel()
        logger.setLevel(logging.ERROR)
        try:
            return fun(self, *args, **kwargs)
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


def retry_on_failure(ntimes=None):
    """Decorator to retry a test in case of failure."""
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


def call_until(fun, expr, timeout=TIMEOUT):
    """Keep calling function for timeout secs and exit if eval()
    expression is True.
    """
    stop_at = time.time() + timeout
    while time.time() < stop_at:
        ret = fun()
        if eval(expr):
            return ret
        time.sleep(0.001)
    raise RuntimeError('timed out (ret=%r)' % ret)


def get_server_handler():
    """Return the first FTPHandler instance running in the IOLoop."""
    ioloop = IOLoop.instance()
    for fd in ioloop.socket_map:
        instance = ioloop.socket_map[fd]
        if isinstance(instance, FTPHandler):
            return instance
    raise RuntimeError("can't find any FTPHandler instance")


# commented out as per bug http://bugs.python.org/issue10354
# tempfile.template = 'tmp-pyftpdlib'

def setup_server(handler, server_class, addr=None):
    addr = (HOST, 0) if addr is None else addr
    authorizer = DummyAuthorizer()
    # full perms
    authorizer.add_user(USER, PASSWD, HOME, perm='elradfmwMT')
    authorizer.add_anonymous(HOME)
    handler.authorizer = authorizer
    handler.auth_failed_timeout = 0.001
    # lower buffer sizes = more "loops" while transfering data
    # = less false positives
    handler.dtp_handler.ac_in_buffer_size = 4096
    handler.dtp_handler.ac_out_buffer_size = 4096
    server = server_class(addr, handler)
    return server


def assert_free_resources():
    ts = threading.enumerate()
    assert len(ts) == 1, ts
    p = psutil.Process()
    children = p.children()
    if children:
        for p in children:
            p.kill()
            p.wait(1)
        assert not children, children
    cons = [x for x in p.connections('tcp')
            if x.status != psutil.CONN_CLOSE_WAIT]
    assert not cons, cons


def reset_server_opts():
    # Since all pyftpdlib configurable "options" are class attributes
    # we reset them at module.class level.
    import pyftpdlib.handlers
    import pyftpdlib.servers
    from pyftpdlib.handlers import _import_sendfile

    # Control handlers.
    tls_handler = getattr(pyftpdlib.handlers, "TLS_FTPHandler",
                          pyftpdlib.handlers.FTPHandler)
    for klass in (pyftpdlib.handlers.FTPHandler, tls_handler):
        klass.auth_failed_timeout = 0.001
        klass.authorizer = DummyAuthorizer()
        klass.banner = "pyftpdlib ready."
        klass.masquerade_address = None
        klass.masquerade_address_map = {}
        klass.max_login_attempts = 3
        klass.passive_ports = None
        klass.permit_foreign_addresses = False
        klass.permit_privileged_ports = False
        klass.tcp_no_delay = hasattr(socket, 'TCP_NODELAY')
        klass.timeout = 300
        klass.unicode_errors = "replace"
        klass.use_gmt_times = True
        klass.use_sendfile = _import_sendfile() is not None
        klass.ac_in_buffer_size = 4096
        klass.ac_out_buffer_size = 4096
        if klass.__name__ == 'TLS_FTPHandler':
            klass.tls_control_required = False
            klass.tls_data_required = False

    # Data handlers.
    tls_handler = getattr(pyftpdlib.handlers, "TLS_DTPHandler",
                          pyftpdlib.handlers.DTPHandler)
    for klass in (pyftpdlib.handlers.DTPHandler, tls_handler):
        klass.timeout = 300
        klass.ac_in_buffer_size = 4096
        klass.ac_out_buffer_size = 4096
    pyftpdlib.handlers.ThrottledDTPHandler.read_limit = 0
    pyftpdlib.handlers.ThrottledDTPHandler.write_limit = 0
    pyftpdlib.handlers.ThrottledDTPHandler.auto_sized_buffers = True

    # Acceptors.
    ls = [pyftpdlib.servers.FTPServer,
          pyftpdlib.servers.ThreadedFTPServer]
    if os.name == 'posix':
        ls.append(pyftpdlib.servers.MultiprocessFTPServer)
    for klass in ls:
        klass.max_cons = 0
        klass.max_cons_per_ip = 0


class ThreadedTestFTPd(threading.Thread):
    """A threaded FTP server used for running tests.
    This is basically a modified version of the FTPServer class which
    wraps the polling loop into a thread.
    The instance returned can be start()ed and stop()ped.
    """
    handler = FTPHandler
    server_class = FTPServer
    poll_interval = 0.001 if TRAVIS else 0.000001
    # Makes the thread stop on interpreter exit.
    daemon = True

    def __init__(self, addr=None):
        super(ThreadedTestFTPd, self).__init__(name='test-ftpd')
        self.server = setup_server(self.handler, self.server_class, addr=addr)
        self.host, self.port = self.server.socket.getsockname()[:2]

        self.lock = threading.Lock()
        self._stop_flag = False
        self._event_stop = threading.Event()

    def run(self):
        try:
            while not self._stop_flag:
                with self.lock:
                    self.server.serve_forever(timeout=self.poll_interval,
                                              blocking=False)
        finally:
            self._event_stop.set()

    def stop(self):
        self._stop_flag = True  # signal the main loop to exit
        self._event_stop.wait()
        self.server.close_all()
        self.join()
        reset_server_opts()
        assert_free_resources()


class MProcessTestFTPd(multiprocessing.Process):
    """Same as above but using a sub process instead."""
    handler = FTPHandler
    server_class = FTPServer

    def __init__(self, addr=None):
        super(MProcessTestFTPd, self).__init__(name='test-ftpd')
        self.server = setup_server(self.handler, self.server_class, addr=addr)
        self.host, self.port = self.server.socket.getsockname()[:2]
        self._started = False

    def run(self):
        assert not self._started
        self._started = True
        self.server.serve_forever()

    def stop(self):
        self.server.close_all()
        self.terminate()
        self.join()
        reset_server_opts()
        assert_free_resources()
