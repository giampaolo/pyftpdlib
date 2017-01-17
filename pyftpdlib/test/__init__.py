# Copyright (C) 2007-2016 Giampaolo Rodola' <g.rodola@gmail.com>.
# Use of this source code is governed by MIT license that can be
# found in the LICENSE file.

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
import time
import warnings
try:
    from queue import Queue  # py3
except ImportError:
    from Queue import Queue
try:
    from unittest import mock  # py3
except ImportError:
    import mock  # NOQA - requires "pip install mock"

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
POSIX = os.name == 'posix'
WINDOWS = os.name == 'nt'
TRAVIS = bool(os.environ.get('TRAVIS'))
VERBOSITY = 1 if os.getenv('SILENT') else 2
DEFAULT = object()


class TestCase(unittest.TestCase):

    def __str__(self):
        return "%s.%s.%s" % (
            self.__class__.__module__, self.__class__.__name__,
            self._testMethodName)


# Hack that overrides default unittest.TestCase in order to print
# a full path representation of the single unit tests being run.
unittest.TestCase = TestCase


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


class ThreadWorker(threading.Thread):
    """A wrapper on top of threading.Thread.
    It lets you define a thread worker class which you can easily
    start() and stop().
    Subclass MUST provide a poll() method. Optionally it can also
    provide the following methods:

    - before_start
    - before_stop
    - after_stop

    poll() is supposed to be a non-blocking method so that the
    worker can be stop()ped immediately.

    **All method calls are supposed to be thread safe, start(), stop()
    and the callback methods.**

    Example:

    class MyWorker(ThreadWorker):

        def poll(self):
            do_something()

        def before_start(self):
            log("starting")

        def before_stop(self):
            log("stopping")

        def after_stop(self):
            do_cleanup()

    worker = MyWorker(poll_interval=5)
    worker.start()
    worker.stop()
    """

    # Makes the thread stop on interpreter exit.
    daemon = True

    def __init__(self, poll_interval=1.0):
        super(ThreadWorker, self).__init__()
        self.poll_interval = poll_interval
        self.started = False
        self.stopped = False
        self.lock = threading.Lock()
        self._stop_flag = False
        self._event_start = threading.Event()
        self._event_stop = threading.Event()

    # --- overridable methods

    def poll(self):
        raise NotImplementedError("must be implemented in subclass")

    def before_start(self):
        """Called right before start()."""
        pass

    def before_stop(self):
        """Called right before stop(), before signaling the thread
        to stop polling.
        """
        pass

    def after_stop(self):
        """Called right after stop(), after the thread stopped polling."""
        pass

    # --- internals

    def sleep(self):
        # Responsive sleep, so that the interpreter will shut down
        # after max 1 sec.
        if self.poll_interval:
            stop_at = time.time() + self.poll_interval
            while True:
                time.sleep(min(self.poll_interval, 1))
                if time.time() >= stop_at:
                    break

    def run(self):
        try:
            while not self._stop_flag:
                with self.lock:
                    if not self.started:
                        self._event_start.set()
                        self.started = True
                    self.poll()
                self.sleep()
        finally:
            self._event_stop.set()

    # --- external API

    def start(self):
        if self.started:
            raise RuntimeError("already started")
        if self._stop_flag:
            # ensure the thread can be restarted
            super(ThreadWorker, self).__init__(self, self.poll_interval)
        with self.lock:
            self.before_start()
        threading.Thread.start(self)
        self._event_start.wait()

    def stop(self):
        # TODO: we might want to specify a timeout arg for join.
        if not self.stopped:
            with self.lock:
                self.before_stop()
                self._stop_flag = True  # signal the main loop to exit
                self.stopped = True
            # It is important to exit the lock context here otherwise
            # we might hang indefinitively.
            self.join()
            self._event_stop.wait()
            with self.lock:
                self.after_stop()


class ThreadedTestFTPd(ThreadWorker):
    """A threaded FTP server used for running tests.

    This is basically a modified version of the FTPServer class which
    wraps the polling loop into a thread.

    The instance returned can be used to start(), stop() and
    eventually re-start() the server.
    """
    handler = FTPHandler
    server_class = FTPServer
    shutdown_after = 10
    poll_interval = 0.001 if TRAVIS else 0.000001

    def __init__(self, addr=None, callback_queues=False, **kwargs):
        ThreadWorker.__init__(self, poll_interval=None)
        self.addr = (HOST, 0) if addr is None else addr

        # Set authorizer.
        self.authorizer = DummyAuthorizer()
        # full perms
        self.authorizer.add_user(USER, PASSWD, HOME, perm='elradfmwM')
        self.authorizer.add_anonymous(HOME)
        self.handler.authorizer = self.authorizer

        # Configure handler.
        max_cons = kwargs.pop('max_cons', DEFAULT)
        max_cons_per_ip = kwargs.pop('max_cons_per_ip', DEFAULT)
        self._config_handler(kwargs)

        # Configure server.
        self.server = self.server_class(self.addr, self.handler)
        if max_cons is not DEFAULT:
            self.server.max_cons = max_cons
        if max_cons_per_ip is not DEFAULT:
            self.server.max_cons_per_ip = max_cons_per_ip

        # Expose host and port.
        self.host, self.port = self.server.socket.getsockname()[:2]
        self.lock = threading.Lock()
        self.queue = None
        if callback_queues:
            self._config_callback_queues()

    def _config_handler(self, config):
        # No delayed response in case of failed auth.
        self.handler.auth_failed_timeout = 0.001
        # lower buffer sizes = more "loops" while transferring data
        # = less false positives
        self.handler.dtp_handler.ac_in_buffer_size = 4096
        self.handler.dtp_handler.ac_out_buffer_size = 4096
        # Configure handler.

        self.original_config = {}
        for k, v in config.items():
            if k not in ('dtp_handler', 'abstracted_fs'):
                assert not callable(getattr(self.handler, k))
            self.original_config[k] = getattr(self.handler, k)
            setattr(self.handler, k, v)

    def _reset_handler_config(self):
        for k, v in self.original_config.items():
            setattr(self.handler, k, v)

    def _config_callback_queues(self):
        self.queue = Queue()
        q = self.queue
        h = self.handler
        h.on_connect = lambda _: q.put('on_connect')
        h.on_disconnect = lambda _: q.put('on_disconnect')
        h.on_login = lambda _, user: q.put(('on_login', user))
        h.on_login_failed = \
            lambda _, user, pwd: q.put(('on_login_failed', user, pwd))
        h.on_logout = lambda _, user: q.put(('on_logout', user))
        h.on_file_sent = lambda _, file: q.put(('on_file_sent', file))
        h.on_file_received = lambda _, file: q.put(('on_file_received', file))
        h.on_incomplete_file_sent = \
            lambda _, file: q.put(('on_incomplete_file_sent', file))
        h.on_incomplete_file_received = \
            lambda _, file: q.put(('on_incomplete_file_received', file))

    def before_start(self):
        self.start_time = time.time()

    def poll(self):
        self.server.serve_forever(timeout=self.poll_interval, blocking=False)
        if (self.shutdown_after and
                time.time() >= self.start_time + self.shutdown_after):
            now = time.time()
            if now <= now + self.shutdown_after:
                self.server.close_all()
                raise Exception("test FTPd shutdown due to timeout")

    def after_stop(self):
        self.server.close_all()
        self._reset_handler_config()
        if self.queue is not None:
            if not self.queue.empty():
                remaining = self.queue.get()
                assert remaining == 'on_disconnect' and self.queue.empty(), \
                    remaining
