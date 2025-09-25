# Copyright (C) 2007 Giampaolo Rodola' <g.rodola@gmail.com>.
# Use of this source code is governed by MIT license that can be
# found in the LICENSE file.


import contextlib
import functools
import logging
import multiprocessing
import os
import shutil
import socket
import stat
import sys
import tempfile
import threading
import time
import unittest
import warnings

import psutil

import pyftpdlib.servers
from pyftpdlib.authorizers import DummyAuthorizer
from pyftpdlib.handlers import FTPHandler
from pyftpdlib.ioloop import IOLoop
from pyftpdlib.servers import FTPServer

HERE = os.path.realpath(os.path.abspath(os.path.dirname(__file__)))
ROOT_DIR = os.path.realpath(os.path.join(HERE, "..", ".."))

PYPY = "__pypy__" in sys.builtin_module_names
OSX = sys.platform.startswith("darwin")
POSIX = os.name == "posix"
BSD = "bsd" in sys.platform
WINDOWS = os.name == "nt"
CERTFILE = os.path.join(HERE, "keycert.pem")


GITHUB_ACTIONS = "GITHUB_ACTIONS" in os.environ or "CIBUILDWHEEL" in os.environ
CI_TESTING = GITHUB_ACTIONS
COVERAGE = "COVERAGE_RUN" in os.environ
PYTEST_PARALLEL = "PYTEST_XDIST_WORKER" in os.environ  # `make test-parallel`

# Attempt to use IP rather than hostname (test suite will run a lot faster)
try:
    HOST = socket.gethostbyname("localhost")
except OSError:
    HOST = "localhost"

USER = "user"
PASSWD = "12345"
HOME = os.getcwd()
# Use PID to disambiguate file name for parallel testing.
TESTFN_PREFIX = f"pyftpd-tmp-{os.getpid()}-"
GLOBAL_TIMEOUT = 2
BUFSIZE = 1024
INTERRUPTED_TRANSF_SIZE = 32768
NO_RETRIES = 5
VERBOSITY = 1 if os.getenv("SILENT") else 2

if CI_TESTING:
    GLOBAL_TIMEOUT *= 3
    NO_RETRIES *= 3

SUPPORTS_IPV4 = None  # set later
SUPPORTS_IPV6 = None  # set later
SUPPORTS_MULTIPROCESSING = hasattr(pyftpdlib.servers, "MultiprocessFTPServer")
if BSD or (OSX and GITHUB_ACTIONS):
    SUPPORTS_MULTIPROCESSING = False  # XXX: it's broken!!


class PyftpdlibTestCase(unittest.TestCase):
    """All test classes inherit from this one."""

    def setUp(self):
        super().setUp()
        reset_server_opts()

    def __str__(self):
        # Print a full path representation of the single unit tests
        # being run.
        fqmod = self.__class__.__module__
        if not fqmod.startswith("pyftpdlib."):
            fqmod = "pyftpdlib.test." + fqmod
        return f"{fqmod}.{self.__class__.__name__}.{self._testMethodName}"

    def get_testfn(self, suffix="", dir=None):
        fname = get_testfn(suffix=suffix, dir=dir)
        self.addCleanup(safe_rmpath, fname)
        return fname


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
                assert resp.startswith("221"), resp
    finally:
        session.close()


def try_address(host, port=0, family=socket.AF_INET):
    """Try to bind a socket on the given host:port and return True
    if that has been possible."""
    # Note: if IPv6 fails on Linux do:
    # $ sudo sh -c 'echo 0 > /proc/sys/net/ipv6/conf/all/disable_ipv6'
    try:
        with contextlib.closing(socket.socket(family)) as sock:
            sock.bind((host, port))
    except (OSError, socket.gaierror):
        return False
    else:
        return True


SUPPORTS_IPV4 = try_address("127.0.0.1")
SUPPORTS_IPV6 = socket.has_ipv6 and try_address("::1", family=socket.AF_INET6)


def get_testfn(suffix="", dir=None):
    """Return an absolute pathname of a file or dir that did not
    exist at the time this call is made. Also schedule it for safe
    deletion at interpreter exit. It's technically racy but probably
    not really due to the time variant.
    """
    if dir is None:
        dir = os.getcwd()
    while True:
        name = tempfile.mktemp(prefix=TESTFN_PREFIX, suffix=suffix, dir=dir)
        if not os.path.exists(name):  # also include dirs
            return os.path.basename(name)


