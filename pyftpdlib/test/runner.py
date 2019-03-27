#!/usr/bin/env python

# Copyright (C) 2007 Giampaolo Rodola' <g.rodola@gmail.com>.
# Use of this source code is governed by MIT license that can be
# found in the LICENSE file.


from __future__ import print_function
import atexit
import os
import sys
from unittest import TestResult
from unittest import TextTestResult
from unittest import TextTestRunner
try:
    import ctypes
except ImportError:
    ctypes = None

from pyftpdlib.test import configure_logging
from pyftpdlib.test import remove_test_files
from pyftpdlib.test import unittest
from pyftpdlib.test import VERBOSITY

HERE = os.path.abspath(os.path.dirname(__file__))
if os.name == 'posix':
    GREEN = 1
    RED = 2
    BROWN = 94
else:
    GREEN = 2
    RED = 4
    BROWN = 6
    DEFAULT_COLOR = 7


def term_supports_colors(file=sys.stdout):
    if os.name == 'nt':
        return ctypes is not None
    try:
        import curses
        assert file.isatty()
        curses.setupterm()
        assert curses.tigetnum("colors") > 0
    except Exception:
        return False
    else:
        return True


def hilite(s, color, bold=False):
    """Return an highlighted version of 'string'."""
    attr = []
    if color == GREEN:
        attr.append('32')
    elif color == RED:
        attr.append('91')
    elif color == BROWN:
        attr.append('33')
    else:
        raise ValueError("unrecognized color")
    if bold:
        attr.append('1')
    return '\x1b[%sm%s\x1b[0m' % (';'.join(attr), s)


def _stderr_handle():
    GetStdHandle = ctypes.windll.Kernel32.GetStdHandle
    STD_ERROR_HANDLE_ID = ctypes.c_ulong(0xfffffff4)
    GetStdHandle.restype = ctypes.c_ulong
    handle = GetStdHandle(STD_ERROR_HANDLE_ID)
    atexit.register(ctypes.windll.Kernel32.CloseHandle, handle)
    return handle


def win_colorprint(printer, s, color, bold=False):
    if bold and color <= 7:
        color += 8
    handle = _stderr_handle()
    SetConsoleTextAttribute = ctypes.windll.Kernel32.SetConsoleTextAttribute
    SetConsoleTextAttribute(handle, color)
    try:
        printer(s)
    finally:
        SetConsoleTextAttribute(handle, DEFAULT_COLOR)


class ColouredResult(TextTestResult):

    def _color_print(self, s, color, bold=False):
        if os.name == 'posix':
            self.stream.writeln(hilite(s, color, bold=bold))
        else:
            win_colorprint(self.stream.writeln, s, color, bold=bold)

    def addSuccess(self, test):
        TestResult.addSuccess(self, test)
        self._color_print("OK", GREEN)

    def addError(self, test, err):
        TestResult.addError(self, test, err)
        self._color_print("ERROR", RED, bold=True)

    def addFailure(self, test, err):
        TestResult.addFailure(self, test, err)
        self._color_print("FAIL", RED)

    def addSkip(self, test, reason):
        TestResult.addSkip(self, test, reason)
        self._color_print("skipped: %s" % reason, BROWN)

    def printErrorList(self, flavour, errors):
        flavour = hilite(flavour, RED, bold=flavour == 'ERROR')
        TextTestResult.printErrorList(self, flavour, errors)


class ColouredRunner(TextTestRunner):
    resultclass = ColouredResult if term_supports_colors() else TextTestResult

    def _makeResult(self):
        # Store result instance so that it can be accessed on
        # KeyboardInterrupt.
        self.result = TextTestRunner._makeResult(self)
        return self.result


def get_suite(name=None):
    suite = unittest.TestSuite()
    if name is None:
        testmods = [os.path.splitext(x)[0] for x in os.listdir(HERE)
                    if x.endswith('.py') and x.startswith('test_')]
        for tm in testmods:
            # ...so that the full test paths are printed on screen
            tm = "pyftpdlib.test.%s" % tm
            suite.addTest(unittest.defaultTestLoader.loadTestsFromName(tm))
    else:
        name = os.path.splitext(os.path.basename(name))[0]
        suite.addTest(unittest.defaultTestLoader.loadTestsFromName(name))
    return suite


def main(name=None):
    configure_logging()
    remove_test_files()
    runner = ColouredRunner(verbosity=VERBOSITY)
    try:
        result = runner.run(get_suite(name))
    except (KeyboardInterrupt, SystemExit) as err:
        print("received %s" % err.__class__.__name__, file=sys.stderr)
        runner.result.printErrors()
        sys.exit(1)
    else:
        success = result.wasSuccessful()
        sys.exit(0 if success else 1)


if __name__ == '__main__':
    main()
