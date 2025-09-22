# Copyright (C) 2007 Giampaolo Rodola' <g.rodola@gmail.com>.
# Use of this source code is governed by MIT license that can be
# found in the LICENSE file.

"""
Start a standalone anonymous FTP server from the command line:

$ python3 -m pyftpdlib
"""

import argparse
import codecs
import logging
import os

from . import servers
from .authorizers import DummyAuthorizer
from .handlers import FTPHandler
from .log import config_logging
from .utils import hilite
from .utils import term_supports_colors

try:
    from .handlers import TLS_FTPHandler
except ImportError:
    TLS_FTPHandler = None  # requires PyOpenSSL


DEFAULT_PORT = 2121


class ColorHelpFormatter(argparse.HelpFormatter):
    def start_section(self, heading):  # titles / groups
        heading = f"{hilite(heading.capitalize(), 'orange')}"
        super().start_section(heading)

    def _format_action_invocation(self, action):
        # colorize the flag part (e.g. "-i, --interface")
        if not action.option_strings:
            default = self._metavar_formatter(action, action.dest)(1)[0]
            return f"{hilite(default, 'white')}"

        parts = []
        for option in action.option_strings:
            parts.append(f"{hilite(option, 'lightblue')}")

        if action.nargs != 0:
            metavar = self._format_args(
                action, self._get_default_metavar_for_optional(action)
            )
            parts[-1] += " " + f"{hilite(metavar, 'green')}"

        return ", ".join(parts)


def parse_encoding(value):
    try:
        codecs.lookup(value)
    except LookupError:
        raise argparse.ArgumentTypeError(f"unknown encoding: {value!r}")
    return value


def parse_port_range(value):
    try:
        start, stop = value.split('-')
        start, stop = int(start), int(stop)
    except ValueError:
        raise argparse.ArgumentTypeError(
            f"invalid port range: {value!r} (expected FROM-TO)"
        )
    if not (0 <= start <= 65535 and 0 <= stop <= 65535):
        raise argparse.ArgumentTypeError(
            "port numbers must be between 0 and 65535"
        )
    if start >= stop:
        raise argparse.ArgumentTypeError(
            f"start port must be <= stop port (got {start}-{stop})"
        )
    return list(range(start, stop + 1))


def parse_server_type(value):
    if value == "async":
        return servers.FTPServer
    if value == "multi-thread":
        return servers.ThreadedFTPServer
    if value == "multi-proc":
        if not hasattr(servers, "MultiprocessFTPServer"):
            raise argparse.ArgumentTypeError(
                "multi process server is not supported on this platform"
            )
        return servers.MultiprocessFTPServer
    raise argparse.ArgumentTypeError(
        f"invalid concurrency {value!r}; choose between 'async',"
        " 'multi-thread' or 'multi-proc'"
    )


