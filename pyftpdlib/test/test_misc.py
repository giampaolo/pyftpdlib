# Copyright (C) 2007 Giampaolo Rodola' <g.rodola@gmail.com>.
# Use of this source code is governed by MIT license that can be
# found in the LICENSE file.

import os
import warnings


try:
    from StringIO import StringIO as BytesIO
except ImportError:
    from io import BytesIO

import pytest

import pyftpdlib
from pyftpdlib import __ver__
from pyftpdlib.__main__ import main
from pyftpdlib._compat import PY3
from pyftpdlib._compat import super
from pyftpdlib.authorizers import DummyAuthorizer
from pyftpdlib.servers import FTPServer
from pyftpdlib.test import PyftpdlibTestCase


class TestCommandLineParser(PyftpdlibTestCase):
    """Test command line parser."""

    def setUp(self):
        super().setUp()

        class DummyFTPServer(FTPServer):
            """An overridden version of FTPServer class which forces
            serve_forever() to return immediately.
            """

            def serve_forever(self, *args, **kwargs):
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

    def test_interface_opt(self):
        # no param
        with pytest.raises(SystemExit) as cm:
            main(["-i"])
        with pytest.raises(SystemExit) as cm:
            main(["--interface"])
        ftpd = main(["--interface", "127.0.0.1"])

    def test_port_opt(self):
        # no param
        with pytest.raises(SystemExit) as cm:
            main(["-p"])
        # not an int
        with pytest.raises(SystemExit) as cm:
            main(["-p", "foo"])
        main(["-p", "0"])
        main(["--port", "0"])

    def test_write_opt(self):
        with warnings.catch_warnings():
            warnings.filterwarnings("error")
            with pytest.raises(RuntimeWarning):
                main(["-w", "-p", "0"])

        with warnings.catch_warnings():
            ftpd = main(["-w", "-p", "0"])
            perms = ftpd.handler.authorizer.get_perms("anonymous")
            assert (
                perms
                == DummyAuthorizer.read_perms + DummyAuthorizer.write_perms
            )

        # unexpected argument
        with pytest.raises(SystemExit):
            main(["-w", "foo", "-p", "0"])

    def test_directory_opt(self):
        dirname = self.get_testfn()
        os.mkdir(dirname)
        ftpd = main(["-d", dirname, "-p", "0"])
        ftpd = main(["--directory", dirname, "-p", "0"])
        assert ftpd.handler.authorizer.get_home_dir(
            "anonymous"
        ) == os.path.abspath(dirname)

        # without argument
        with pytest.raises(SystemExit):
            main(["-d"])

        # no such directory
        with pytest.raises(ValueError, match="no such directory"):
            main(["-d", "?!?"])

    def test_nat_address_opt(self):
        ftpd = main(["-n", "127.0.0.1"])
        assert ftpd.handler.masquerade_address == "127.0.0.1"
        ftpd = main(["--nat-address", "127.0.0.1"])
        assert ftpd.handler.masquerade_address == "127.0.0.1"
        # without argument
        with pytest.raises(SystemExit):
            main(["-n"])

    def test_range_opt(self):
        ftpd = main(["-r", "60000-61000"])
        assert ftpd.handler.passive_ports == list(range(60000, 61000 + 1))

        # without arg
        with pytest.raises(SystemExit):
            main(["-r"])
        # wrong arg
        with pytest.raises(SystemExit):
            main(["-r", "yyy-zzz"])

    def test_debug_opt(self):
        main(["-D"])
        main(["--debug"])
        # with arg
        with pytest.raises(SystemExit):
            main(["-D", "xxx"])

    def test_version_opt(self):
        for opt in ("-v", "--version"):
            with pytest.raises(SystemExit) as cm:
                main([opt])
            assert str(cm.exception) == "pyftpdlib %s" % __ver__

    def test_verbose_opt(self):
        for opt in ("-V", "--verbose"):
            main([opt])

    def test_username_and_password_opt(self):
        ftpd = main(["--username", "foo", "--password", "bar"])
        assert ftpd.handler.authorizer.has_user("foo")
        # no --password
        with pytest.raises(SystemExit) as cm:
            main(["--username", "foo"])
