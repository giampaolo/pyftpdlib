.. image:: http://pepy.tech/badge/pyftpdlib
    :target: http://pepy.tech/project/pyftpdlib
    :alt: Downloads

.. image:: https://img.shields.io/travis/giampaolo/pyftpdlib/master.svg?maxAge=3600&label=Linux%20/%20OSX
    :target: https://travis-ci.org/giampaolo/pyftpdlib
    :alt: Linux tests (Travis)

.. image:: https://img.shields.io/appveyor/ci/giampaolo/pyftpdlib/master.svg?maxAge=3600&label=Windows
    :target: https://ci.appveyor.com/project/giampaolo/pyftpdlib
    :alt: Windows tests (Appveyor)

.. image:: https://coveralls.io/repos/github/giampaolo/pyftpdlib/badge.svg?branch=master
    :target: https://coveralls.io/github/giampaolo/pyftpdlib?branch=master
    :alt: Test coverage (coverall.io)

.. image:: https://readthedocs.org/projects/pyftpdlib/badge/?version=latest
    :target: http://pyftpdlib.readthedocs.io/en/latest/?badge=latest
    :alt: Documentation Status

.. image:: https://img.shields.io/pypi/v/pyftpdlib.svg?label=pypi
    :target: https://pypi.python.org/pypi/pyftpdlib/
    :alt: Latest version

.. image:: https://img.shields.io/github/stars/giampaolo/pyftpdlib.svg
    :target: https://github.com/giampaolo/pyftpdlib/
    :alt: Github stars

.. image:: https://img.shields.io/pypi/l/pyftpdlib.svg
    :target: https://pypi.python.org/pypi/pyftpdlib/
    :alt: License

Quick links
===========

- `Home <https://github.com/giampaolo/pyftpdlib>`__
- `Documentation <http://pyftpdlib.readthedocs.io>`__
- `Download <https://pypi.python.org/pypi/pyftpdlib/>`__
- `Blog <http://grodola.blogspot.com/search/label/pyftpdlib>`__
- `Mailing list <http://groups.google.com/group/pyftpdlib/topics>`__
- `What's new <https://github.com/giampaolo/pyftpdlib/blob/master/HISTORY.rst>`__

About
=====

Python FTP server library provides a high-level portable interface to easily
write very efficient, scalable and asynchronous FTP servers with Python. It is
the most complete `RFC-959 <http://www.faqs.org/rfcs/rfc959.html>`__ FTP server
implementation available for `Python <http://www.python.org/>`__ programming
language and it's used in projects like
`Google Chromium <http://www.code.google.com/chromium/>`__ and
`Bazaar <http://bazaar-vcs.org/>`__ and included in
`Debian <http://packages.debian.org/sid/python-pyftpdlib>`__,
`Fedora <https://admin.fedoraproject.org/pkgdb/packages/name/pyftpdlib>`__ and
`FreeBSD <http://www.freshports.org/ftp/py-pyftpdlib/>`__ package repositories.

Features
========

- Extremely **lightweight**, **fast** and **scalable** (see
  `why <https://github.com/giampaolo/pyftpdlib/issues/203>`__ and
  `benchmarks <http://pyftpdlib.readthedocs.io/en/latest/benchmarks.html>`__).
- Uses **sendfile(2)** (see `pysendfile <https://github.com/giampaolo/pysendfile>`__)
  system call for uploads.
