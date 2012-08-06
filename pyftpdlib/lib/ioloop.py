#!/usr/bin/env python
# $Id$

"""
A specialized IO loop on top of asyncore adding support for epoll()
on Linux and kqueue() and OSX/BSD, dramatically increasing performances
offered by base asyncore module.

poll() and select() loops are also reimplemented and are an order of
magnitude faster as they support fd un/registration and modification.

This module is not supposed to be used directly unless you want to
include a new dispatcher which runs within the main FTP server loop,
in which case:
  __________________________________________________________________
 |                      |                                           |
 | INSTEAD OF           | ...USE:                                   |
 |______________________|___________________________________________|
 |                      |                                           |
 | asyncore.dispacher   | Acceptor (for servers)                    |
 | asyncore.dispacher   | Connector (for clients)                   |
 | asynchat.async_chat  | AsyncChat (for a full duplex connection ) |
 | asyncore.loop        | FTPServer.server_forever()                |
 |______________________|___________________________________________|

asyncore.dispatcher_with_send is not supported, same for "map" argument
for asyncore.loop and asyncore.dispatcher and asynchat.async_chat
constructors.

Follows a server example:

import socket
from pyftpdlib.lib.ioloop import IOLoop, Acceptor, AsyncChat

class Handler(AsyncChat):

    def __init__(self, sock):
        AsyncChat.__init__(self, sock)
        self.push('200 hello\r\n')
        self.close_when_done()

class Server(Acceptor):

    def __init__(self, host, port):
        Acceptor.__init__(self)
        self.create_socket(socket.AF_INET, socket.SOCK_STREAM)
        self.set_reuse_addr()
        self.bind((host, port))
        self.listen(5)

    def handle_accepted(self, sock, addr):
        Handler(sock)

server = Server('localhost', 8021)
IOLoop.instance().loop()
"""

import asyncore
import asynchat
import errno
import select
import os
import sys
import traceback
import time
import heapq
import socket
try:
    import threading
except ImportError:
    import dummy_threading as threading

from pyftpdlib.lib.compat import MAXSIZE, callable


_read = asyncore.read
_write = asyncore.write

# XXX
def logerror(msg):
    sys.stderr.write(str(msg) + '\n')
    sys.stderr.flush()


# ===================================================================
# --- scheduler
# ===================================================================

class _Scheduler(object):
    """Run the scheduled functions due to expire soonest (if any)."""

    def __init__(self):
        # the heap used for the scheduled tasks
        self._tasks = []
        self._cancellations = 0

    def poll(self):
        """Run the scheduled functions due to expire soonest and
        return the timeout of the next one (if any, else None).
        """
        now = time.time()
        calls = []
        while self._tasks:
            if now < self._tasks[0].timeout:
                break
            call = heapq.heappop(self._tasks)
            if not call.cancelled:
                calls.append(call)
            else:
                self._cancellations -= 1

        for call in calls:
            if call._repush:
                heapq.heappush(self._tasks, call)
                call._repush = False
                continue
            try:
                call.call()
            except Exception:
                logerror(traceback.format_exc())

        # remove cancelled tasks and re-heapify the queue if the
        # number of cancelled tasks is more than the half of the
        # entire queue
        if self._cancellations > 512 \
          and self._cancellations > (len(self._tasks) >> 1):
            self._cancellations = 0
            self._tasks = [x for x in self._tasks if not x.cancelled]
            self.reheapify()

        try:
            return max(0, self._tasks[0].timeout - now)
        except IndexError:
            pass

    def register(self, what):
        heapq.heappush(self._tasks, what)

    def unregister(self, what):
        self._cancellations += 1

    def reheapify(self):
        heapq.heapify(self._tasks)


