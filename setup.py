#!/usr/bin/env python
# setup.py

from distutils.core import setup

setup(name='pyftpdlib',
      version="0.1.1",       
      author='billiejoex',
      author_email='billiejoex@gmail.com',
      maintainer='billiejoex',
      maintainer_email='billiejoex@gmail.com',
      url='http://billiejoex.altervista.org',      
      description='High-level asynchronous FTP server library',
      classifiers=[
          'Development Status :: Beta',
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
