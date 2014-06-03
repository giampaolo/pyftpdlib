#!/usr/bin/env python

#  pyftpdlib is released under the MIT license, reproduced below:
#  ======================================================================
#  Copyright (C) 2007-2014 Giampaolo Rodola' <g.rodola@gmail.com>
#
#                         All Rights Reserved
#
# Permission is hereby granted, free of charge, to any person
# obtaining a copy of this software and associated documentation
# files (the "Software"), to deal in the Software without
# restriction, including without limitation the rights to use,
# copy, modify, merge, publish, distribute, sublicense, and/or sell
# copies of the Software, and to permit persons to whom the
# Software is furnished to do so, subject to the following
# conditions:
#
# The above copyright notice and this permission notice shall be
# included in all copies or substantial portions of the Software.
#
# THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND,
# EXPRESS OR IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES
# OF MERCHANTABILITY, FITNESS FOR A PARTICULAR PURPOSE AND
# NONINFRINGEMENT. IN NO EVENT SHALL THE AUTHORS OR COPYRIGHT
# HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER LIABILITY,
# WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING
# FROM, OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR
# OTHER DEALINGS IN THE SOFTWARE.
#
#  ======================================================================

"""pyftpdlib installer.

$ python setup.py install
"""

import os
import sys
try:
    from setuptools import setup
except ImportError:
    from distutils.core import setup


def get_version():
    INIT = os.path.abspath(os.path.join(os.path.dirname(__file__),
                           'pyftpdlib', '__init__.py'))
    f = open(INIT, 'r')
    try:
        for line in f:
            if line.startswith('__ver__'):
                ret = eval(line.strip().split(' = ')[1])
                assert ret.count('.') == 2, ret
                for num in ret.split('.'):
                    assert num.isdigit(), ret
                return ret
        raise ValueError("couldn't find version string")
    finally:
        f.close()


def term_supports_colors():
    try:
        import curses
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
        elif ok:   # green
            attr.append('32')
        else:   # red
            attr.append('31')
        if bold:
            attr.append('1')
        return '\x1b[%sm%s\x1b[0m' % (';'.join(attr), s)


if sys.version_info < (2, 4):
    sys.exit('python version not supported (min 2.4)')

VERSION = get_version()


def main():
    setup(
        name='pyftpdlib',
        version=get_version(),
        description='Very fast asynchronous FTP server library',
        long_description=open('README.rst').read(),
        license='MIT',
        platforms='Platform Independent',
        author="Giampaolo Rodola'",
        author_email='g.rodola@gmail.com',
        url='https://github.com/giampaolo/pyftpdlib/',
        packages=['pyftpdlib', 'pyftpdlib/contrib'],
        keywords=['ftp', 'ftps', 'server', 'ftpd', 'daemon', 'python', 'ssl',
                  'sendfile', 'asynchronous', 'nonblocking', 'eventdriven',
                  'rfc959', 'rfc1123', 'rfc2228', 'rfc2428', 'rfc2640',
                  'rfc3659'],
        extras_require={
            'ssl': ["PyOpenSSL"],
            'sendfile': ["pysendfile"],
        },
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
            'Programming Language :: Python :: 2',
            'Programming Language :: Python :: 2.4',
            'Programming Language :: Python :: 2.5',
            'Programming Language :: Python :: 2.6',
            'Programming Language :: Python :: 2.7',
            'Programming Language :: Python :: 3',
            'Programming Language :: Python :: 3.0',
            'Programming Language :: Python :: 3.1',
            'Programming Language :: Python :: 3.2',
            'Programming Language :: Python :: 3.3',
            'Programming Language :: Python :: 3.4',
        ],
    )

    # suggest to install pysendfile
    if os.name == 'posix' and sys.version_info >= (2, 5):
        try:
            # os.sendfile() appeared in python 3.3
            # http://bugs.python.org/issue10882
            if not hasattr(os, 'sendfile'):
                # fallback on using third-party pysendfile module
                # https://github.com/giampaolo/pysendfile/
                import sendfile
                if hasattr(sendfile, 'has_sf_hdtr'):  # old 1.2.4 version
                    raise ImportError
        except ImportError:
            msg = "\nyou might want to install 'pysendfile' module to " \
                  "speedup transfers:\n" \
                  "https://github.com/giampaolo/pysendfile/\n"
            sys.stderr.write(hilite(msg, ok=0, bold=1))

    try:
        from OpenSSL import SSL  # NOQA
    except ImportError:
        msg = "\nyou might want to install 'PyOpenSSL' module to support " \
              "FTPS\n"
        sys.stderr.write(hilite(msg, ok=0, bold=1))


if __name__ == '__main__':
    main()