- Uses epoll() / kqueue() / select() to handle concurrency asynchronously.
- ...But can optionally skip to a
  `multiple thread / process <http://pyftpdlib.readthedocs.io/en/latest/tutorial.html#changing-the-concurrency-model>`__
  model (as in: you'll be free to block or use slow filesystems).
- Portable: entirely written in pure Python; works with Python from **2.6** to
  **3.5** by using a single code base.
- Supports **FTPS** (`RFC-4217 <http://tools.ietf.org/html/rfc4217>`__),
  **IPv6** (`RFC-2428 <ftp://ftp.rfc-editor.org/in-notes/rfc2428.txt>`__),
  **Unicode** file names (`RFC-2640 <http://tools.ietf.org/html/rfc2640>`__),
  **MLSD/MLST** commands (`RFC-3659 <ftp://ftp.rfc-editor.org/in-notes/rfc3659.txt>`__).
- Support for virtual users and virtual filesystem.
- Extremely flexible system of "authorizers" able to manage both "virtual" and
  "real" users on on both
  `UNIX <http://pyftpdlib.readthedocs.io/en/latest/tutorial.html#unix-ftp-server>`__
  and
  `Windows <http://pyftpdlib.readthedocs.io/en/latest/tutorial.html#windows-ftp-server>`__.
- `Test coverage <https://github.com/giampaolo/pyftpdlib/blob/master/pyftpdlib/test/>`__
  close to 100%.

Performances
============

Despite being written in an intepreted language, pyftpdlib has transfer rates
superior to most common UNIX FTP servers. It also scales better since whereas
vsftpd and proftpd use multiple processes to achieve concurrency, pyftpdlib
will only use one process and handle concurrency asynchronously (see
`the C10K problem <http://www.kegel.com/c10k.html>`__). Here are some
`benchmarks <https://github.com/giampaolo/pyftpdlib/blob/master/scripts/ftpbench>`__
made against my Linux 3.0.0 box, Intel core-duo 3.1 Ghz:

pyftpdlib vs. proftpd 1.3.4
---------------------------

+-----------------------------------------+----------------+----------------+-------------+
| **benchmark type**                      | **pyftpdlib**  | **proftpd**    | **speedup** |
+-----------------------------------------+----------------+----------------+-------------+
| STOR (client -> server)                 |  585.90 MB/sec | 600.49 MB/sec  | -0.02x      |
+-----------------------------------------+----------------+----------------+-------------+
| RETR (server -> client)                 | 1652.72 MB/sec | 1524.05 MB/sec | **+0.08**   |
+-----------------------------------------+----------------+----------------+-------------+
| 300 concurrent clients (connect, login) |    0.19 secs   | 9.98 secs      | **+51x**    |
+-----------------------------------------+----------------+----------------+-------------+
| STOR (1 file with 300 idle clients)     |  585.59 MB/sec | 518.55 MB/sec  | **+0.1x**   |
+-----------------------------------------+----------------+----------------+-------------+
| RETR (1 file with 300 idle clients)     | 1497.58 MB/sec | 1478.19 MB/sec | 0x          |
+-----------------------------------------+----------------+----------------+-------------+
| 300 concurrent clients (RETR 10M file)  |    3.41 secs   | 3.60 secs      | **+0.05x**  |
+-----------------------------------------+----------------+----------------+-------------+
| 300 concurrent clients (STOR 10M file)  |    8.60 secs   | 11.56 secs     | **+0.3x**   |
+-----------------------------------------+----------------+----------------+-------------+
| 300 concurrent clients (QUIT)           |    0.03 secs   | 0.39 secs      | **+12x**    |
+-----------------------------------------+----------------+----------------+-------------+

pyftpdlib vs. vsftpd 2.3.5
--------------------------

+-----------------------------------------+----------------+----------------+-------------+
| **benchmark type**                      | **pyftpdlib**  | **vsftpd**     | **speedup** |
+-----------------------------------------+----------------+----------------+-------------+
| STOR (client -> server)                 |  585.90 MB/sec | 611.73 MB/sec  | -0.04x      |
+-----------------------------------------+----------------+----------------+-------------+
| RETR (server -> client)                 | 1652.72 MB/sec | 1512.92 MB/sec | **+0.09**   |
+-----------------------------------------+----------------+----------------+-------------+
| 300 concurrent clients (connect, login) |    0.19 secs   | 20.39 secs     | **+106x**   |
+-----------------------------------------+----------------+----------------+-------------+
| STOR (1 file with 300 idle clients)     |  585.59 MB/sec | 610.23 MB/sec  | -0.04x      |
+-----------------------------------------+----------------+----------------+-------------+
| RETR (1 file with 300 idle clients)     | 1497.58 MB/sec | 1493.01 MB/sec | 0x          |
+-----------------------------------------+----------------+----------------+-------------+
| 300 concurrent clients (RETR 10M file)  |    3.41 secs   | 3.67 secs      | **+0.07x**  |
+-----------------------------------------+----------------+----------------+-------------+
| 300 concurrent clients (STOR 10M file)  |    8.60 secs   | 9.82 secs      | **+0.07x**  |
+-----------------------------------------+----------------+----------------+-------------+
| 300 concurrent clients (QUIT)           |    0.03 secs   | 0.01 secs      | +0.14x      |
+-----------------------------------------+----------------+----------------+-------------+

For more benchmarks see `here <http://pyftpdlib.readthedocs.io/en/latest/benchmarks.html>`__.

Quick start
===========

.. code-block:: python

    >>> from pyftpdlib.authorizers import DummyAuthorizer
    >>> from pyftpdlib.handlers import FTPHandler
    >>> from pyftpdlib.servers import FTPServer
    >>>
    >>> authorizer = DummyAuthorizer()
    >>> authorizer.add_user("user", "12345", "/home/giampaolo", perm="elradfmwMT")
    >>> authorizer.add_anonymous("/home/nobody")
    >>>
    >>> handler = FTPHandler
    >>> handler.authorizer = authorizer
    >>>
    >>> server = FTPServer(("127.0.0.1", 21), handler)
    >>> server.serve_forever()
    [I 13-02-19 10:55:42] >>> starting FTP server on 127.0.0.1:21 <<<
    [I 13-02-19 10:55:42] poller: <class 'pyftpdlib.ioloop.Epoll'>
    [I 13-02-19 10:55:42] masquerade (NAT) address: None
    [I 13-02-19 10:55:42] passive ports: None
    [I 13-02-19 10:55:42] use sendfile(2): True
    [I 13-02-19 10:55:45] 127.0.0.1:34178-[] FTP session opened (connect)
    [I 13-02-19 10:55:48] 127.0.0.1:34178-[user] USER 'user' logged in.
    [I 13-02-19 10:56:27] 127.0.0.1:34179-[user] RETR /home/giampaolo/.vimrc completed=1 bytes=1700 seconds=0.001
    [I 13-02-19 10:56:39] 127.0.0.1:34179-[user] FTP session closed (disconnect).

`other code samples <http://pyftpdlib.readthedocs.io/en/latest/tutorial.html>`__

Donate
======

A lot of time and effort went into making pyftpdlib as it is right now.
If you feel pyftpdlib is useful to you or your business and want to support its
future development please consider donating me
(`Giampaolo Rodola' <http://grodola.blogspot.com/p/about.html>`_) some money.
I only ask for a small donation, but of course I appreciate any amount.

.. image:: https://www.paypal.com/en_US/i/btn/btn_donateCC_LG.gif
  :target: https://www.paypal.com/cgi-bin/webscr?cmd=_s-xclick&hosted_button_id=ZSSF7G42VA2XE
  :alt: Donate via PayPal

Don't want to donate money? Then maybe you could
`write me a recommendation on Linkedin <http://www.linkedin.com/in/grodola>`_.
In case you're using pyftpdlib into a software of yours
`mail me <http://grodola.blogspot.com/p/about.html>`_ and I'll add your
software to the
`adoptions list <http://pyftpdlib.readthedocs.io/en/latest/adoptions.html>`__.

Trademarks
==========

Some famous trademarks which adopted pyftpdlib (`complete list <http://pyftpdlib.readthedocs.io/en/latest/adoptions.html>`__).

.. image:: docs/images/chrome.jpg
  :target: http://www.google.com/chrome
.. image:: docs/images/debian.png
  :target: http://www.debian.org
.. image:: docs/images/fedora.png
  :target: http://fedoraproject.org/
.. image:: docs/images/freebsd.gif
  :target: http://www.freebsd.org
.. image:: docs/images/openerp.jpg
  :target: http://openerp.com
.. image:: docs/images/bazaar.jpg
  :target: http://bazaar-vcs.org
.. image:: docs/images/bitsontherun.png
  :target: http://www.bitsontherun.com
.. image:: docs/images/openvms.png
  :target: http://www.openvms.org/
.. image:: docs/images/smartfile.png
  :target: https://www.smartfile.com/
