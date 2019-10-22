# Copyright (C) 2007 Giampaolo Rodola' <g.rodola@gmail.com>.
# Use of this source code is governed by MIT license that can be
# found in the LICENSE file.

"""
Logging support for pyftpdlib, inspired from Tornado's
(http://www.tornadoweb.org/).

This is not supposed to be imported/used directly.
Instead you should use logging.basicConfig before serve_forever().
"""

import logging
import sys
import time
try:
    import curses
except ImportError:
    curses = None

from ._compat import unicode


# default logger
logger = logging.getLogger('pyftpdlib')


def _stderr_supports_color():
    color = False
    if curses is not None and sys.stderr.isatty():
        try:
            curses.setupterm()
            if curses.tigetnum("colors") > 0:
                color = True
        except Exception:
            pass
    return color


# configurable options
LEVEL = logging.INFO
PREFIX = '[%(levelname)1.1s %(asctime)s]'
PREFIX_MPROC = '[%(levelname)1.1s %(asctime)s %(process)s]'
COLOURED = _stderr_supports_color()
TIME_FORMAT = "%Y-%m-%d %H:%M:%S"


# taken and adapted from Tornado
class LogFormatter(logging.Formatter):
    """Log formatter used in pyftpdlib.
    Key features of this formatter are:

    * Color support when logging to a terminal that supports it.
    * Timestamps on every log line.
    * Robust against str/bytes encoding problems.
    """
    PREFIX = PREFIX

    def __init__(self, *args, **kwargs):
        logging.Formatter.__init__(self, *args, **kwargs)
        self._coloured = COLOURED and _stderr_supports_color()
        if self._coloured:
            curses.setupterm()
            # The curses module has some str/bytes confusion in
            # python3.  Until version 3.2.3, most methods return
            # bytes, but only accept strings.  In addition, we want to
            # output these strings with the logging module, which
            # works with unicode strings.  The explicit calls to
            # unicode() below are harmless in python2 but will do the
            # right conversion in python 3.
            fg_color = (curses.tigetstr("setaf") or curses.tigetstr("setf") or
                        "")
            if (3, 0) < sys.version_info < (3, 2, 3):
                fg_color = unicode(fg_color, "ascii")
            self._colors = {
                # blues
                logging.DEBUG: unicode(curses.tparm(fg_color, 4), "ascii"),
                # green
                logging.INFO: unicode(curses.tparm(fg_color, 2), "ascii"),
                # yellow
                logging.WARNING: unicode(curses.tparm(fg_color, 3), "ascii"),
                # red
                logging.ERROR: unicode(curses.tparm(fg_color, 1), "ascii")
            }
            self._normal = unicode(curses.tigetstr("sgr0"), "ascii")

    def format(self, record):
        try:
            record.message = record.getMessage()
        except Exception as err:
            record.message = "Bad message (%r): %r" % (err, record.__dict__)

        record.asctime = time.strftime(TIME_FORMAT,
                                       self.converter(record.created))
        prefix = self.PREFIX % record.__dict__
        if self._coloured:
            prefix = (self._colors.get(record.levelno, self._normal) +
                      prefix + self._normal)

        # Encoding notes:  The logging module prefers to work with character
        # strings, but only enforces that log messages are instances of
        # basestring.  In python 2, non-ascii bytestrings will make
        # their way through the logging framework until they blow up with
        # an unhelpful decoding error (with this formatter it happens
        # when we attach the prefix, but there are other opportunities for
        # exceptions further along in the framework).
        #
        # If a byte string makes it this far, convert it to unicode to
        # ensure it will make it out to the logs.  Use repr() as a fallback
        # to ensure that all byte strings can be converted successfully,
        # but don't do it by default so we don't add extra quotes to ascii
        # bytestrings.  This is a bit of a hacky place to do this, but
        # it's worth it since the encoding errors that would otherwise
        # result are so useless (and tornado is fond of using utf8-encoded
        # byte strings wherever possible).
        try:
            message = unicode(record.message)
        except UnicodeDecodeError:
            message = repr(record.message)

        formatted = prefix + " " + message
        if record.exc_info:
            if not record.exc_text:
                record.exc_text = self.formatException(record.exc_info)
        if record.exc_text:
            formatted = formatted.rstrip() + "\n" + record.exc_text
        return formatted.replace("\n", "\n    ")


def debug(s, inst=None):
    s = "[debug] " + s
    if inst is not None:
        s += " (%r)" % inst
    logger.debug(s)


def is_logging_configured():
    if logging.getLogger('pyftpdlib').handlers:
        return True
    if logging.root.handlers:
        return True
    return False


# TODO: write tests
def config_logging(level=LEVEL, prefix=PREFIX, other_loggers=None):
    # Little speed up
    if "(process)" not in prefix:
        logging.logProcesses = False
    if "%(processName)s" not in prefix:
        logging.logMultiprocessing = False
    if "%(thread)d" not in prefix and "%(threadName)s" not in prefix:
        logging.logThreads = False
    handler = logging.StreamHandler()
    formatter = LogFormatter()
    formatter.PREFIX = prefix
    handler.setFormatter(formatter)
    loggers = [logging.getLogger('pyftpdlib')]
    if other_loggers is not None:
        loggers.extend(other_loggers)
    for logger in loggers:
        logger.setLevel(level)
        logger.addHandler(handler)
