#!/usr/bin/env python
# setup.py

"""pyftpdlib installer.

To install pyftpdlib just open a command shell and run:
> python setup.py install
"""

from distutils.core import setup

long_descr = """\
Python FTP server library, based on asyncore framework, provides
an high-level portable interface to easily write asynchronous
FTP servers with Python."""

setup(
    name='pyftpdlib',
    version="0.5.0",
    description='High-level asynchronous FTP server library',
    long_description=long_descr,
    license='MIT License',
    platforms='Platform Independent',
    author="Giampaolo Rodola'",
    author_email='g.rodola@gmail.com',
    url='http://code.google.com/p/pyftpdlib/',
    download_url='http://pyftpdlib.googlecode.com/files/pyftpdlib-0.5.0.tar.gz',
    packages=['pyftpdlib'],
    classifiers=[
          'Development Status :: 4 - Beta',
          'Environment :: Console',
          'Intended Audience :: Developers',
          'Intended Audience :: System Administrators',
          'License :: OSI Approved :: MIT License',
          'Operating System :: OS Independent',
          'Programming Language :: Python',
          'Topic :: Internet :: File Transfer Protocol (FTP)',
          'Topic :: Software Development :: Libraries :: Python Modules'
          ],
    )
