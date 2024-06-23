# Copyright (C) 2007 Giampaolo Rodola' <g.rodola@gmail.com>.
# Use of this source code is governed by MIT license that can be
# found in the LICENSE file.

"""pyftpdlib installer.

$ python setup.py install
"""


import ast
import os
import sys
import textwrap


try:
    from setuptools import setup
except ImportError:
    from distutils.core import setup


def get_version():
    INIT = os.path.abspath(
        os.path.join(os.path.dirname(__file__), 'pyftpdlib', '__init__.py')
    )
    with open(INIT) as f:
        for line in f:
            if line.startswith('__ver__'):
                ret = ast.literal_eval(line.strip().split(' = ')[1])
                assert ret.count('.') == 2, ret
                for num in ret.split('.'):
                    assert num.isdigit(), ret
                return ret
        raise ValueError("couldn't find version string")


def term_supports_colors():
    try:
        import curses  # noqa: PLC0415

        assert sys.stderr.isatty()
        curses.setupterm()
        assert curses.tigetnum("colors") > 0
    except Exception:
        return False
    else:
        return True


def hilite(s, ok=True, bold=False):
    """Return an highlighted version of 's'."""
    if not term_supports_colors():
        return s
    else:
        attr = []
        if ok is None:  # no color
            pass
        elif ok:
            attr.append('32')  # green
        else:
            attr.append('31')  # red
        if bold:
            attr.append('1')
        return '\x1b[%sm%s\x1b[0m' % (';'.join(attr), s)


if sys.version_info[0] < 3:
    sys.exit(
        'Python 2 is no longer supported. Latest version is 1.5.10; use:\n'
        'python3 -m pip install pyftpdlib==1.5.10'
    )

extras_require = {'ssl': ["PyOpenSSL"]}

VERSION = get_version()

with open('README.rst') as f:
    long_description = f.read()


def main():
    setup(
        name='pyftpdlib',
        version=get_version(),
        description='Very fast asynchronous FTP server library',
        long_description=long_description,
        license='MIT',
        platforms='Platform Independent',
        author="Giampaolo Rodola'",
        author_email='g.rodola@gmail.com',
        url='https://github.com/giampaolo/pyftpdlib/',
        packages=['pyftpdlib', 'pyftpdlib.test'],
        scripts=['scripts/ftpbench'],
        package_data={
            "pyftpdlib.test": [
                "README",
                'keycert.pem',
            ],
        },
        # fmt: off
        keywords=['ftp', 'ftps', 'server', 'ftpd', 'daemon', 'python', 'ssl',
                  'sendfile', 'asynchronous', 'nonblocking', 'eventdriven',
                  'rfc959', 'rfc1123', 'rfc2228', 'rfc2428', 'rfc2640',
                  'rfc3659'],
        # fmt: on
        extras_require=extras_require,
        classifiers=[
            'Development Status :: 5 - Production/Stable',
            'Environment :: Console',
            'Intended Audience :: Developers',
            'Intended Audience :: System Administrators',
            'License :: OSI Approved :: MIT License',
            'Operating System :: OS Independent',
            'Programming Language :: Python',
            'Topic :: Internet :: File Transfer Protocol (FTP)',
            'Topic :: Software Development :: Libraries :: Python Modules',
            'Topic :: System :: Filesystems',
            'Programming Language :: Python',
            'Programming Language :: Python :: 3',
        ],
    )

    try:
        from OpenSSL import SSL  # NOQA
    except ImportError:
        msg = textwrap.dedent("""
            'pyopenssl' third-party module is not installed. This means
            FTPS support will be disabled. You can install it with:
            'pip install pyopenssl'.""")
        print(hilite(msg, ok=False), file=sys.stderr)


if __name__ == '__main__':
    main()