def safe_rmpath(path):
    """Convenience function for removing temporary test files or dirs."""

    def retry_fun(fun):
        # On Windows it could happen that the file or directory has
        # open handles or references preventing the delete operation
        # to succeed immediately, so we retry for a while. See:
        # https://bugs.python.org/issue33240
        stop_at = time.time() + GLOBAL_TIMEOUT
        while time.time() < stop_at:
            try:
                return fun()
            except FileNotFoundError:
                pass
            except OSError as _:
                err = _
                warnings.warn(f"ignoring {err!s}", UserWarning, stacklevel=2)
            time.sleep(0.01)
        raise err

    try:
        st = os.stat(path)
        if stat.S_ISDIR(st.st_mode):
            fun = functools.partial(shutil.rmtree, path)
        else:
            fun = functools.partial(os.remove, path)
        if POSIX:
            fun()
        else:
            retry_fun(fun)
    except FileNotFoundError:
        pass


def touch(name):
    """Create a file and return its name."""
    with open(name, "w") as f:
        return f.name


def disable_log_warning(fun):
    """Temporarily set FTP server's logging level to ERROR."""

    @functools.wraps(fun)
    def wrapper(self, *args, **kwargs):
        logger = logging.getLogger("pyftpdlib")
        level = logger.getEffectiveLevel()
        logger.setLevel(logging.ERROR)
        try:
            return fun(self, *args, **kwargs)
        finally:
            logger.setLevel(level)

    return wrapper


class retry:
    """A retry decorator."""

    def __init__(
        self,
        exception=Exception,
        timeout=None,
        retries=None,
        interval=0.001,
        logfun=None,
    ):
        if timeout and retries:
            raise ValueError("timeout and retries args are mutually exclusive")
        self.exception = exception
        self.timeout = timeout
        self.retries = retries
        self.interval = interval
        self.logfun = logfun

    def __iter__(self):
        if self.timeout:
            stop_at = time.time() + self.timeout
            while time.time() < stop_at:
                yield
        elif self.retries:
            for _ in range(self.retries):
                yield
        else:
            while True:
                yield

    def sleep(self):
        if self.interval is not None:
            time.sleep(self.interval)

    def __call__(self, fun):
        @functools.wraps(fun)
        def wrapper(cls, *args, **kwargs):
            exc = None
            for _ in self:
                try:
                    return fun(cls, *args, **kwargs)
                except self.exception as _:
                    exc = _
                    if self.logfun is not None:
                        self.logfun(exc)
                    self.sleep()
                    if isinstance(cls, unittest.TestCase):
                        cls.tearDown()
                        cls.setUp()
                    continue

            raise exc

        # This way the user of the decorated function can change config
        # parameters.
        wrapper.decorator = self
        return wrapper


def retry_on_failure(fun):
    """Decorator which runs a test function and retries N times before
    actually failing.
    """

    @functools.wraps(fun)
    def wrapper(self, *args, **kwargs):
        for x in range(NO_RETRIES):
            try:
                return fun(self, *args, **kwargs)
            except AssertionError as exc:
                if x + 1 >= NO_RETRIES:
                    raise
                msg = f"{exc!r}, retrying"
                print(msg, file=sys.stderr)  # noqa: T201
                if PYTEST_PARALLEL:
                    warnings.warn(msg, ResourceWarning, stacklevel=2)
                self.tearDown()
                self.setUp()

    return wrapper


def call_until(fun, expr, timeout=GLOBAL_TIMEOUT):
    """Keep calling function for timeout secs and exit if eval()
    expression is True.
    """
    stop_at = time.time() + timeout
    while time.time() < stop_at:
        ret = fun()
        if eval(expr):
            return ret
        time.sleep(0.001)
    raise RuntimeError(f"timed out (ret={ret!r})")


def get_server_handler():
    """Return the first FTPHandler instance running in the IOLoop."""
    ioloop = IOLoop.instance()
    for fd in ioloop.socket_map:
        instance = ioloop.socket_map[fd]
        if isinstance(instance, FTPHandler):
            return instance
    raise RuntimeError("can't find any FTPHandler instance")


# commented out as per bug https://bugs.python.org/issue10354
# tempfile.template = 'tmp-pyftpdlib'


def setup_server(handler, server_class, addr=None):
    addr = (HOST, 0) if addr is None else addr
    authorizer = DummyAuthorizer()
    # full perms
    authorizer.add_user(USER, PASSWD, HOME, perm="elradfmwMT")
    authorizer.add_anonymous(HOME)
    handler.authorizer = authorizer
    handler.auth_failed_timeout = 0.001
    # lower buffer sizes = more "loops" while transferring data
    # = less false positives
    handler.dtp_handler.ac_in_buffer_size = 4096
    handler.dtp_handler.ac_out_buffer_size = 4096
    server = server_class(addr, handler)
    return server