class _CallLater(object):
    """Container object which instance is returned by ioloop.call_later()."""

    __slots__ = ('_delay', '_target', '_args', '_kwargs', '_errback', '_sched',
                 '_repush', 'timeout', 'cancelled')

    def __init__(self, seconds, target, *args, **kwargs):
        assert callable(target), "%s is not callable" % target
        assert MAXSIZE >= seconds >= 0, "%s is not greater than or equal " \
                                        "to 0 seconds" % seconds
        self._delay = seconds
        self._target = target
        self._args = args
        self._kwargs = kwargs
        self._errback = kwargs.pop('_errback', None)
        self._sched = kwargs.pop('_scheduler')
        self._repush = False
        # seconds from the epoch at which to call the function
        if not seconds:
            self.timeout = 0
        else:
            self.timeout = time.time() + self._delay
        self.cancelled = False
        self._sched.register(self)

    def __lt__(self, other):
        return self.timeout < other.timeout

    def __le__(self, other):
        return self.timeout <= other.timeout

    def __repr__(self):
        if self._target is None:
            sig = object.__repr__(self)
        else:
            sig = repr(self._target)
        sig += ' args=%s, kwargs=%s, cancelled=%s, secs=%s' \
                % (self._args or '[]',  self._kwargs or '{}', self.cancelled,
                   self._delay)
        return '<%s>' % sig

    __str__ = __repr__

    def _post_call(self, exc):
        if not self.cancelled:
            self.cancel()

    def call(self):
        """Call this scheduled function."""
        assert not self.cancelled, "already cancelled"
        exc = None
        try:
            try:
                self._target(*self._args, **self._kwargs)
            except Exception:
                exc = sys.exc_info()[1]
                if self._errback is not None:
                    self._errback()
                else:
                    raise
        finally:
            self._post_call(exc)

    def reset(self):
        """Reschedule this call resetting the current countdown."""
        assert not self.cancelled, "already cancelled"
        self.timeout = time.time() + self._delay
        self._repush = True

    def cancel(self):
        """Unschedule this call."""
        assert not self.cancelled, "already cancelled"
        self.cancelled = True
        self._target = self._args = self._kwargs = self._errback = None
        self._sched.unregister(self)


class _CallEvery(_CallLater):
    """Container object which instance is returned by ioloop.call_every()."""

    def _post_call(self, exc):
        if not self.cancelled:
            if exc:
                self.cancel()
            else:
                self.timeout = time.time() + self._delay
                self._sched.register(self)


class _IOLoop(object):
    """Base class which will later be referred as IOLoop."""

    READ = 1
    WRITE = 2
    _instance = None
    _lock = threading.Lock()

    def __init__(self):
        self.socket_map = {}
        self.sched = _Scheduler()

    @classmethod
    def instance(cls):
        """Return a global IOLoop instance."""
        if cls._instance is None:
            cls._lock.acquire()
            try:
                cls._instance = cls()
            finally:
                cls._lock.release()
        return cls._instance

    def register(self, fd, instance, events):
        """Register a fd, handled by instance for the given events."""
        raise NotImplementedError('must be implemented in subclass')

    def unregister(self, fd):
        """Register fd."""
        raise NotImplementedError('must be implemented in subclass')

    def modify(self, fd, events):
        """Changes the events assigned for fd."""
        raise NotImplementedError('must be implemented in subclass')

    def poll(self, timeout):
        """Poll once."""
        raise NotImplementedError('must be implemented in subclass')

    def loop(self, timeout=None, blocking=True):
        """Start the asynchronous IO loop.

         - (float) timeout: the timeout passed to the underlying
           multiplex syscall (select(), epoll() etc.).

         - (bool) blocking: if False loop once and then return the
           timeout of the next scheduled call next to expire soonest
           (if any, else None).
        """
        if blocking:
            # localize variable access to minimize overhead
            poll = self.poll
            socket_map = self.socket_map
            tasks = self.sched._tasks
            sched_poll = self.sched.poll

            if timeout is not None:
                while socket_map:
                    poll(timeout)
                    sched_poll()
            else:
                soonest_timeout = None
                while socket_map:
                    poll(soonest_timeout)
                    soonest_timeout = sched_poll()
        else:
            sched = self.sched
            if self.socket_map:
                self.poll(timeout)
            if sched._tasks:
                return sched.poll()

    def call_later(self, seconds, target, *args, **kwargs):
        """Calls a function at a later time.
        It can be used to asynchronously schedule a call within the polling
        loop without blocking it. The instance returned is an object that
        can be used to cancel or reschedule the call.

         - (int) seconds: the number of seconds to wait
         - (obj) target: the callable object to call later
         - args: the arguments to call it with
         - kwargs: the keyword arguments to call it with; a special
           '_errback' parameter can be passed: it is a callable
           called in case target function raises an exception.
       """
        kwargs['_scheduler'] = self.sched
        return _CallLater(seconds, target, *args, **kwargs)

    def call_every(self, seconds, target, *args, **kwargs):
        """Schedules the given callback to be called periodically."""
        kwargs['_scheduler'] = self.sched
        return _CallEvery(seconds, target, *args, **kwargs)

    def close(self):
        """Closes the IOLoop, freeing any resources used."""
        self.__class__._instance = None

        # free connections
        instances = sorted(self.socket_map.values(), key=lambda x: x._fileno)
        for inst in instances:
            try:
                inst.close()
            except OSError:
                err = sys.exc_info()[1]
                if err.args[0] != errno.EBADF:
                    logerror(traceback.format_exc())  # XXX
            except Exception:
                logerror(traceback.format_exc())  # XXX
        self.socket_map.clear()

        # free scheduled functions
        for x in self.sched._tasks:
            try:
                if not x.cancelled:
                    x.cancel()
            except Exception:
                logerror(traceback.format_exc())  # XXX
        del self.sched._tasks[:]


