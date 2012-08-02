#!/usr/bin/env python
# $Id$

#  ======================================================================
#  Copyright (C) 2007-2012 Giampaolo Rodola' <g.rodola@gmail.com>
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

"""
This module contains two FTPServer subclasses changing the asynchronous
concurrency model used natively by pyftpdlib.

You might be interested in these in case your code contains blocking
parts which cannot be adapted to the base async model or if the
underlying filesystem is particularly slow, see:

https://code.google.com/p/pyftpdlib/issues/detail?id=197
https://code.google.com/p/pyftpdlib/issues/detail?id=212

Two classes are provided:

 - ThreadingFTPServer
 - MultiprocessFTPServer

...spawning a new thread or process every time a client connects.

The main thread will be async-based and be used only to accept new
connections (not handling them).
Every time a new connection comes in that will be dispatched to a
separate thread/process which internally will run its own IO loop.
This way the handler handling that connections will be free to block
without hanging the whole FTP server.

Example usage:

>>> from pyftpdlib import ftpserver
>>> from pyftpdlib.contrib.servers import ThreadedFTPServer
>>>
>>> authorizer = ftpserver.DummyAuthorizer()
>>> handler = ftpserver.FTPHandler
>>> handler.authorizer = authorizer
>>> server = ThreadedFTPServer(('', 21), handler)
>>> server.serve_forever()
"""

from pyftpdlib.ftpserver import FTPServer as _FTPServer
from pyftpdlib.lib.ioloop import IOLoop

__all__ = []


class _Base(_FTPServer):
    """Base class shared by both implementations (not supposed to be used)"""
    poll_timeout = 1.0
    _lock = None

    def __init__(self, address, handler, ioloop=None):
        _FTPServer.__init__(self, address, handler, ioloop)
        self._serving = False
        self._active_tasks = []

    def _start_task(self, *args, **kwargs):
        raise NotImplementedError('must be implemented in subclass')

    def _current_task(self):
        raise NotImplementedError('must be implemented in subclass')

    def _map_len(self):
        raise NotImplementedError('must be implemented in subclass')

    def _loop(self, ioloop):
        # this loop will live in a separate thread/process
        poll = ioloop.poll
        socket_map = ioloop.socket_map
        tasks = ioloop.sched._tasks
        sched_poll = ioloop.sched.poll
        timeout = self.poll_timeout
        while self._serving and socket_map:
            poll(timeout=timeout)
            if tasks:
                sched_poll()

        self._lock.acquire()
        try:
            self._active_tasks.remove(self._current_task())
        except ValueError:
            pass
        self._lock.release()

        ioloop.close()

    def handle_accepted(self, sock, addr):
        handler = _FTPServer.handle_accepted(self, sock, addr)
        if handler is not None:
            # unregister the handler from the main IOLoop used by the
            # main thread to accept connection, then instantiate a new
            # IOLoop and make that loop into a separate thread
            self.ioloop.unregister(handler._fileno)
            ioloop = IOLoop()
            handler.ioloop = ioloop
            handler.add_channel()

            t = self._start_task(target=self._loop, args=(ioloop,))
            t.start()
            self._lock.acquire()
            self._active_tasks.append(t)
            self._lock.release()

    def serve_forever(self, timeout=None, blocking=True):
        self._serving = True
        try:
            _FTPServer.serve_forever(self, timeout, blocking)
        finally:
            if blocking:
                self.close_all()

    def close_all(self):
        self._serving = False
        for t in self._active_tasks:
            if hasattr(t, 'terminate'):
                t.terminate()
            t.join()
        del self._active_tasks[:]
        _FTPServer.close_all(self)

try:
    import threading
except ImportError:
    pass
else:
    __all__ += ['ThreadedFTPServer']

    class ThreadedFTPServer(_Base):
        """A modified version of base FTPServer class which spawns a
        thread every time a new connection is established.
        """
        _lock = threading.Lock()

        def _start_task(self, *args, **kwargs):
            return threading.Thread(*args, **kwargs)

        def _current_task(self):
            return threading.current_thread()

        def _map_len(self):
            return threading.active_count()

try:
    import multiprocessing
except ImportError:
    pass
else:
    __all__ += ['MultiprocessFTPServer']

    class MultiprocessFTPServer(_Base):
        """A modified version of base FTPServer class which spawns a
        process every time a new connection is established.
        """
        _lock = multiprocessing.Lock()

        def _start_task(self, *args, **kwargs):
            return multiprocessing.Process(*args, **kwargs)

        def _current_task(self):
            return multiprocessing.current_process()

        def _map_len(self):
            return len(multiprocessing.active_children())
