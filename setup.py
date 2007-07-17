#!/usr/bin/env python
# setup.py

from distutils.core import setup

setup(name='Python FTP server library (pyftpdlib)',
      version="v0.1.0 (experimental)",       
      author='billiejoex',
      author_email='billiejoex@gmail.com',
      maintainer='billiejoex',
      maintainer_email='billiejoex@gmail.com',
      url='http://billiejoex.altervista.org',
      description='High level FTP server library',
      long_description="""
Python FTP server library provides an high-level portable interface\
to easily write asynchronous FTP servers with Python.\
Based on asyncore / asynchat frameworks pyftpdlib is actually the most \
complete RFC959 FTP server implementation available for Python language.""",
      classifiers=[
          'Development Status :: Experimental',
          'Environment :: Networking',
          'Intended Audience :: Network programmers',
          'License :: GNU',
          'Operating System :: MacOS :: MacOS X',
          'Operating System :: Microsoft :: Windows',
          'Operating System :: POSIX',
          'Programming Language :: Python',
          ],
      packages = ['pyftpdlib'],
      )
