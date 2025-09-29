# Copyright (C) 2007 Giampaolo Rodola' <g.rodola@gmail.com>.
# Use of this source code is governed by MIT license that can be
# found in the LICENSE file.

import contextlib
import os
import socket
import sys

try:
    from OpenSSL import SSL  # requires "pip install pyopenssl"
except ImportError:
    SSL = None

__all__ = [
    "has_dualstack_ipv6",
    "hilite",
    "is_ssl_sock",
    "memoize",
    "strerror",
    "term_supports_colors",
]


def memoize(fun):
    """A simple memoize decorator for functions supporting (hashable)
    positional arguments.
    """

    def wrapper(*args, **kwargs):
        key = (args, frozenset(sorted(kwargs.items())))
        try:
            return cache[key]
        except KeyError:
            ret = cache[key] = fun(*args, **kwargs)
            return ret

    cache = {}
    return wrapper


@memoize
def term_supports_colors():
    if os.name == "nt":
        return False
    try:
        import curses  # noqa: PLC0415

        assert sys.stdout.isatty()
        assert sys.stderr.isatty()
        curses.setupterm()
        assert curses.tigetnum("colors") > 0
    except Exception:
        return False
    else:
        return True


def hilite(s, color=None, bold=False):  # pragma: no cover
    """Return an highlighted version of 'string'."""
    if not term_supports_colors():
        return s
    attr = []
    colors = dict(
        blue="34",
        brown="33",
        darkgrey="30",
        green="32",
        grey="37",
        lightblue="38;5;66",
        red="91",
        violet="35",
        yellow="93",
        orange="38;5;208",
    )
    colors[None] = "29"
    try:
        color = colors[color]
    except KeyError:
        msg = f"invalid color {color!r}; choose amongst {list(colors.keys())}"
        raise ValueError(msg) from None
    attr.append(color)
    if bold:
        attr.append("1")
    return f"\x1b[{';'.join(attr)}m{s}\x1b[0m"


def strerror(err):
    if isinstance(err, OSError):
        return os.strerror(err.errno)
    return str(err)


# backport of Python 3.8 socket.has_dualstack_ipv6()
@memoize
def has_dualstack_ipv6():
    """Return True if the platform supports creating a SOCK_STREAM socket
    which can handle both AF_INET and AF_INET6 (IPv4 / IPv6) connections.
    """
    if (
        not socket.has_ipv6
        or not hasattr(socket, "IPPROTO_IPV6")
        or not hasattr(socket, "IPV6_V6ONLY")
    ):
        return False
    try:
        with contextlib.closing(
            socket.socket(socket.AF_INET6, socket.SOCK_STREAM)
        ) as sock:
            sock.setsockopt(socket.IPPROTO_IPV6, socket.IPV6_V6ONLY, 0)
            return True
    except OSError:
        return False


def is_ssl_sock(sock):
    return SSL is not None and isinstance(sock, SSL.Connection)
