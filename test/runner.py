#!/usr/bin/env python

# Copyright (C) 2007-2016 Giampaolo Rodola' <g.rodola@gmail.com>.
# Use of this source code is governed by MIT license that can be
# found in the LICENSE file.

import os
import sys

from testutils import configure_logging
from testutils import remove_test_files
from testutils import unittest
from testutils import VERBOSITY


HERE = os.path.abspath(os.path.dirname(__file__))


def main():
    testmodules = [os.path.splitext(x)[0] for x in os.listdir(HERE)
                   if x.endswith('.py') and x.startswith('test_')]
    configure_logging()
    remove_test_files()
    suite = unittest.TestSuite()
    for t in testmodules:
        suite.addTest(unittest.defaultTestLoader.loadTestsFromName(t))
    result = unittest.TextTestRunner(verbosity=VERBOSITY).run(suite)
    return result.wasSuccessful()


if __name__ == '__main__':
    if not main():
        sys.exit(1)