def assert_free_resources(parent_pid=None):
    # check orphaned threads
    ts = threading.enumerate()
    assert len(ts) == 1, ts
    # check orphaned process children
    this_proc = psutil.Process(parent_pid or os.getpid())
    children = this_proc.children()
    if children:
        warnings.warn(
            f"some children didn't terminate (pid={os.getpid()!r})"
            f" {str(children)!r}",
            UserWarning,
            stacklevel=2,
        )
        for child in children:
            try:
                child.kill()
                child.wait(GLOBAL_TIMEOUT)
            except psutil.NoSuchProcess:
                pass
    # check unclosed connections
    if POSIX:
        cons = [
            x
            for x in this_proc.net_connections("tcp")
            if x.status != psutil.CONN_CLOSE_WAIT
        ]
        if cons:
            warnings.warn(
                f"some connections didn't close (pid={os.getpid()!r})"
                f" {str(cons)!r}",
                UserWarning,
                stacklevel=2,
            )


def reset_server_opts():
    # Since all pyftpdlib configurable "options" are class attributes
    # we reset them at module.class level.
    import pyftpdlib.handlers  # noqa: PLC0415
    import pyftpdlib.servers  # noqa: PLC0415

    # Control handlers.
    tls_handler = getattr(
        pyftpdlib.handlers, "TLS_FTPHandler", pyftpdlib.handlers.FTPHandler
    )
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
        klass.tcp_no_delay = hasattr(socket, "TCP_NODELAY")
        klass.timeout = 300
        klass.unicode_errors = "replace"
        klass.use_gmt_times = True
        klass.use_sendfile = hasattr(os, "sendfile")
        klass.ac_in_buffer_size = 4096
        klass.ac_out_buffer_size = 4096
        klass.encoding = "utf8"
        if klass.__name__ == "TLS_FTPHandler":
            klass.tls_control_required = False
            klass.tls_data_required = False

    # Data handlers.
    tls_handler = getattr(
        pyftpdlib.handlers, "TLS_DTPHandler", pyftpdlib.handlers.DTPHandler
    )
    for klass in (pyftpdlib.handlers.DTPHandler, tls_handler):
        klass.timeout = 300
        klass.ac_in_buffer_size = 4096
        klass.ac_out_buffer_size = 4096
    pyftpdlib.handlers.ThrottledDTPHandler.read_limit = 0
    pyftpdlib.handlers.ThrottledDTPHandler.write_limit = 0
    pyftpdlib.handlers.ThrottledDTPHandler.auto_sized_buffers = True

    # Acceptors.
    ls = [pyftpdlib.servers.FTPServer, pyftpdlib.servers.ThreadedFTPServer]
    if POSIX:
        ls.append(pyftpdlib.servers.MultiprocessFTPServer)
    for klass in ls:
        klass.max_cons = 0
        klass.max_cons_per_ip = 0


class FtpdThreadWrapper(threading.Thread):
    """A threaded FTP server used for running tests.
    This is basically a modified version of the FTPServer class which
    wraps the polling loop into a thread.
    The instance returned can be start()ed and stop()ped.
    """

    handler = FTPHandler
    server_class = FTPServer
    poll_interval = 0.001 if CI_TESTING else 0.000001
    # Makes the thread stop on interpreter exit.
    daemon = True

    def __init__(self, addr=None):
        self.parent_pid = os.getpid()
        super().__init__(name="test-ftpd")
        self.server = setup_server(self.handler, self.server_class, addr=addr)
        self.host, self.port = self.server.socket.getsockname()[:2]

        self.lock = threading.Lock()
        self._stop_flag = False
        self._event_stop = threading.Event()

    def run(self):
        try:
            while not self._stop_flag:
                with self.lock:
                    self.server.serve_forever(
                        timeout=self.poll_interval, blocking=False
                    )
        finally:
            self._event_stop.set()

    def stop(self):
        self._stop_flag = True  # signal the main loop to exit
        self._event_stop.wait()
        self.server.close_all()
        self.join()
        reset_server_opts()
        assert_free_resources(self.parent_pid)


if POSIX:

    class FtpdMultiprocWrapper(multiprocessing.Process):
        """Same as above but using a sub process instead."""

        handler = FTPHandler
        server_class = FTPServer

        def __init__(self, addr=None):
            super().__init__()
            self.server = setup_server(
                self.handler, self.server_class, addr=addr
            )
            self.host, self.port = self.server.socket.getsockname()[:2]
            self._started = False

        def run(self):
            assert not self._started
            self._started = True
            self.name = f"{self.__class__.__name__}({self.pid})"
            self.server.serve_forever()

        def stop(self):
            self.server.close_all()
            self.terminate()
            self.join()
            reset_server_opts()
            assert_free_resources()

else:
    # Windows
    FtpdMultiprocWrapper = FtpdThreadWrapper
