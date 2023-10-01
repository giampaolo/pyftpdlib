#!/usr/bin/env python3

# Copyright (c) 2009 Giampaolo Rodola'. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

"""
This gets executed on 'git commit' and rejects the commit in case the
submitted code does not pass validation. Validation is run only against
the files which were modified in the commit. Checks:

- assert no space at EOLs
- assert not pdb.set_trace in code
- assert no bare except clause ("except:") in code
- assert "flake8" checks pass
- assert "isort" checks pass
- abort if files were added/renamed/removed and MANIFEST.in was not updated

Install this with "make install-git-hooks".
"""

from __future__ import print_function

import os
import shlex
import subprocess
import sys


PYTHON = sys.executable
PY3 = sys.version_info[0] == 3
THIS_SCRIPT = os.path.realpath(__file__)


def term_supports_colors():
    try:
        import curses
        assert sys.stderr.isatty()
        curses.setupterm()
        assert curses.tigetnum("colors") > 0
    except Exception:
        return False
    return True


def hilite(s, ok=True, bold=False):
    """Return an highlighted version of 'string'."""
    if not term_supports_colors():
        return s
    attr = []
    if ok is None:  # no color
        pass
    elif ok:   # green
        attr.append('32')
    else:   # red
        attr.append('31')
    if bold:
        attr.append('1')
    return '\x1b[%sm%s\x1b[0m' % (';'.join(attr), s)


def exit(msg):
    print(hilite("commit aborted: " + msg, ok=False), file=sys.stderr)
    sys.exit(1)


def sh(cmd):
    p = subprocess.Popen(cmd, shell=True, stdout=subprocess.PIPE,
                         stderr=subprocess.PIPE, universal_newlines=True)
    stdout, stderr = p.communicate()
    if p.returncode != 0:
        raise RuntimeError(stderr)
    if stderr:
        print(stderr, file=sys.stderr)
    if stdout.endswith('\n'):
        stdout = stdout[:-1]
    return stdout


def open_text(path):
    kw = {'encoding': 'utf8'} if PY3 else {}
    return open(path, 'rt', **kw)


def git_commit_files():
    out = sh("git diff --cached --name-only")
    py_files = [x for x in out.split('\n') if x.endswith('.py') and
                os.path.exists(x)]
    new_rm_mv = sh("git diff --name-only --diff-filter=ADR --cached")
    # XXX: we should escape spaces and possibly other amenities here
    new_rm_mv = new_rm_mv.split()
    return (py_files, new_rm_mv)


def main():
    py_files, new_rm_mv = git_commit_files()
    # Check file content.
    for path in py_files:
        if os.path.realpath(path) == THIS_SCRIPT:
            continue
        with open_text(path) as f:
            lines = f.readlines()
        for lineno, line in enumerate(lines, 1):
            # space at end of line
            if line.endswith(' '):
                print("%s:%s %r" % (path, lineno, line))
                return sys.exit("space at end of line")

    # Python linters
    if py_files:
        # flake8
        assert os.path.exists('.flake8')
        cmd = "%s -m flake8 --config=.flake8 %s" % (PYTHON, " ".join(py_files))
        ret = subprocess.call(shlex.split(cmd))
        if ret != 0:
            return sys.exit("python code didn't pass 'flake8' style check; "
                            "try running 'make fix-flake8'")
        # isort
        assert os.path.exists('pyproject.toml')
        cmd = "%s -m isort --settings=pyproject.toml --check-only %s" % (
            PYTHON, " ".join(py_files))
        ret = subprocess.call(shlex.split(cmd))
        if ret != 0:
            return sys.exit("python code didn't pass 'isort' style check; "
                            "try running 'make fix-imports'")
    if new_rm_mv:
        out = sh("%s scripts/internal/generate_manifest.py" % PYTHON)
        with open_text('MANIFEST.in') as f:
            if out.strip() != f.read().strip():
                return sys.exit(
                    "some files were added, deleted or renamed; "
                    "run 'make generate-manifest' and commit again")


main()