def parse_args(args=None):
    usage = "python3 -m pyftpdlib [options]"
    parser = argparse.ArgumentParser(
        usage=usage,
        description=main.__doc__,
        formatter_class=(
            ColorHelpFormatter
            if term_supports_colors()
            else argparse.HelpFormatter
        ),
    )

    # --- most important opts

    group_main = parser.add_argument_group("Main options")
    group_main.add_argument(
        '-i',
        '--interface',
        default=None,
        metavar="ADDRESS",
        help="specify the interface to run on (default: all interfaces)",
    )
    group_main.add_argument(
        '-p',
        '--port',
        type=int,
        default=DEFAULT_PORT,
        metavar="PORT",
        help=f"specify port number to run on (default: {DEFAULT_PORT})",
    )
    group_main.add_argument(
        '-w',
        '--write',
        action="store_true",
        default=False,
        help="grants write access for logged in user (default: read-only)",
    )
    group_main.add_argument(
        '-d',
        '--directory',
        default=os.getcwd(),
        metavar="PATH",
        help="specify the directory to share (default: current directory)",
    )
    group_main.add_argument(
        '-n',
        '--nat-address',
        default=None,
        metavar="ADDRESS",
        help="the NAT address to use for passive connections",
    )
    group_main.add_argument(
        '-r',
        '--range',
        type=parse_port_range,
        default=None,
        metavar="FROM-TO",
        help=(
            "the range of TCP ports to use for passive "
            "connections (e.g. -r 8000-9000)"
        ),
    )
    group_main.add_argument(
        '-D',
        '--debug',
        action='store_true',
        help="enable DEBUG logging level",
    )
    group_main.add_argument(
        '-u',
        '--username',
        type=str,
        default=None,
        help=(
            "specify username to login with (anonymous login "
            "will be disabled and password required "
            "if supplied)"
        ),
    )
    group_main.add_argument(
        '-P',
        '--password',
        type=str,
        default=None,
        help=(
            "specify a password to login with (username required to be useful)"
        ),
    )
    group_main.add_argument(
        '--concurrency',
        type=parse_server_type,
        default="async",
        help=(
            "the FTP server concurrency model to use, either 'async'"
            " (default), 'multi-thread' or 'multi-proc'"
        ),
    )

    # --- TLS opts

    group_tls = parser.add_argument_group("TLS options")
    group_tls.add_argument(
        "--tls",
        default=False,
        action="store_true",
        help=(
            "whether to enable FTPS (FTP over SSL); requires --keyfile and"
            " --certfile args"
        ),
    )
    group_tls.add_argument(
        '--keyfile',
        metavar="PATH",
        help="the SSL keyfile",
    )
    group_tls.add_argument(
        '--certfile',
        metavar="PATH",
        help="the SSL keyfile",
    )
    group_tls.add_argument(
        "--tls-control-required",
        default=False,
        action="store_true",
        help="impose SSL for the control connection (before login)",
    )
    group_tls.add_argument(
        "--tls-data-required",
        default=False,
        action="store_true",
        help="impose SSL for data connection",
    )

    # --- less important opts

    group_misc = parser.add_argument_group("Other options")
    group_misc.add_argument(
        '--timeout',
        type=int,
        default=FTPHandler.timeout,
        help=f"connection timeout (default: {FTPHandler.timeout} seconds)",
    )
    group_misc.add_argument(
        '--banner',
        type=str,
        default=FTPHandler.banner,
        help=(
            "the message sent when client connects (default:"
            f" {FTPHandler.banner!r})"
        ),
    )
    group_misc.add_argument(
        "--permit-foreign-addresses",
        default=FTPHandler.permit_foreign_addresses,
        action="store_true",
        help=(
            "allow data connections from an IP address different than the"
            " control connection"
        ),
    )
    group_misc.add_argument(
        "--permit-privileged-ports",
        default=FTPHandler.permit_privileged_ports,
        action="store_true",
        help="allow data connections (PORT) over privileged TCP ports",
    )
    group_misc.add_argument(
        "--encoding",
        type=parse_encoding,
        default="utf-8",
        help=(
            "the encoding used for client / server communication (default:"
            f" {FTPHandler.encoding})"
        ),
    )
    group_misc.add_argument(
        "--use-localtime",
        default=False,
        action="store_true",
        help=(
            "display directory listings with the time in your local time zone"
            " (default: use GMT)"
        ),
    )
    if hasattr(os, "sendfile"):
        group_misc.add_argument(
            "--disable-sendfile",
            default=False,
            action="store_true",
            help="disable sendfile() syscall, used for faster file transfers",
        )
    group_misc.add_argument(
        '--max-cons',
        type=int,
        default=servers.FTPServer.max_cons,
        help=(
            "max number of simultaneous connections (default:"
            f" {servers.FTPServer.max_cons})"
        ),
    )
    group_misc.add_argument(
        '--max-cons-per-ip',
        type=int,
        default=servers.FTPServer.max_cons,
        help=(
            "maximum number connections from the same IP address (default:"
            " unlimited)"
        ),
    )
    group_misc.add_argument(
        '--max-login-attempts',
        type=int,
        default=FTPHandler.max_login_attempts,
        help=(
            "max number of failed authentications before disconnect (default:"
            f" {FTPHandler.max_login_attempts})"
        ),
    )

    return parser.parse_args(args)


def main(args=None):
    """Start a standalone anonymous FTP server."""
    opts = parse_args(args=args)

    if opts.debug:
        config_logging(level=logging.DEBUG)

    # On recent Windows versions, if address is not specified and IPv6
    # is installed the socket will listen on IPv6 by default; in this
    # case we force IPv4 instead.
    if os.name in ('nt', 'ce') and not opts.interface:
        opts.interface = '0.0.0.0'

    authorizer = DummyAuthorizer()
    perm = "elradfmwMT" if opts.write else "elr"
    if opts.username:
        if not opts.password:
            raise argparse.ArgumentTypeError(
                "if username (-u) is supplied, password (-P) is required"
            )
        authorizer.add_user(
            opts.username, opts.password, opts.directory, perm=perm
        )
    else:
        authorizer.add_anonymous(opts.directory, perm=perm)

    # FTP or FTPS?
    if opts.tls:
        if TLS_FTPHandler is None:
            raise argparse.ArgumentTypeError("PyOpenSSL not installed")
        if not opts.certfile or not opts.keyfile:
            raise argparse.ArgumentTypeError(
                "--tls requires --keyfile and --certfile args"
            )
        handler = TLS_FTPHandler
        handler.certfile = opts.certfile
        handler.keyfile = opts.keyfile
        if opts.tls_control_required:
            handler.tls_control_required = True
        if opts.tls_data_required:
            handler.tls_data_required = True
    else:
        if opts.certfile or opts.keyfile:
            raise argparse.ArgumentTypeError(
                "--keyfile and --certfile args requires --tls arg"
            )
        handler = FTPHandler

    # Configure handler.
    handler.authorizer = authorizer
    handler.masquerade_address = opts.nat_address
    handler.passive_ports = opts.range
    handler.timeout = opts.timeout
    handler.dtp_handler.timeout = opts.timeout
    handler.banner = opts.banner
    handler.max_login_attempts = opts.max_login_attempts
    handler.permit_foreign_addresses = opts.permit_foreign_addresses
    handler.permit_privileged_ports = opts.permit_privileged_ports
    handler.encoding = opts.encoding
    handler.use_gmt_times = not opts.use_localtime
    if hasattr(os, "sendfile"):
        handler.use_sendfile = not opts.disable_sendfile

    # Configure server / acceptor.
    server = opts.concurrency((opts.interface, opts.port), handler)
    server.max_cons = opts.max_cons
    server.max_cons_per_ip = opts.max_cons_per_ip

    # On Windows specify a timeout for the underlying select() so
    # that the server can be interrupted with CTRL + C.
    try:
        server.serve_forever(timeout=2 if os.name == 'nt' else None)
    finally:
        server.close_all()
    if args:  # only used in unit tests
        return server


if __name__ == '__main__':
    main()