# ===================================================================
# --- select() - POSIX / Windows
# ===================================================================

class Select(_IOLoop):
    """select()-based poller."""

    def __init__(self):
        _IOLoop.__init__(self)
        self._r = []
        self._w = []

    def register(self, fd, instance, events):
        if fd not in self.socket_map:
            self.socket_map[fd] = instance
            if events & self.READ:
                self._r.append(fd)
            if events & self.WRITE:
                self._w.append(fd)

    def unregister(self, fd):
        try:
            del self.socket_map[fd]
        except KeyError:
            pass
        for l in (self._r, self._w):
            try:
                l.remove(fd)
            except ValueError:
                pass

    def modify(self, fd, events):
        inst = self.socket_map.get(fd)
        if inst is not None:
            self.unregister(fd)
            self.register(fd, inst, events)

    def poll(self, timeout):
        try:
            r, w, e = select.select(self._r, self._w, [], timeout)
        except select.error:  # XXX catch EnvironmentError?
            err = sys.exc_info()[1]
            if err.args[0] == errno.EINTR:
                return
            raise

        smap_get = self.socket_map.get
        for fd in r:
            obj = smap_get(fd)
            if obj is None or not obj.readable():
                continue
            _read(obj)
        for fd in w:
            obj = smap_get(fd)
            if obj is None or not obj.writable():
                continue
            _write(obj)


# ===================================================================
# --- poll() / epoll()
# ===================================================================

class _BasePollEpoll(_IOLoop):
    """This is common to both poll/epoll implementations which
    almost share the same interface.
    Not supposed to be used directly.
    """

    def __init__(self):
        _IOLoop.__init__(self)
        self._poller = self._poller()

    def register(self, fd, instance, events):
        self._poller.register(fd, events)
        self.socket_map[fd] = instance

    def unregister(self, fd):
        try:
            del self.socket_map[fd]
        except KeyError:
            pass
        else:
            self._poller.unregister(fd)

    def modify(self, fd, events):
        self._poller.modify(fd, events)

    def poll(self, timeout):
        try:
            events = self._poller.poll(timeout or -1)  # -1 waits indefinitely
        except (EnvironmentError, select.error):  # XXX expect select.error?
            err = sys.exc_info()[1]
            if err.args[0] == errno.EINTR:
                return
            raise
        for fd, event in events:
            inst = self.socket_map.get(fd)
            if inst is None:
                continue
            if event & self._ERROR and not event & self.READ:
                inst.handle_close()
            else:
                if event & self.READ:
                    if inst.readable():
                        _read(inst)
                if event & self.WRITE:
                    if inst.writable():
                        _write(inst)


# ===================================================================
# --- poll() - POSIX
# ===================================================================

if hasattr(select, 'poll'):

    class Poll(_BasePollEpoll):
        """poll() based poller."""

        READ = select.POLLIN
        WRITE = select.POLLOUT
        _ERROR = select.POLLERR | select.POLLHUP | select.POLLNVAL
        _poller = select.poll

        # select.poll() on py < 2.6 has no 'modify' method
        if not hasattr(select.poll(), 'modify'):
            def modify(self, fd, events):
                inst = self.socket_map[fd]
                self.unregister(fd)
                self.register(fd, inst, events)

        def poll(self, timeout):
            # poll() timeout is expressed in milliseconds
            if timeout is not None:
                timeout = int(timeout * 1000)
            _BasePollEpoll.poll(self, timeout)


