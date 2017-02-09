#!/usr/bin/env python

# Copyright (C) 2007 Giampaolo Rodola' <g.rodola@gmail.com>.
# Use of this source code is governed by MIT license that can be
# found in the LICENSE file.

from pyftpdlib.test import unittest
from pyftpdlib.test import VERBOSITY
from pyftpdlib.test import ThreadWorker


class TestThreadWorker(unittest.TestCase):

    def test_callback_methods(self):
        class Worker(ThreadWorker):

            def poll(self):
                if 'poll' not in flags:
                    flags.append('poll')

            def before_start(self):
                flags.append('before_start')

            def before_stop(self):
                flags.append('before_stop')

            def after_stop(self):
                flags.append('after_stop')

        # Stress test it a little to make sure there are no race conditions
        # between locks: the order is always supposed to be the same, no
        # matter what.
        for x in range(100):
            flags = []
            tw = Worker(0.001)
            tw.start()
            tw.stop()
            self.assertEqual(
                flags, ['before_start', 'poll', 'before_stop', 'after_stop'])


if __name__ == '__main__':
    unittest.main(verbosity=VERBOSITY)
