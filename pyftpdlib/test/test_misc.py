# Copyright (C) 2007 Giampaolo Rodola' <g.rodola@gmail.com>.
# Use of this source code is governed by MIT license that can be
# found in the LICENSE file.

import logging
import os
import sys
import warnings

from pyftpdlib.authorizers import DummyAuthorizer


try:
    from StringIO import StringIO as BytesIO
except ImportError:
    from io import BytesIO

import pyftpdlib
from pyftpdlib.__main__ import main
from pyftpdlib._compat import PY3
from pyftpdlib._compat import super
from pyftpdlib.servers import FTPServer
from pyftpdlib.test import PyftpdlibTestCase
from pyftpdlib.test import mock
from pyftpdlib.test import safe_rmpath


class TestCommandLineParser(PyftpdlibTestCase):
    """Test command line parser."""

    def setUp(self):
        super().setUp()

        class DummyFTPServer(FTPServer):
            """An overridden version of FTPServer class which forces
            serve_forever() to return immediately.
            """

            started = False

            def serve_forever(self, *args, **kwargs):
                self.started = True
                return

        if PY3:
            import io

            self.devnull = io.StringIO()
        else:
            self.devnull = BytesIO()
        self.original_ftpserver_class = FTPServer
        pyftpdlib.__main__.FTPServer = DummyFTPServer

    def tearDown(self):
        self.devnull.close()
        pyftpdlib.servers.FTPServer = self.original_ftpserver_class
        super().tearDown()

    def test_port_opt(self):
        # no param
        with self.assertRaises(SystemExit) as cm:
            main(["-p"])
        # not an int
        with self.assertRaises(SystemExit) as cm:
            main(["-p", "foo"])
        main(["-p", "0"])
        main(["--port", "0"])

    def test_write_opt(self):
        with warnings.catch_warnings():
            warnings.filterwarnings("error")
            with self.assertRaises(RuntimeWarning):
                main(["-w", "-p", "0"])

        with warnings.catch_warnings():
            ftpd = main(["-w", "-p", "0"])
            perms = ftpd.handler.authorizer.get_perms("anonymous")
            self.assertEqual(
                perms, DummyAuthorizer.read_perms + DummyAuthorizer.write_perms
            )

        # unexpected argument
        self.assertRaises(SystemExit, main, ["-w", "foo", "-p", "0"])

    def test_d_option(self):
        dirname = self.get_testfn()
        os.mkdir(dirname)
        sys.argv += ["-d", dirname, "-p", "0"]
        pyftpdlib.__main__.main()

        # without argument
        sys.argv = self.SYSARGV[:]
        sys.argv += ["-d"]
        sys.stderr = self.devnull
        self.assertRaises(SystemExit, pyftpdlib.__main__.main)

        # no such directory
        sys.argv = self.SYSARGV[:]
        sys.argv += ["-d %s" % dirname]
        safe_rmpath(dirname)
        self.assertRaises(ValueError, pyftpdlib.__main__.main)

    def test_r_option(self):
        sys.argv += ["-r 60000-61000", "-p", "0"]
        pyftpdlib.__main__.main()

        # without arg
        sys.argv = self.SYSARGV[:]
        sys.argv += ["-r"]
        sys.stderr = self.devnull
        self.assertRaises(SystemExit, pyftpdlib.__main__.main)

        # wrong arg
        sys.argv = self.SYSARGV[:]
        sys.argv += ["-r yyy-zzz"]
        self.assertRaises(SystemExit, pyftpdlib.__main__.main)

    def test_v_option(self):
        sys.argv += ["-v"]
        self.assertRaises(SystemExit, pyftpdlib.__main__.main)

        # unexpected argument
        sys.argv = self.SYSARGV[:]
        sys.argv += ["-v foo"]
        sys.stderr = self.devnull
        self.assertRaises(SystemExit, pyftpdlib.__main__.main)

    def test_D_option(self):
        with mock.patch('pyftpdlib.__main__.config_logging') as fun:
            sys.argv += ["-D", "-p 0"]
            pyftpdlib.__main__.main()
            fun.assert_called_once_with(level=logging.DEBUG)

        # unexpected argument
        sys.argv = self.SYSARGV[:]
        sys.argv += ["-V foo"]
        sys.stderr = self.devnull
        self.assertRaises(SystemExit, pyftpdlib.__main__.main)


if __name__ == '__main__':
    from pyftpdlib.test.runner import run_from_name

    run_from_name(__file__)
