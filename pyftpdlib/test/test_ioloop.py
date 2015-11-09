#!/usr/bin/env python

# Copyright (C) 2007-2016 Giampaolo Rodola' <g.rodola@gmail.com>.
# Use of this source code is governed by MIT license that can be
# found in the LICENSE file.

import contextlib
import socket
import time

from pyftpdlib.ioloop import AsyncChat
from pyftpdlib.ioloop import IOLoop
from pyftpdlib.test import POSIX
from pyftpdlib.test import unittest
from pyftpdlib.test import VERBOSITY
import pyftpdlib.ioloop


if hasattr(socket, 'socketpair'):
    socketpair = socket.socketpair
else:
    def socketpair(family=socket.AF_INET, type=socket.SOCK_STREAM, proto=0):
        with contextlib.closing(socket.socket(family, type, proto)) as l:
            l.bind(("localhost", 0))
            l.listen()
            c = socket.socket(family, type, proto)
            try:
                c.connect(l.getsockname())
                caddr = c.getsockname()
                while True:
                    a, addr = l.accept()
                    # check that we've got the correct client
                    if addr == caddr:
                        return c, a
                    a.close()
            except OSError:
                c.close()
                raise


# TODO: write more tests.
class BaseIOLoopTestCase(object):

    ioloop_class = None

    def make_socketpair(self):
        rd, wr = socketpair()
        self.addCleanup(rd.close)
        self.addCleanup(wr.close)
        return rd, wr

    def test_register(self):
        s = self.ioloop_class()
        self.addCleanup(s.close)
        rd, wr = self.make_socketpair()
        handler = AsyncChat(rd)
        s.register(rd, handler, s.READ)
        s.register(wr, handler, s.WRITE)
        self.assertIn(rd, s.socket_map)
        self.assertIn(wr, s.socket_map)
        return (s, rd, wr)

    def test_unregister(self):
        s, rd, wr = self.test_register()
        s.unregister(rd)
        s.unregister(wr)
        self.assertNotIn(rd, s.socket_map)
        self.assertNotIn(wr, s.socket_map)

    def test_unregister_twice(self):
        s, rd, wr = self.test_register()
        s.unregister(rd)
        s.unregister(rd)
        s.unregister(wr)
        s.unregister(wr)

    def test_modify(self):
        s, rd, wr = self.test_register()
        s.modify(rd, s.WRITE)
        s.modify(wr, s.READ)

    def test_close(self):
        s, rd, wr = self.test_register()
        s.close()
        self.assertEqual(s.socket_map, {})


class DefaultIOLoopTestCase(unittest.TestCase, BaseIOLoopTestCase):
    ioloop_class = pyftpdlib.ioloop.IOLoop


class SelectIOLoopTestCase(unittest.TestCase, BaseIOLoopTestCase):
    ioloop_class = pyftpdlib.ioloop.Select


@unittest.skipUnless(hasattr(pyftpdlib.ioloop, 'Poll'),
                     "poll() not available on this platform")
class PollIOLoopTestCase(unittest.TestCase, BaseIOLoopTestCase):
    ioloop_class = getattr(pyftpdlib.ioloop, "Poll", None)


@unittest.skipUnless(hasattr(pyftpdlib.ioloop, 'Epoll'),
                     "epoll() not available on this platform (Linux only)")
class EpollIOLoopTestCase(unittest.TestCase, BaseIOLoopTestCase):
    ioloop_class = getattr(pyftpdlib.ioloop, "Epoll", None)


@unittest.skipUnless(hasattr(pyftpdlib.ioloop, 'DevPoll'),
                     "/dev/poll not available on this platform (Solaris only)")
class DevPollIOLoopTestCase(unittest.TestCase, BaseIOLoopTestCase):
    ioloop_class = getattr(pyftpdlib.ioloop, "DevPoll", None)


@unittest.skipUnless(hasattr(pyftpdlib.ioloop, 'Kqueue'),
                     "/dev/poll not available on this platform (BSD only)")
class KqueueIOLoopTestCase(unittest.TestCase, BaseIOLoopTestCase):
    ioloop_class = getattr(pyftpdlib.ioloop, "Kqueue", None)


