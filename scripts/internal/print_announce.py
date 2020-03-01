#!/usr/bin/env python

# Copyright (c) 2009 Giampaolo Rodola'. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

"""
Prints release announce based on HISTORY.rst file content.
"""

import os
import re

from pyftpdlib import __ver__ as PRJ_VERSION


HERE = os.path.abspath(os.path.dirname(__file__))
HISTORY = os.path.abspath(os.path.join(HERE, '../HISTORY.rst'))

PRJ_NAME = 'pyftpdlib'
PRJ_URL_HOME = 'https://github.com/giampaolo/pyftpdlib'
PRJ_URL_DOC = 'http://pyftpdlib.readthedocs.io'
PRJ_URL_DOWNLOAD = 'https://pypi.python.org/pypi/pyftpdlib'
PRJ_URL_WHATSNEW = \
    'https://github.com/giampaolo/pyftpdlib/blob/master/HISTORY.rst'

template = """\
Hello all,
I'm glad to announce the release of {prj_name} {prj_version}:
{prj_urlhome}

About
=====

Python FTP server library provides a high-level portable interface to easily \
write very efficient, scalable and asynchronous FTP servers with Python.

What's new
==========

{changes}

Links
=====

- Home page: {prj_urlhome}
- Download: {prj_urldownload}
- Documentation: {prj_urldoc}
- What's new: {prj_urlwhatsnew}

--

Giampaolo - http://grodola.blogspot.com
"""


def get_changes():
    """Get the most recent changes for this release by parsing
    HISTORY.rst file.
    """
    with open(HISTORY) as f:
        lines = f.readlines()

    block = []

    # eliminate the part preceding the first block
    for i, line in enumerate(lines):
        line = lines.pop(0)
        if line.startswith('===='):
            break
    lines.pop(0)

    for i, line in enumerate(lines):
        line = lines.pop(0)
        line = line.rstrip()
        if re.match(r"^- \d+_: ", line):
            num, _, rest = line.partition(': ')
            num = ''.join([x for x in num if x.isdigit()])
            line = "- #%s: %s" % (num, rest)

        if line.startswith('===='):
            break
        block.append(line)

    # eliminate bottom empty lines
    block.pop(-1)
    while not block[-1]:
        block.pop(-1)

    return "\n".join(block)


def main():
    changes = get_changes()
    print(template.format(
        prj_name=PRJ_NAME,
        prj_version=PRJ_VERSION,
        prj_urlhome=PRJ_URL_HOME,
        prj_urldownload=PRJ_URL_DOWNLOAD,
        prj_urldoc=PRJ_URL_DOC,
        prj_urlwhatsnew=PRJ_URL_WHATSNEW,
        changes=changes,
    ))


if __name__ == '__main__':
    main()
