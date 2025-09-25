#!/usr/bin/env python3

# Copyright (C) 2007 Giampaolo Rodola' <g.rodola@gmail.com>.
# Use of this source code is governed by MIT license that can be
# found in the LICENSE file.

"""Shortcuts for various tasks, emulating UNIX "make" on Windows.
This is supposed to be invoked by "make.bat" and not used directly.
This was originally written as a bat file but they suck so much
that they should be deemed illegal!
"""

import argparse
import errno
import fnmatch
import os
import shlex
import shutil
import site
import subprocess
import sys

PYTHON = os.getenv("PYTHON", sys.executable)
HERE = os.path.abspath(os.path.dirname(__file__))
ROOT_DIR = os.path.realpath(os.path.join(HERE, "..", ".."))
WINDOWS = os.name == "nt"


sys.path.insert(0, ROOT_DIR)  # so that we can import setup.py

import setup  # noqa: E402

TEST_DEPS = setup.TEST_DEPS
DEV_DEPS = setup.DEV_DEPS


# ===================================================================
# utils
# ===================================================================


def safe_print(text, file=sys.stdout):
    """Prints a (unicode) string to the console, encoded depending on
    the stdout/file encoding (eg. cp437 on Windows). This is to avoid
    encoding errors in case of funky path names.
    """
    if not isinstance(text, str):
        return print(text, file=file)
    try:
        file.write(text)
    except UnicodeEncodeError:
        bytes_string = text.encode(file.encoding, "backslashreplace")
        if hasattr(file, "buffer"):
            file.buffer.write(bytes_string)
        else:
            text = bytes_string.decode(file.encoding, "strict")
            file.write(text)
    file.write("\n")


def sh(cmd, nolog=False):
    assert isinstance(cmd, list), repr(cmd)
    if not nolog:
        safe_print("cmd: " + " ".join(cmd))
    p = subprocess.Popen(cmd, env=os.environ, cwd=os.getcwd())
    p.communicate()
    if p.returncode != 0:
        sys.exit(p.returncode)


def rm(pattern, directory=False):
    """Recursively remove a file or dir by pattern."""

    def safe_remove(path):
        try:
            os.remove(path)
        except OSError as err:
            if err.errno != errno.ENOENT:
                raise
        else:
            safe_print("rm %s" % path)

    def safe_rmtree(path):
        def onerror(fun, path, excinfo):
            exc = excinfo[1]
            if exc.errno != errno.ENOENT:
                raise  # noqa: PLE0704

        existed = os.path.isdir(path)
        shutil.rmtree(path, onerror=onerror)
        if existed:
            safe_print(f"rmdir -f {path}")

    if "*" not in pattern:
        if directory:
            safe_rmtree(pattern)
        else:
            safe_remove(pattern)
        return

    for root, dirs, files in os.walk("."):
        root = os.path.normpath(root)
        if root.startswith(".git/"):
            continue
        found = fnmatch.filter(dirs if directory else files, pattern)
        for name in found:
            path = os.path.join(root, name)
            if directory:
                safe_print(f"rmdir -f {path}")
                safe_rmtree(path)
            else:
                safe_print(f"rm {path}")
                safe_remove(path)


def safe_remove(path):
    try:
        os.remove(path)
    except FileNotFoundError:
        pass
    else:
        safe_print(f"rm {path}")


def safe_rmtree(path):
    def onerror(fun, path, excinfo):
        exc = excinfo[1]
        if exc.errno != errno.ENOENT:
            raise  # noqa: PLE0704

    existed = os.path.isdir(path)
    shutil.rmtree(path, onerror=onerror)
    if existed:
        safe_print(f"rmdir -f {path}")


def recursive_rm(*patterns):
    """Recursively remove a file or matching a list of patterns."""
    for root, dirs, files in os.walk("."):
        root = os.path.normpath(root)
        if root.startswith(".git/"):
            continue
        for file in files:
            for pattern in patterns:
                if fnmatch.fnmatch(file, pattern):
                    safe_remove(os.path.join(root, file))
        for dir in dirs:
            for pattern in patterns:
                if fnmatch.fnmatch(dir, pattern):
                    safe_rmtree(os.path.join(root, dir))


# ===================================================================
# commands
# ===================================================================


def install_pip():
    """Install pip."""
    sh([PYTHON, os.path.join(HERE, "install_pip.py")])


def install():
    """Install in develop / edit mode."""
    sh([PYTHON, "setup.py", "develop"])


def uninstall():
    """Uninstall."""
    clean()
    install_pip()
    here = os.getcwd()
    try:
        os.chdir("C:\\")
        while True:
            try:
                import pyftpdlib  # noqa: PLC0415, F401
            except ImportError:
                break
            else:
                sh([PYTHON, "-m", "pip", "uninstall", "-y", "pyftpdlib"])
    finally:
        os.chdir(here)

    for dir in site.getsitepackages():
        for name in os.listdir(dir):
            if name.startswith("pyftpdlib"):
                rm(os.path.join(dir, name))
            elif name == "easy-install.pth":
                # easy_install can add a line (installation path) into
                # easy-install.pth; that line alters sys.path.
                path = os.path.join(dir, name)
                with open(path) as f:
                    lines = f.readlines()
                    hasit = False
                    for line in lines:
                        if "pyftpdlib" in line:
                            hasit = True
                            break
                if hasit:
                    with open(path, "w") as f:
                        for line in lines:
                            if "pyftpdlib" not in line:
                                f.write(line)
                            else:
                                print(f"removed line {line!r} from {path!r}")