class TestCallLater(unittest.TestCase):
    """Tests for CallLater class."""

    def setUp(self):
        self.ioloop = IOLoop.instance()
        for task in self.ioloop.sched._tasks:
            if not task.cancelled:
                task.cancel()
        del self.ioloop.sched._tasks[:]

    def scheduler(self, timeout=0.01, count=100):
        while self.ioloop.sched._tasks and count > 0:
            self.ioloop.sched.poll()
            count -= 1
            time.sleep(timeout)

    def test_interface(self):
        def fun():
            return 0

        self.assertRaises(AssertionError, self.ioloop.call_later, -1, fun)
        x = self.ioloop.call_later(3, fun)
        self.assertEqual(x.cancelled, False)
        x.cancel()
        self.assertEqual(x.cancelled, True)
        self.assertRaises(AssertionError, x.call)
        self.assertRaises(AssertionError, x.reset)
        x.cancel()

    def test_order(self):
        def fun(x):
            l.append(x)

        l = []
        for x in [0.05, 0.04, 0.03, 0.02, 0.01]:
            self.ioloop.call_later(x, fun, x)
        self.scheduler()
        self.assertEqual(l, [0.01, 0.02, 0.03, 0.04, 0.05])

    # The test is reliable only on those systems where time.time()
    # provides time with a better precision than 1 second.
    if not str(time.time()).endswith('.0'):
        def test_reset(self):
            def fun(x):
                l.append(x)

            l = []
            self.ioloop.call_later(0.01, fun, 0.01)
            self.ioloop.call_later(0.02, fun, 0.02)
            self.ioloop.call_later(0.03, fun, 0.03)
            x = self.ioloop.call_later(0.04, fun, 0.04)
            self.ioloop.call_later(0.05, fun, 0.05)
            time.sleep(0.1)
            x.reset()
            self.scheduler()
            self.assertEqual(l, [0.01, 0.02, 0.03, 0.05, 0.04])

    def test_cancel(self):
        def fun(x):
            l.append(x)

        l = []
        self.ioloop.call_later(0.01, fun, 0.01).cancel()
        self.ioloop.call_later(0.02, fun, 0.02)
        self.ioloop.call_later(0.03, fun, 0.03)
        self.ioloop.call_later(0.04, fun, 0.04)
        self.ioloop.call_later(0.05, fun, 0.05).cancel()
        self.scheduler()
        self.assertEqual(l, [0.02, 0.03, 0.04])

    def test_errback(self):
        l = []
        self.ioloop.call_later(
            0.0, lambda: 1 // 0, _errback=lambda: l.append(True))
        self.scheduler()
        self.assertEqual(l, [True])


class TestCallEvery(unittest.TestCase):
    """Tests for CallEvery class."""

    def setUp(self):
        self.ioloop = IOLoop.instance()
        for task in self.ioloop.sched._tasks:
            if not task.cancelled:
                task.cancel()
        del self.ioloop.sched._tasks[:]

    def scheduler(self, timeout=0.003):
        stop_at = time.time() + timeout
        while time.time() < stop_at:
            self.ioloop.sched.poll()

    def test_interface(self):
        def fun():
            return 0

        self.assertRaises(AssertionError, self.ioloop.call_every, -1, fun)
        x = self.ioloop.call_every(3, fun)
        self.assertEqual(x.cancelled, False)
        x.cancel()
        self.assertEqual(x.cancelled, True)
        self.assertRaises(AssertionError, x.call)
        self.assertRaises(AssertionError, x.reset)
        x.cancel()

    def test_only_once(self):
        # make sure that callback is called only once per-loop
        def fun():
            l1.append(None)

        l1 = []
        self.ioloop.call_every(0, fun)
        self.ioloop.sched.poll()
        self.assertEqual(l1, [None])

    def test_multi_0_timeout(self):
        # make sure a 0 timeout callback is called as many times
        # as the number of loops
        def fun():
            l.append(None)

        l = []
        self.ioloop.call_every(0, fun)
        for x in range(100):
            self.ioloop.sched.poll()
        self.assertEqual(len(l), 100)

    # run it on systems where time.time() has a higher precision
    if POSIX:
        def test_low_and_high_timeouts(self):
            # make sure a callback with a lower timeout is called more
            # frequently than another with a greater timeout
            def fun():
                l1.append(None)

            l1 = []
            self.ioloop.call_every(0.001, fun)
            self.scheduler()

            def fun():
                l2.append(None)

            l2 = []
            self.ioloop.call_every(0.005, fun)
            self.scheduler(timeout=0.01)

            self.assertTrue(len(l1) > len(l2))

    def test_cancel(self):
        # make sure a cancelled callback doesn't get called anymore
        def fun():
            l.append(None)

        l = []
        call = self.ioloop.call_every(0.001, fun)
        self.scheduler()
        len_l = len(l)
        call.cancel()
        self.scheduler()
        self.assertEqual(len_l, len(l))

    def test_errback(self):
        l = []
        self.ioloop.call_every(
            0.0, lambda: 1 // 0, _errback=lambda: l.append(True))
        self.scheduler()
        self.assertTrue(l)


if __name__ == '__main__':
    unittest.main(verbosity=VERBOSITY)
