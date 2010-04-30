#!/usr/bin/env python
# $Id$

"""pyftpdlib installer.

To install pyftpdlib just open a command shell and run:
> python setup.py install
"""

from distutils.core import setup

# Hack for Python 3 to tell distutils to run 2to3 against the files
# copied in the build directory before installing.
try:
    from distutils.command.build_py import build_py_2to3 as build_py
except ImportError:
    from distutils.command.build_py import build_py


name = 'pyftpdlib'
version = '0.5.2'
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
              'rfc2228', 'rfc2428', 'rfc3659'],
    cmdclass={'build_py' : build_py},
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
          ],
    )
