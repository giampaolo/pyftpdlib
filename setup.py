#!/usr/bin/env python
# setup.py

from distutils.core import setup

long_descr = """
Python FTP server library, based on asyncore framework, provides
an high-level portable interface to easily write asynchronous
FTP servers with Python."""

setup(
    name='pyftpdlib',
    version = "0.2.0",
    description = 'High-level asynchronous FTP server library',
    long_description = long_descr,
    license = 'MIT License',
    platforms = 'Platform Independent',
    author = "Giampaolo Rodola'",
    author_email = 'g.rodola@gmail.com',
    url = 'http://code.google.com/p/pyftpdlib/',
    download_url = 'http://code.google.com/p/pyftpdlib/downloads/list',
    packages = ['pyftpdlib'],
    classifiers = [
          'Development Status :: 4 - Beta',
          'Environment :: Console',
          'License :: OSI Approved :: MIT License',
          'Operating System :: OS Independent',
          'Programming Language :: Python',
          'Topic :: Internet :: File Transfer Protocol (FTP)'
          ],
    )
