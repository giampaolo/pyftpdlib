# Copyright (C) 2007 Giampaolo Rodola' <g.rodola@gmail.com>.
# Use of this source code is governed by MIT license that can be
# found in the LICENSE file.

import argparse
import io
import os
import warnings
from unittest.mock import patch

import pytest

import pyftpdlib
from pyftpdlib.__main__ import main
from pyftpdlib.authorizers import DummyAuthorizer
from pyftpdlib.handlers import TLS_FTPHandler
from pyftpdlib.servers import FTPServer
from pyftpdlib.servers import ThreadedFTPServer

from . import CERTFILE
from . import PyftpdlibTestCase
from . import reset_server_opts


class DummyFTPServer(FTPServer):
    """An overridden version of FTPServer class which forces
    serve_forever() to return immediately.
    """

    def serve_forever(self, *args, **kwargs):
        self.close_all()


class DummyThreadedFTPServer(DummyFTPServer):
    pass


class TestCommandLineParser(PyftpdlibTestCase):
    """Test command line parser."""

    def setUp(self):
        super().setUp()

        self.devnull = io.BytesIO()
        self.original_ftpserver_class = FTPServer
        self.original_threaded_ftpserver_class = ThreadedFTPServer
        self.clog = patch("pyftpdlib.__main__.config_logging")
        self.clog.start()
        pyftpdlib.__main__.servers.FTPServer = DummyFTPServer
        pyftpdlib.__main__.servers.ThreadedFTPServer = DummyThreadedFTPServer

    def tearDown(self):
        self.clog.stop()
        pyftpdlib.servers.FTPServer = self.original_ftpserver_class
        pyftpdlib.servers.ThreadedFTPServer = (
            self.original_threaded_ftpserver_class
        )
        super().tearDown()

    def test_interface_opt(self):
        # no param
        with pytest.raises(SystemExit):
            main(["-i"])
        with pytest.raises(SystemExit):
            main(["--interface"])
        main(["--interface", "127.0.0.1", "-p", "0"])

    def test_port_opt(self):
        # no param
        with pytest.raises(SystemExit):
            main(["-p"])
        # not an int
        with pytest.raises(SystemExit):
            main(["-p", "foo"])
        main(["-p", "0"])
        main(["--port", "0"])

    def test_write_opt(self):
        with warnings.catch_warnings():
            warnings.filterwarnings("error")
            with pytest.raises(RuntimeWarning):
                main(["-w", "-p", "0"])

        with warnings.catch_warnings():
            warnings.filterwarnings("ignore")
            ftpd = main(["-w", "-p", "0"])
            perms = ftpd.handler.authorizer.get_perms("anonymous")
            assert (
                perms
                == DummyAuthorizer.read_perms + DummyAuthorizer.write_perms
            )

        # unexpected argument
        with warnings.catch_warnings():
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
            main(["-d", "?!?", "-p", "0"])

    def test_nat_address_opt(self):
        ftpd = main(["-n", "127.0.0.1", "-p", "0"])
        assert ftpd.handler.masquerade_address == "127.0.0.1"
        ftpd.close_all()
        ftpd = main(["--nat-address", "127.0.0.1", "-p", "0"])
        ftpd.close_all()
        assert ftpd.handler.masquerade_address == "127.0.0.1"
        # without argument
        with pytest.raises(SystemExit):
            main(["-n", "-p", "0"])

    def test_range_opt(self):
        ftpd = main(["-r", "60000-61000", "-p", "0"])
        assert ftpd.handler.passive_ports == list(range(60000, 61000 + 1))

        # without arg
        with pytest.raises(SystemExit):
            main(["-r"])
        # wrong arg
        with pytest.raises(SystemExit):
            main(["-r", "yyy-zzz"])

    def test_debug_opt(self):
        main(["-D", "-p", "0"])
        main(["--debug", "-p", "0"])
        # with arg
        with pytest.raises(SystemExit):
            main(["-D", "xxx"])

    def test_username_and_password_opt(self):
        ftpd = main(["--username", "foo", "--password", "bar", "-p", "0"])
        assert ftpd.handler.authorizer.has_user("foo")
        # no --password
        with pytest.raises(argparse.ArgumentTypeError):
            main(["--username", "foo"])

    def test_concurrency(self):
        ftpd = main(["--concurrency", "multi-thread"])
        assert isinstance(ftpd, DummyThreadedFTPServer)

    def test_timeout(self):
        ftpd = main(["--timeout", "10"])
        assert ftpd.handler.timeout == 10

    def test_banner(self):
        ftpd = main(["--banner", "hello there"])
        assert ftpd.handler.banner == "hello there"

    def test_permit_foreign_addresses(self):
        ftpd = main(["--permit-foreign-addresses"])
        assert ftpd.handler.permit_foreign_addresses is True

    def test_permit_privileged_ports(self):
        ftpd = main(["--permit-privileged-ports"])
        assert ftpd.handler.permit_privileged_ports is True

    def test_encoding(self):
        ftpd = main(["--encoding", "ascii"])
        assert ftpd.handler.encoding == "ascii"

    def test_use_localtime(self):
        ftpd = main(["--use-localtime"])
        assert ftpd.handler.use_gmt_times is False

    @pytest.mark.skipif(
        not hasattr(os, "sendfile"), reason="sendfile() not supported"
    )
    def test_disable_sendfile(self):
        ftpd = main(["--disable-sendfile"])
        assert ftpd.handler.use_sendfile is False

    def test_max_cons(self):
        ftpd = main(["--max-cons", "10"])
        assert ftpd.max_cons == 10

    def test_max_cons_per_ip(self):
        ftpd = main(["--max-cons-per-ip", "10"])
        assert ftpd.max_cons_per_ip == 10

    def test_max_login_attempts(self):
        ftpd = main(["--max-login-attempts", "10"])
        assert ftpd.handler.max_login_attempts == 10

    def test_tls(self):
        with pytest.raises(argparse.ArgumentTypeError) as cm:
            main(["--tls"])
        assert cm.match("requires")
        assert cm.match("--keyfile")
        assert cm.match("--certfile")

        ftpd = main(["--tls", "--keyfile", CERTFILE, "--certfile", CERTFILE])
        assert issubclass(ftpd.handler, TLS_FTPHandler)
        assert ftpd.handler.keyfile == CERTFILE
        assert ftpd.handler.certfile == CERTFILE

    def test_tls_required(self):
        ftpd = main(["--tls", "--keyfile", CERTFILE, "--certfile", CERTFILE])
        assert ftpd.handler.tls_control_required is False
        assert ftpd.handler.tls_data_required is False

        ftpd = main([
            "--tls",
            "--keyfile",
            CERTFILE,
            "--certfile",
            CERTFILE,
            "--tls-control-required",
        ])
        assert ftpd.handler.tls_control_required is True
        assert ftpd.handler.tls_data_required is False

        reset_server_opts()

        ftpd = main([
            "--tls",
            "--keyfile",
            CERTFILE,
            "--certfile",
            CERTFILE,
            "--tls-data-required",
        ])
        assert ftpd.handler.tls_control_required is False
        assert ftpd.handler.tls_data_required is True
