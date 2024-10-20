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
import atexit
import ctypes
import errno
import fnmatch
import os
import shutil
import site
import subprocess
import sys


APPVEYOR = bool(os.environ.get('APPVEYOR'))
PYTHON = sys.executable if APPVEYOR else os.getenv('PYTHON', sys.executable)
PY3 = sys.version_info[0] >= 3
PYTEST_ARGS = "-v -s --tb=short"
HERE = os.path.abspath(os.path.dirname(__file__))
ROOT_DIR = os.path.realpath(os.path.join(HERE, "..", ".."))
PYPY = '__pypy__' in sys.builtin_module_names
WINDOWS = os.name == "nt"


sys.path.insert(0, ROOT_DIR)  # so that we can import setup.py

import setup  # NOQA

TEST_DEPS = setup.TEST_DEPS
DEV_DEPS = setup.DEV_DEPS

_cmds = {}

GREEN = 2
LIGHTBLUE = 3
YELLOW = 6
RED = 4
DEFAULT_COLOR = 7


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
        bytes_string = text.encode(file.encoding, 'backslashreplace')
        if hasattr(file, 'buffer'):
            file.buffer.write(bytes_string)
        else:
            text = bytes_string.decode(file.encoding, 'strict')
            file.write(text)
    file.write("\n")


def stderr_handle():
    GetStdHandle = ctypes.windll.Kernel32.GetStdHandle
    STD_ERROR_HANDLE_ID = ctypes.c_ulong(0xFFFFFFF4)
    GetStdHandle.restype = ctypes.c_ulong
    handle = GetStdHandle(STD_ERROR_HANDLE_ID)
    atexit.register(ctypes.windll.Kernel32.CloseHandle, handle)
    return handle


def win_colorprint(s, color=LIGHTBLUE):
    if not WINDOWS:
        return print(s)
    color += 8  # bold
    handle = stderr_handle()
    SetConsoleTextAttribute = ctypes.windll.Kernel32.SetConsoleTextAttribute
    SetConsoleTextAttribute(handle, color)
    try:
        print(s)
    finally:
        SetConsoleTextAttribute(handle, DEFAULT_COLOR)


def sh(cmd, nolog=False):
    if not nolog:
        safe_print("cmd: " + cmd)
    p = subprocess.Popen(  # noqa S602
        cmd, shell=True, env=os.environ, cwd=os.getcwd()
    )
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

    for root, dirs, files in os.walk('.'):
        root = os.path.normpath(root)
        if root.startswith('.git/'):
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
    for root, dirs, files in os.walk('.'):
        root = os.path.normpath(root)
        if root.startswith('.git/'):
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


def build():
    """Build / compile."""
    # Make sure setuptools is installed (needed for 'develop' /
    # edit mode).
    sh(f'{PYTHON} -c "import setuptools"')

    cmd = [PYTHON, "setup.py", "build"]
    # Print coloured warnings in real time.
    p = subprocess.Popen(
        cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True
    )
    try:
        for line in iter(p.stdout.readline, ''):
            line = line.strip()
            if 'warning' in line:
                win_colorprint(line, YELLOW)
            elif 'error' in line:
                win_colorprint(line, RED)
            else:
                print(line)
        # retcode = p.poll()
        p.communicate()
        if p.returncode:
            win_colorprint("failure", RED)
            sys.exit(p.returncode)
    finally:
        p.terminate()
        p.wait()

    # Make sure it actually worked.
    sh(f'{PYTHON} -c "import pyftpdlib"')
    win_colorprint("build + import successful", GREEN)


def wheel():
    """Create wheel file."""
    build()
    sh(f"{PYTHON} setup.py bdist_wheel")


def upload_wheels():
    """Upload wheel files on PyPI."""
    build()
    sh(f"{PYTHON} -m twine upload dist/*.whl")


def install_pip():
    """Install pip."""
    sh('%s %s' % (PYTHON, os.path.join(HERE, "install_pip.py")))


def install():
    """Install in develop / edit mode."""
    build()
    sh(f"{PYTHON} setup.py develop")


def uninstall():
    """Uninstall."""
    clean()
    install_pip()
    here = os.getcwd()
    try:
        os.chdir('C:\\')
        while True:
            try:
                import pyftpdlib  # NOQA
            except ImportError:
                break
            else:
                sh(f"{PYTHON} -m pip uninstall -y pyftpdlib")
    finally:
        os.chdir(here)

    for dir in site.getsitepackages():
        for name in os.listdir(dir):
            if name.startswith('pyftpdlib'):
                rm(os.path.join(dir, name))
            elif name == 'easy-install.pth':
                # easy_install can add a line (installation path) into
                # easy-install.pth; that line alters sys.path.
                path = os.path.join(dir, name)
                with open(path) as f:
                    lines = f.readlines()
                    hasit = False
                    for line in lines:
                        if 'pyftpdlib' in line:
                            hasit = True
                            break
                if hasit:
                    with open(path, "w") as f:
                        for line in lines:
                            if 'pyftpdlib' not in line:
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
    sh("%s -m pip install --user -U %s" % (PYTHON, " ".join(TEST_DEPS)))


