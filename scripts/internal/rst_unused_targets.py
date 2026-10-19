#!/usr/bin/env python3

# Copyright (C) 2007 Giampaolo Rodola' <g.rodola@gmail.com>.
# Use of this source code is governed by MIT license that can be
# found in the LICENSE file.

"""Check .rst files for URL hyperlink targets that are defined but
never referenced. Run by "make lint-rst".

Undefined references are already caught by Sphinx during the docs
build, so this only covers the unused-target case.
"""

import argparse
import re
import sys

RE_URL_TARGET = re.compile(r"^\.\. _`?([^`\n:]+)`?:\s*https?://", re.MULTILINE)
RE_BACKTICK_REF = re.compile(r"`([^`<\n]+)`_(?!_)")
RE_BARE_REF = re.compile(r"(?<![`\w])([A-Za-z][\w-]*)_(?!\w)")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("files", nargs="+", metavar="FILE")
    args = parser.parse_args()

    errors = []
    for path in args.files:
        with open(path) as f:
            text = f.read()
        used = set()
        for regex in (RE_BACKTICK_REF, RE_BARE_REF):
            used.update(
                m.group(1).strip().lower() for m in regex.finditer(text)
            )
        for m in RE_URL_TARGET.finditer(text):
            name = m.group(1).strip()
            if name.lower() not in used:
                lineno = text.count("\n", 0, m.start()) + 1
                msg = f"unreferenced hyperlink target: {name!r}"
                errors.append((path, lineno, msg))

    for path, lineno, msg in sorted(errors):
        print(f"{path}:{lineno}: {msg}")
    if errors:
        sys.exit(1)


if __name__ == "__main__":
    main()