# ===================================================================
# --- epoll() - Linux
# ===================================================================

if hasattr(select, 'epoll'):

    class Epoll(_BasePollEpoll):
        """epoll() based poller."""

        READ = select.EPOLLIN
        WRITE = select.EPOLLOUT
        _ERROR = select.EPOLLERR | select.EPOLLHUP
        _poller = select.epoll

        def close(self):
            _IOLoop.close(self)
            self._poller.close()


# ===================================================================
# --- kqueue() - BSD / OSX
# ===================================================================

if hasattr(select, 'kqueue'):

    class Kqueue(_IOLoop):
        """kqueue() based poller."""

        def __init__(self):
            _IOLoop.__init__(self)
            self._kqueue = select.kqueue()
            self._active = {}

        def close(self):
            _IOLoop.close(self)
            self._kqueue.close()

        def register(self, fd, instance, events):
            self.socket_map[fd] = instance
            self._control(fd, events, select.KQ_EV_ADD)
            self._active[fd] = events

        def unregister(self, fd):
            try:
                del self.socket_map[fd]
                events = self._active.pop(fd)
            except KeyError:
                pass
            else:
                try:
                    self._control(fd, events, select.KQ_EV_DELETE)
                except OSError:
                    err = sys.exc_info()[1]
                    if err.errno != errno.EBADF:
                        raise

        def modify(self, fd, events):
            instance = self.socket_map[fd]
            self.unregister(fd)
            self.register(fd, instance, events)

        def _control(self, fd, events, flags):
            kevents = []
            if events & self.WRITE:
                kevents.append(select.kevent(
                        fd, filter=select.KQ_FILTER_WRITE, flags=flags))
            if events & self.READ or not kevents:
                # always read when there is not a write
                kevents.append(select.kevent(
                        fd, filter=select.KQ_FILTER_READ, flags=flags))
            # even though control() takes a list, it seems to return
            # EINVAL on Mac OS X (10.6) when there is more than one
            # event in the list
            for kevent in kevents:
                self._kqueue.control([kevent], 0)

        # localize variable access to minimize overhead
        def poll(self, timeout,
                       _len=len,
                       _READ=select.KQ_FILTER_READ,
                       _WRITE=select.KQ_FILTER_WRITE,
                       _EOF=select.KQ_EV_EOF,
                       _ERROR=select.KQ_EV_ERROR):
            kevents = self._kqueue.control(None, _len(self.socket_map), timeout)
            for kevent in kevents:
                inst = self.socket_map.get(kevent.ident)
                if inst is None:
                    continue
                if kevent.filter == _READ:
                    if inst.readable():
                        _read(inst)
                if kevent.filter == _WRITE:
                    if kevent.flags & _EOF:
                        # If an asynchronous connection is refused,
                        # kqueue returns a write event with the EOF
                        # flag set.
                        # Note that for read events, EOF may be returned
                        # before all data has been consumed from the
                        # socket buffer, so we only check for EOF on
                        # write events.
                        inst.handle_close()
                    else:
                        if inst.writable():
                            _write(inst)
                if kevent.flags & _ERROR:
                    inst.handle_close()


# ===================================================================
# --- choose the better poller for this platform
# ===================================================================

if hasattr(select, 'epoll'):     # epoll() - Linux only
    IOLoop = Epoll
elif hasattr(select, 'kqueue'):  # kqueue() - BSD / OSX
    IOLoop = Kqueue
elif hasattr(select, 'poll'):    # poll()- POSIX
    IOLoop = Poll
else:                            # select() - POSIX and Windows
    IOLoop = Select


# ===================================================================
# --- asyncore dispatchers
# ===================================================================

# these are overridden in order to register() and unregister()
# file descriptors against the new pollers

