#!/usr/bin/env python
# $Id$

"""pyftpdlib installer.

To install pyftpdlib just open a command shell and run:
> python setup.py install
"""

import os
import sys
try:
    from setuptools import setup
except ImportError:
    from distutils.core import setup

name = 'pyftpdlib'
version = '0.7.0'
download_url = "http://pyftpdlib.googlecode.com/files/" + name + "-" + \
                                                          version + ".tar.gz"

setup(
    name=name,
    version=version,
    description='High-level asynchronous FTP server library',
    long_description="Python FTP server library provides an high-level portable "
                     "interface to easily write asynchronous FTP servers with "
                     "Python.",
    license='MIT License',
    platforms='Platform Independent',
    author="Giampaolo Rodola'",
    author_email='g.rodola@gmail.com',
    url='http://code.google.com/p/pyftpdlib/',
    download_url=download_url,
    packages=['pyftpdlib', 'pyftpdlib/contrib'],
    keywords=['ftp', 'server', 'ftpd', 'daemon', 'python', 'rfc959', 'rfc1123',
              'rfc2228', 'rfc2428', 'rfc3659', 'ftps'],
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
          ],
    )

if os.name == 'posix':
    try:
        import sendfile
    except ImportError:
        msg = "\nYou might want to install py-sendfile module to speedup " \
              "transfers:\nhttp://code.google.com/p/py-sendfile/\n"
        if sys.stderr.isatty():
            sys.stderr.write('\x1b[1m%s\x1b[0m' % msg)
        else:
            sys.stderr.write(msg)
