#!/usr/bin/env python3

# Copyright (c) 2009 Giampaolo Rodola'. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

"""
This gets executed on 'git commit' and rejects the commit in case the
submitted code does not pass validation. Validation is run only against
the files which were modified in the commit. Install this with "make
install-git-hooks".
"""


import os
import shlex
import subprocess
import sys


PYTHON = sys.executable
THIS_SCRIPT = os.path.realpath(__file__)


def term_supports_colors():
    try:
        import curses  # noqa: PLC0415

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
    elif ok:  # green
        attr.append("32")
    else:  # red
        attr.append("31")
    if bold:
        attr.append("1")
    return "\x1b[%sm%s\x1b[0m" % (";".join(attr), s)


def exit(msg):
    print(hilite("commit aborted: " + msg, ok=False), file=sys.stderr)
    sys.exit(1)


def sh(cmd):
    if isinstance(cmd, str):
        cmd = shlex.split(cmd)
    p = subprocess.Popen(
        cmd,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        universal_newlines=True,
    )
    stdout, stderr = p.communicate()
    if p.returncode != 0:
        raise RuntimeError(stderr)
    if stderr:
        print(stderr, file=sys.stderr)
    if stdout.endswith("\n"):
        stdout = stdout[:-1]
    return stdout


def open_text(path):
    return open(path, encoding="utf8")


def git_committed_files():
    out = sh(["git", "diff", "--cached", "--name-only"])
    py_files = [
        x for x in out.split("\n") if x.endswith(".py") and os.path.exists(x)
    ]
    rst_files = [
        x for x in out.split("\n") if x.endswith(".rst") and os.path.exists(x)
    ]
    toml_files = [
        x for x in out.split("\n") if x.endswith(".toml") and os.path.exists(x)
    ]
    # XXX: we should escape spaces and possibly other amenities here
    new_rm_mv = sh(
        ["git", "diff", "--name-only", "--diff-filter=ADR", "--cached"]
    ).split()
    return (py_files, rst_files, toml_files, new_rm_mv)


def ruff(files):
    print("running ruff (%s)" % len(files))
    cmd = [PYTHON, "-m", "ruff", "check", "--no-cache"] + files
    if subprocess.call(cmd) != 0:
        msg = "Python code didn't pass 'ruff' style check. "
        msg += "Try running 'make fix-ruff'."
        return exit(msg)


def rstcheck(files):
    print("running rst linter (%s)" % len(files))
    cmd = ["rstcheck", "--config=pyproject.toml"] + files
    if subprocess.call(cmd) != 0:
        return sys.exit("RST code didn't pass style check")


def toml_sort(files):
    print("running toml linter (%s)" % len(files))
    cmd = ["toml-sort", "--check"] + files
    if subprocess.call(cmd) != 0:
        return sys.exit("%s didn't pass style check" % ' '.join(files))


def main():
    py_files, rst_files, toml_files, new_rm_mv = git_committed_files()
    if py_files:
        ruff(py_files)
    if rst_files:
        rstcheck(rst_files)
    if toml_files:
        toml_sort(toml_files)
    if new_rm_mv:
        out = sh([PYTHON, "scripts/internal/generate_manifest.py"])
        with open_text("MANIFEST.in") as f:
            if out.strip() != f.read().strip():
                sys.exit(
                    "some files were added, deleted or renamed; "
                    "run 'make generate-manifest' and commit again"
                )


main()
