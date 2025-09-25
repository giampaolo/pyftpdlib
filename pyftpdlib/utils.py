# Copyright (C) 2007 Giampaolo Rodola' <g.rodola@gmail.com>.
# Use of this source code is governed by MIT license that can be
# found in the LICENSE file.

import os
import sys


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