def clean():
    """Deletes dev files."""
    recursive_rm(
        "$testfn*",
        "*.bak",
        "*.core",
        "*.egg-info",
        "*.orig",
        "*.pyc",
        "*.pyd",
        "*.pyo",
        "*.rej",
        "*.so",
        "*.~",
        "*__pycache__",
        ".coverage",
        ".failed-tests.txt",
    )
    safe_rmtree("build")
    safe_rmtree(".coverage")
    safe_rmtree("dist")
    safe_rmtree("docs/_build")
    safe_rmtree("htmlcov")
    safe_rmtree("tmp")


def install_pydeps_test():
    """Install useful deps."""
    install_pip()
    install_git_hooks()
    cmd = [PYTHON, "-m", "pip", "install", "--user", "-U", *TEST_DEPS]
    sh(cmd)


def install_pydeps_dev():
    """Install useful deps."""
    install_pip()
    install_git_hooks()
    cmd = [PYTHON, "-m", "pip", "install", "--user", "-U", *DEV_DEPS]
    sh(cmd)


def test(args=None):  # noqa: PT028
    """Run tests."""
    if args is None:
        args = []
    elif isinstance(args, str):
        args = shlex.split(args)
    sh([PYTHON, "-m", "pytest", *args])


def test_authorizers():
    sh([
        PYTHON,
        "-m",
        "pytest",
        "tests/test_authorizers.py",
    ])


def test_filesystems():
    sh([
        PYTHON,
        "-m",
        "pytest",
        "tests/test_filesystems.py",
    ])


def test_functional():
    sh([
        PYTHON,
        "-m",
        "pytest",
        "tests/test_functional.py",
    ])


def test_functional_ssl():
    sh([
        PYTHON,
        "-m",
        "pytest",
        "tests/test_functional_ssl.py",
    ])


def test_ioloop():
    sh([PYTHON, "-m", "pytest", "tests/test_ioloop.py"])


def test_cli():
    sh([PYTHON, "-m", "pytest", "tests/test_cli.py"])


def test_servers():
    sh([
        PYTHON,
        "-m",
        "pytest",
        "tests/test_servers.py",
    ])


def coverage():
    """Run coverage tests."""
    sh([PYTHON, "-m", "coverage", "run", "-m", "pytest"])
    sh([PYTHON, "-m", "coverage", "report"])
    sh([PYTHON, "-m", "coverage", "html"])
    sh([PYTHON, "-m", "webbrowser", "-t", "htmlcov/index.html"])


def test_by_name(name):
    """Run test by name."""
    test(name)


def test_last_failed():
    """Re-run tests which failed on last run."""
    sh([PYTHON, "-m", "pytest", "--last-failed"])


def install_git_hooks():
    """Install GIT pre-commit hook."""
    if os.path.isdir(".git"):
        src = os.path.join(
            ROOT_DIR, "scripts", "internal", "git_pre_commit.py"
        )
        dst = os.path.realpath(
            os.path.join(ROOT_DIR, ".git", "hooks", "pre-commit")
        )
        with open(src) as s, open(dst, "w") as d:
            d.write(s.read())


def get_python(path):
    if not path:
        return sys.executable
    if os.path.isabs(path):
        return path
    # try to look for a python installation given a shortcut name
    path = path.replace(".", "")
    vers = (
        "38",
        "38-32",
        "38-64",
        "39-32",
        "39-64",
    )
    for v in vers:
        pypath = r"C:\\python%s\python.exe" % v
        if path in pypath and os.path.isfile(pypath):
            return pypath


def parse_args():
    parser = argparse.ArgumentParser()
    # option shared by all commands
    parser.add_argument("-p", "--python", help="use python executable path")
    sp = parser.add_subparsers(dest="command", title="targets")
    sp.add_parser("clean", help="deletes dev files")
    sp.add_parser("coverage", help="run coverage tests.")
    sp.add_parser("help", help="print this help")
    sp.add_parser("install", help="install in develop/edit mode")
    sp.add_parser("install-git-hooks", help="install GIT pre-commit hook")
    sp.add_parser("install-pip", help="install pip")
    sp.add_parser("install-pydeps-dev", help="install dev python deps")
    sp.add_parser("install-pydeps-test", help="install python test deps")
    sp.add_parser("test-authorizers")
    sp.add_parser("test-filesystems")
    sp.add_parser("test-functional")
    sp.add_parser("test-functional-ssl")
    sp.add_parser("test-ioloop")
    sp.add_parser("test-misc")
    sp.add_parser("test-servers")
    test = sp.add_parser("test", help="[ARG] run tests")
    test_by_name = sp.add_parser("test-by-name", help="<ARG> run test by name")
    sp.add_parser("uninstall", help="uninstall")

    for p in (test, test_by_name):
        p.add_argument("arg", type=str, nargs="?", default="", help="arg")

    args = parser.parse_args()

    if not args.command or args.command == "help":
        parser.print_help(sys.stderr)
        sys.exit(1)

    return args


def main():
    global PYTHON
    args = parse_args()
    # set python exe
    PYTHON = get_python(args.python)
    if not PYTHON:
        return sys.exit(
            "can't find any python installation matching %r" % args.python
        )
    os.putenv("PYTHON", PYTHON)
    print("using " + PYTHON)

    fname = args.command.replace("-", "_")
    fun = getattr(sys.modules[__name__], fname)  # err if fun not defined
    funargs = []
    # mandatory args
    if args.command in ("test-by-name", "test-script"):
        if not args.arg:
            sys.exit("command needs an argument")
        funargs = [args.arg]
    # optional args
    if args.command == "test" and args.arg:
        funargs = [args.arg]
    fun(*funargs)


if __name__ == "__main__":
    main()