class Acceptor(asyncore.dispatcher):

    def __init__(self, ioloop=None):
        self.ioloop = ioloop or IOLoop.instance()
        asyncore.dispatcher.__init__(self)

    def add_channel(self, map=None):
        self.ioloop.register(self._fileno, self, self.ioloop.READ)

    def del_channel(self, map=None):
        self.ioloop.unregister(self._fileno)

    def bind_af_unspecified(self, addr):
        """Same as bind() but guesses address family from addr.
        Return the address family just determined.
        """
        assert self.socket is None
        host, port = addr
        err = "getaddrinfo() returned an empty list"
        info = socket.getaddrinfo(host, port, socket.AF_UNSPEC,
                                  socket.SOCK_STREAM, 0, socket.AI_PASSIVE)
        for res in info:
            self.socket = None
            self.del_channel()
            af, socktype, proto, canonname, sa = res
            try:
                self.create_socket(af, socktype)
                self.set_reuse_addr()
                self.bind(sa)
            except socket.error:
                err = sys.exc_info()[1]
                if self.socket is not None:
                    self.socket.close()
                    self.del_channel()
                continue
            break
        if self.socket is None:
            self.del_channel()
            raise socket.error(err)
        return af

    def listen(self, num):
        asyncore.dispatcher.listen(self, num)
        # XXX - this seems to be necessary, otherwise kqueue.control()
        # won't return listening fd events
        try:
            if isinstance(self.ioloop, Kqueue):
                self.ioloop.modify(self._fileno, self.ioloop.READ)
        except NameError:
            pass

    def handle_accept(self):
        try:
            sock, addr = self.accept()
        except TypeError:
            # sometimes accept() might return None (see issue 91)
            return
        except socket.error:
            err = sys.exc_info()[1]
            # ECONNABORTED might be thrown on *BSD (see issue 105)
            if err.args[0] != errno.ECONNABORTED:
                raise
        else:
            # sometimes addr == None instead of (ip, port) (see issue 104)
            if addr is not None:
                self.handle_accepted(sock, addr)

    def handle_accepted(self, sock, addr):
        sock.close()
        self.log_info('unhandled accepted event', 'warning')

    # overridden for convenience; avoid to reuse address on Windows
    if (os.name in ('nt', 'ce')) or (sys.platform == 'cygwin'):
        def set_reuse_addr(self):
            pass


class Connector(Acceptor):

    def add_channel(self, map=None):
        self.ioloop.register(self._fileno, self, self.ioloop.WRITE)

    def connect_af_unspecified(self, addr, source_address=None):
        """Same as connect() but guesses address family from addr.
        Return the address family just determined.
        """
        assert self.socket is None
        host, port = addr
        err = "getaddrinfo() returned an empty list"
        info = socket.getaddrinfo(host, port, socket.AF_UNSPEC,
                                  socket.SOCK_STREAM, 0, socket.AI_PASSIVE)
        for res in info:
            self.socket = None
            af, socktype, proto, canonname, sa = res
            try:
                self.create_socket(af, socktype)
                if source_address:
                    self.bind(source_address)
                self.connect((host, port))
            except socket.error:
                err = sys.exc_info()[1]
                if self.socket is not None:
                    self.socket.close()
                    self.del_channel()
                continue
            break
        if self.socket is None:
            self.del_channel()
            raise socket.error(err)
        return af


class AsyncChat(asynchat.async_chat):

    def __init__(self, sock, ioloop=None):
        self.ioloop = ioloop or IOLoop.instance()
        self._current_io_events = self.ioloop.READ
        self._closed = False
        self._closing = False
        asynchat.async_chat.__init__(self, sock)

    def add_channel(self, map=None, events=None):
        self.ioloop.register(self._fileno, self, events or self.ioloop.READ)

    def del_channel(self, map=None):
        self.ioloop.unregister(self._fileno)

    def initiate_send(self):
        asynchat.async_chat.initiate_send(self)
        if not self._closed:
            # if there's still data to send we want to be ready
            # for writing, else we're only intereseted in reading
            if not self.producer_fifo:
                wanted = self.ioloop.READ
            else:
                wanted = self.ioloop.READ | self.ioloop.WRITE
            if self._current_io_events != wanted:
                self.ioloop.modify(self._fileno, wanted)
                self._current_io_events = wanted

    def close_when_done(self):
        if len(self.producer_fifo) == 0:
            self.handle_close()
        else:
            self._closing = True
            asynchat.async_chat.close_when_done(self)
