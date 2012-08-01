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
"""

import asyncore
import asynchat
import errno
import select
import os
import sys
try:
    import threading
except ImportError:
    import dummy_threading as threading


class _Base(object):
    READ = 1
    WRITE = 2
    _instance = None
    _lock = threading.Lock()

    @classmethod
    def instance(cls):
        if cls._instance is None:
            cls._lock.acquire()
            try:
                cls._instance = cls()
            finally:
                cls._lock.release()
        return cls._instance

    @classmethod
    def close(cls):
        cls._instance = None

_read = asyncore.read
_write = asyncore.write


# ===================================================================
# --- select() - POSIX / Windows
# ===================================================================

class Select(_Base):
    """select()-based poller."""

    def __init__(self):
        self.socket_map = {}
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
        except select.error:
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

class _BasePollEpoll(_Base):
    """This is common to both poll/epoll implementations which
    almost share the same interface.
    Not supposed to be used directly.
    """

    def __init__(self):
        self.socket_map = {}
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
        except select.error:
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
            self._poller.close()
            Epoll._instance = None


# ===================================================================
# --- kqueue() - BSD / OSX
# ===================================================================

if hasattr(select, 'kqueue'):

    class Kqueue(_Base):
        """kqueue() based poller."""
        READ = 1
        WRITE = 2

        def __init__(self):
            self.socket_map = {}
            self._kqueue = select.kqueue()
            self._active = {}

        def close(self):
            self._kqueue.close()
            Kqueue._instance = None

        def register(self, fd, instance, events):
            self.socket_map[fd] = instance
            self._control(fd, events, select.KQ_EV_ADD)
            self._active[fd] = events

        def unregister(self, fd):
            del self.socket_map[fd]
            events = self._active.pop(fd)
            self._control(fd, events, select.KQ_EV_DELETE)

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
    ioloop = Epoll
elif hasattr(select, 'kqueue'):  # kqueue() - BSD / OSX
    ioloop = Kqueue
elif hasattr(select, 'poll'):    # poll()- POSIX
    ioloop = Poll
else:                            # select() - POSIX and Windows
    ioloop = Select


def install(poller):
    """Utility method to install a specific poller."""
    global ioloop
    if ioloop._instance is not None:
        raise ValueError("IO poller must be stopped first")
    ioloop = poller

#install(Epoll)
#install(Kqueue)
#install(Poll)
#install(Select)

# ===================================================================
# --- asyncore dispatchers
# ===================================================================

# these are overridden in order to register() and unregister()
# file descriptors against the new pollers

class Acceptor(asyncore.dispatcher):

    def add_channel(self, map=None):
        io = ioloop.instance()
        io.register(self._fileno, self, io.READ)

    def del_channel(self, map=None):
        ioloop.instance().unregister(self._fileno)
        self._fileno = None

    def listen(self, num):
        asyncore.dispatcher.listen(self, num)
        io = ioloop.instance()
        # XXX - this seems to be necessary, otherwise kqueue.control()
        # won't return listening fd events
        try:
            if isinstance(io, Kqueue):
                io.modify(self._fileno, io.READ)
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
        io = ioloop.instance()
        io.register(self._fileno, self, io.WRITE)


class AsyncChat(asynchat.async_chat):

    def __init__(self, *args, **kwargs):
        self._current_io_events = ioloop.READ
        self._closed = False
        asynchat.async_chat.__init__(self, *args, **kwargs)

    def add_channel(self, map=None):
        io = ioloop.instance()
        io.register(self._fileno, self, io.READ)

    def del_channel(self, map=None):
        ioloop.instance().unregister(self._fileno)
        self._fileno = None

    def initiate_send(self):
        asynchat.async_chat.initiate_send(self)
        if not self._closed:
            # if there's still data to send we want to be ready
            # for writing, else we're only intereseted in reading
            if not self.producer_fifo:
                wanted = ioloop.READ
            else:
                wanted = ioloop.READ | ioloop.WRITE
            if self._current_io_events != wanted:
                ioloop.instance().modify(self._fileno, wanted)
                self._current_io_events = wanted
