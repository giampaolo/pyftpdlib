#!/usr/bin/env python

import ftplib
import time

from pyftpdlib.test import unittest
from pyftpdlib.test import VERBOSITY
from pyftpdlib.test import TIMEOUT
from pyftpdlib.test import configure_logging
from pyftpdlib.test import remove_test_files
from pyftpdlib.test import ThreadedTestFTPd
from pyftpdlib.servers import FTPServer
from pyftpdlib.authorizers import DummyAuthorizer

from demo.anti_flood_ftpd import AntiFloodHandler


class TestAntiFloodFTPD(unittest.TestCase):

    server_class = ThreadedTestFTPd
    client_class = ftplib.FTP

    def setUp(self):
        handler = AntiFloodHandler
        self.server = self.server_class(('', 2121), handler)
        self.server.handler = handler
        with self.server.lock:
            self.server.handler.auth_failed_timeout = 0.001
        self.server.start()
        self.client = self.client_class(timeout=TIMEOUT)

    def tearDown(self):
        self.client.close()
        self.server.stop()

    def test_anti_flood(self):
        self.client.connect('127.0.0.1', 2121)
        self.client.login(user='user', passwd='12345')
        for i in xrange(300):
            self.client.sendcmd('pwd')
        time.sleep(1)
        self.assertRaisesRegex(ftplib.error_perm, '550 You are banned for 3600 seconds.',
                               self.client.sendcmd, 'pwd')


configure_logging()
remove_test_files()


if __name__ == '__main__':
    unittest.main(verbosity=VERBOSITY)
