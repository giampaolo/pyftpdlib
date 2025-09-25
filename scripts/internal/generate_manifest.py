#!/usr/bin/env python3

# Copyright (C) 2007 Giampaolo Rodola' <g.rodola@gmail.com>.
# Use of this source code is governed by MIT license that can be
# found in the LICENSE file.

"""
Generate MANIFEST.in file.
"""

import os
import subprocess

SKIP_EXTS = (".png", ".jpg", ".jpeg", ".svg")
SKIP_FILES = tuple()
SKIP_PREFIXES = (".ci/", ".github/")


def sh(cmd):
    return subprocess.check_output(cmd, universal_newlines=True).strip()


def main():
    files = sh(["git", "ls-files"]).split("\n")
    for file in files:
        if (
            file.startswith(SKIP_PREFIXES)
            or os.path.splitext(file)[1].lower() in SKIP_EXTS
            or file in SKIP_FILES
        ):
            continue
        print("include " + file)


if __name__ == "__main__":
    main()
