# Copyright (C) 2007 Giampaolo Rodola' <g.rodola@gmail.com>.
# Use of this source code is governed by MIT license that can be
# found in the LICENSE file.

"""
Start a stand alone anonymous FTP server from the command line as in:

$ python3 -m pyftpdlib
"""

import argparse
import codecs
import logging
import os

from .authorizers import DummyAuthorizer
from .handlers import FTPHandler
from .log import config_logging
from .servers import FTPServer

DEFAULT_PORT = 2121


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


def parse_args(args=None):
    usage = "python3 -m pyftpdlib [options]"
    parser = argparse.ArgumentParser(
        usage=usage,
        description=main.__doc__,
    )

    # --- most important opts

    group1 = parser.add_argument_group("Main options")
    group1.add_argument(
        '-i',
        '--interface',
        default=None,
        metavar="ADDRESS",
        help="specify the interface to run on (default: all interfaces)",
    )
    group1.add_argument(
        '-p',
        '--port',
        type=int,
        default=DEFAULT_PORT,
        metavar="PORT",
        help=f"specify port number to run on (default: {DEFAULT_PORT})",
    )
    group1.add_argument(
        '-w',
        '--write',
        action="store_true",
        default=False,
        help="grants write access for logged in user (default: read-only)",
    )
    group1.add_argument(
        '-d',
        '--directory',
        default=os.getcwd(),
        metavar="FOLDER",
        help="specify the directory to share (default: current directory)",
    )
    group1.add_argument(
        '-n',
        '--nat-address',
        default=None,
        metavar="ADDRESS",
        help="the NAT address to use for passive connections",
    )
    group1.add_argument(
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
    group1.add_argument(
        '-D',
        '--debug',
        action='store_true',
        help="enable DEBUG logging level",
    )
    group1.add_argument(
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
    group1.add_argument(
        '-P',
        '--password',
        type=str,
        default=None,
        help=(
            "specify a password to login with (username required to be useful)"
        ),
    )

    # --- less important opts

    group2 = parser.add_argument_group("Other options")
    group2.add_argument(
        '--timeout',
        type=int,
        default=FTPHandler.timeout,
        help=f"connection timeout (default: {FTPHandler.timeout} seconds)",
    )
    group2.add_argument(
        '--banner',
        type=str,
        default=FTPHandler.banner,
        help=(
            "the message sent when client connects (default:"
            f" {FTPHandler.banner!r})"
        ),
    )
    group2.add_argument(
        '--max-login-attempts',
        type=int,
        default=FTPHandler.max_login_attempts,
        help=(
            "max number of failed authentications before disconnect (default:"
            f" {FTPHandler.max_login_attempts})"
        ),
    )
    group2.add_argument(
        "--permit-foreign-addresses",
        default=FTPHandler.permit_foreign_addresses,
        action="store_true",
        help=(
            "allow data connections from an IP address different than the"
            " control connection"
        ),
    )
    group2.add_argument(
        "--permit-privileged-ports",
        default=FTPHandler.permit_privileged_ports,
        action="store_true",
        help="allow data connections (PORT) over privileged TCP ports",
    )
    group2.add_argument(
        "--encoding",
        type=parse_encoding,
        default="utf-8",
        help=(
            "the encoding used for client / server communication (default:"
            f" {FTPHandler.encoding})"
        ),
    )
    group2.add_argument(
        "--use-localtime",
        default=False,
        action="store_true",
        help=(
            "display directory listings with the time in your local time zone"
            " (default: use GMT)"
        ),
    )
    if hasattr(os, "sendfile"):
        group2.add_argument(
            "--disable-sendfile",
            default=False,
            action="store_true",
            help="disable sendfile() syscall, used for faster file transfers",
        )
    group2.add_argument(
        '--max-cons',
        type=int,
        default=FTPServer.max_cons,
        help=(
            "max number of simultaneous connections (default:"
            f" {FTPServer.max_cons})"
        ),
    )
    group2.add_argument(
        '--max-cons-per-ip',
        type=int,
        default=FTPServer.max_cons,
        help=(
            "maximum number connections from the same IP address (default:"
            " unlimited)"
        ),
    )

    return parser.parse_args(args)


def main(args=None):
    """Start a stand alone anonymous FTP server."""
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
                "if username (-u) is supplied, password ('-P') is required"
            )
        authorizer.add_user(
            opts.username, opts.password, opts.directory, perm=perm
        )
    else:
        authorizer.add_anonymous(opts.directory, perm=perm)

    handler = FTPHandler
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
    handler.use_sendfile = not opts.disable_sendfile

    ftpd = FTPServer((opts.interface, opts.port), FTPHandler)
    ftpd.max_cons = opts.max_cons
    ftpd.max_cons_per_ip = opts.max_cons_per_ip

    # On Windows specify a timeout for the underlying select() so
    # that the server can be interrupted with CTRL + C.
    try:
        ftpd.serve_forever(timeout=2 if os.name == 'nt' else None)
    finally:
        ftpd.close_all()
    if args:  # only used in unit tests
        return ftpd


if __name__ == '__main__':
    main()