def install_pydeps_dev():
    """Install useful deps."""
    install_pip()
    install_git_hooks()
    sh("%s -m pip install --user -U %s" % (PYTHON, " ".join(DEV_DEPS)))


def test(args=""):
    """Run tests."""
    build()
    sh(f"{PYTHON} -m pytest {PYTEST_ARGS} {args}")


def test_authorizers():
    build()
    sh(f"{PYTHON} pyftpdlib\\test\\test_authorizers.py")


def test_filesystems():
    build()
    sh(f"{PYTHON} pyftpdlib\\test\\test_filesystems.py")


def test_functional():
    build()
    sh(f"{PYTHON} pyftpdlib\\test\\test_functional.py")


def test_functional_ssl():
    build()
    sh(f"{PYTHON} pyftpdlib\\test\\test_functional_ssl.py")


def test_ioloop():
    build()
    sh(f"{PYTHON} pyftpdlib\\test\\test_ioloop.py")


def test_cli():
    build()
    sh(f"{PYTHON} pyftpdlib\\test\\test_cli.py")


def test_servers():
    build()
    sh(f"{PYTHON} pyftpdlib\\test\\test_servers.py")


def coverage():
    """Run coverage tests."""
    build()
    sh(f"{PYTHON} -m coverage run -m pytest {PYTEST_ARGS}")
    sh(f"{PYTHON} -m coverage report")
    sh(f"{PYTHON} -m coverage html")
    sh(f"{PYTHON} -m webbrowser -t htmlcov/index.html")


def test_by_name(name):
    """Run test by name."""
    build()
    test(name)


def test_last_failed():
    """Re-run tests which failed on last run."""
    build()
    sh(f"{PYTHON} -m pytest {PYTEST_ARGS} --last-failed")


def install_git_hooks():
    """Install GIT pre-commit hook."""
    if os.path.isdir('.git'):
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
    path = path.replace('.', '')
    vers = (
        '27',
        '27-32',
        '27-64',
        '36',
        '36-32',
        '36-64',
        '37',
        '37-32',
        '37-64',
        '38',
        '38-32',
        '38-64',
        '39-32',
        '39-64',
    )
    for v in vers:
        pypath = r'C:\\python%s\python.exe' % v  # noqa: UP031
        if path in pypath and os.path.isfile(pypath):
            return pypath


def parse_args():
    parser = argparse.ArgumentParser()
    # option shared by all commands
    parser.add_argument('-p', '--python', help="use python executable path")
    sp = parser.add_subparsers(dest='command', title='targets')
    sp.add_parser('build', help="build")
    sp.add_parser('clean', help="deletes dev files")
    sp.add_parser('coverage', help="run coverage tests.")
    sp.add_parser('help', help="print this help")
    sp.add_parser('install', help="build + install in develop/edit mode")
    sp.add_parser('install-git-hooks', help="install GIT pre-commit hook")
    sp.add_parser('install-pip', help="install pip")
    sp.add_parser('install-pydeps-dev', help="install dev python deps")
    sp.add_parser('install-pydeps-test', help="install python test deps")
    sp.add_parser('test', help="run tests")
    sp.add_parser('test-authorizers')
    sp.add_parser('test-filesystems')
    sp.add_parser('test-functional')
    sp.add_parser('test-functional-ssl')
    sp.add_parser('test-ioloop')
    sp.add_parser('test-misc')
    sp.add_parser('test-servers')
    sp.add_parser('lint', help="run flake8 against all py files")
    test = sp.add_parser('test', help="[ARG] run tests")
    test_by_name = sp.add_parser('test-by-name', help="<ARG> run test by name")
    sp.add_parser('uninstall', help="uninstall")

    for p in (test, test_by_name):
        p.add_argument('arg', type=str, nargs='?', default="", help="arg")

    args = parser.parse_args()

    if not args.command or args.command == 'help':
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
    os.putenv('PYTHON', PYTHON)
    win_colorprint("using " + PYTHON)

    fname = args.command.replace('-', '_')
    fun = getattr(sys.modules[__name__], fname)  # err if fun not defined
    funargs = []
    # mandatory args
    if args.command in ('test-by-name', 'test-script'):
        if not args.arg:
            sys.exit('command needs an argument')
        funargs = [args.arg]
    # optional args
    if args.command == 'test' and args.arg:
        funargs = [args.arg]
    fun(*funargs)


if __name__ == '__main__':
    main()
