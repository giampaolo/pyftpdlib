"""
test run a ftpserver using with statement
"""

import random

from ftplib import FTP

from pyftpdlib.servers import FTPServer, FTPServerContext
from pyftpdlib.authorizers import DummyAuthorizer
from pyftpdlib.handlers import FTPHandler

from pyftpdlib.test import PyftpdlibTestCase
from pyftpdlib.test import unittest


# logging.basicConfig(level=logging.INFO)


class ContextServerTest(PyftpdlibTestCase):

    def test_context(self):
        port = random.randint(10000, 20000)
        authorizer = DummyAuthorizer()
        authorizer.add_anonymous(".")
        handler = FTPHandler
        handler.authorizer = authorizer
        server = FTPServer(("localhost", port), handler)
        with FTPServerContext(server):
            with FTP() as ftp:
                ftp.connect(host='localhost', port=port)
                ftp.login()
                # time.sleep(1)
                print(ftp.dir())
                print("get the directory successfully first time")

    def test_auto_close(self):
        port = random.randint(10000, 20000)
        authorizer = DummyAuthorizer()
        authorizer.add_anonymous(".")
        handler = FTPHandler
        handler.authorizer = authorizer
        server = FTPServer(("localhost", port), handler)
        with FTPServerContext(server):
            with FTP() as ftp:
                ftp.connect(host='localhost', port=port)
                ftp.login()
                # time.sleep(1)
                print(ftp.dir())
                print("get the directory successfully first time")
        with self.assertRaises(ConnectionRefusedError):
            with FTP() as ftp:
                ftp.connect(host='localhost', port=port)
                ftp.login()


if __name__ == "__main__":
    unittest.main()
