#!/usr/bin/env python

# Copyright (C) 2007 Giampaolo Rodola' <g.rodola@gmail.com>.
# Use of this source code is governed by MIT license that can be
# found in the LICENSE file.

import os
import sys

from pyftpdlib.test import configure_logging
from pyftpdlib.test import remove_test_files
from pyftpdlib.test import unittest
from pyftpdlib.test import VERBOSITY


HERE = os.path.abspath(os.path.dirname(__file__))


def main():
    testmodules = [os.path.splitext(x)[0] for x in os.listdir(HERE)
                   if x.endswith('.py') and x.startswith('test_')]
    configure_logging()
    remove_test_files()
    suite = unittest.TestSuite()
    for t in testmodules:
        # ...so that "make test" will print the full test paths
        t = "pyftpdlib.test.%s" % t
        suite.addTest(unittest.defaultTestLoader.loadTestsFromName(t))
    result = unittest.TextTestRunner(verbosity=VERBOSITY).run(suite)
    return result.wasSuccessful()


if __name__ == '__main__':
    if not main():
        sys.exit(1)
