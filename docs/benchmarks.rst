==========
Benchmarks
==========

pyftpdlib 0.7.0 vs. pyftpdlib 1.0.0
-----------------------------------

+-----------------------------------------+-----------------+----------------+------------+
| *benchmark type*                        | *0.7.0*         | *1.0.0*        | *speedup*  |
+=========================================+=================+================+============+
| STOR (client -> server)                 |   528.63 MB/sec | 585.90 MB/sec  | **+0.1x**  |
+-----------------------------------------+-----------------+----------------+------------+
| RETR (server -> client)                 |  1702.07 MB/sec | 1652.72 MB/sec | -0.02x     |
+-----------------------------------------+-----------------+----------------+------------+
| 300 concurrent clients (connect, login) |       1.70 secs | 0.19 secs      | **+8x**    |
+-----------------------------------------+-----------------+----------------+------------+
| STOR (1 file with 300 idle clients)     |    60.77 MB/sec | 585.59 MB/sec  | **+8.6x**  |
+-----------------------------------------+-----------------+----------------+------------+
| RETR (1 file with 300 idle clients)     |    63.46 MB/sec | 1497.58 MB/sec | **+22.5x** |
+-----------------------------------------+-----------------+----------------+------------+
| 300 concurrent clients (RETR 10M file)  |       4.68 secs | 3.41 secs      | **+0.3x**  |
+-----------------------------------------+-----------------+----------------+------------+
| 300 concurrent clients (STOR 10M file)  |      10.13 secs | 8.78 secs      | **+0.1x**  |
+-----------------------------------------+-----------------+----------------+------------+
| 300 concurrent clients (QUIT)           |       0.02 secs | 0.02 secs      | 0x         |
+-----------------------------------------+-----------------+----------------+------------+

pyftpdlib vs. proftpd 1.3.4
---------------------------

+-----------------------------------------+-----------------+----------------+------------+
| *benchmark type*                        | *pyftpdlib*     | *proftpd*      | *speedup*  |
+=========================================+=================+================+============+
| STOR (client -> server)                 |   585.90 MB/sec | 600.49 MB/sec  | -0.02x     |
+-----------------------------------------+-----------------+----------------+------------+
| RETR (server -> client)                 |  1652.72 MB/sec | 1524.05 MB/sec | **+0.08**  |
+-----------------------------------------+-----------------+----------------+------------+
| 300 concurrent clients (connect, login) |     0.19 secs   | 9.98 secs      | **+51x**   |
+-----------------------------------------+-----------------+----------------+------------+
| STOR (1 file with 300 idle clients)     |   585.59 MB/sec | 518.55 MB/sec  | **+0.1x**  |
+-----------------------------------------+-----------------+----------------+------------+
| RETR (1 file with 300 idle clients)     |  1497.58 MB/sec | 1478.19 MB/sec | 0x         |
+-----------------------------------------+-----------------+----------------+------------+
| 300 concurrent clients (RETR 10M file)  |     3.41 secs   | 3.60 secs      | **+0.05x** |
+-----------------------------------------+-----------------+----------------+------------+
| 300 concurrent clients (STOR 10M file)  |     8.60 secs   | 11.56 secs     | **+0.3x**  |
+-----------------------------------------+-----------------+----------------+------------+
| 300 concurrent clients (QUIT)           |     0.03 secs   | 0.39 secs      | **+12x**   |
+-----------------------------------------+-----------------+----------------+------------+

pyftpdlib vs. vsftpd 2.3.5
--------------------------

+-----------------------------------------+----------------+----------------+-------------+
| *benchmark type*                        |   *pyftpdlib*  | *vsftpd*       | *speedup*   |
+=========================================+================+================+=============+
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

pyftpdlib vs. Twisted 12.3
--------------------------

By using *sendfile()* (Twisted *does not* support sendfile()):

+-----------------------------------------+----------------+----------------+-------------+
| *benchmark type*                        |  *pyftpdlib*   |  *twisted*     | *speedup*   |
+=========================================+================+================+=============+
| STOR (client -> server)                 |  585.90 MB/sec | 496.44 MB/sec  | **+0.01x**  |
+-----------------------------------------+----------------+----------------+-------------+
| RETR (server -> client)                 | 1652.72 MB/sec | 283.24 MB/sec  | **+4.8x**   |
+-----------------------------------------+----------------+----------------+-------------+
| 300 concurrent clients (connect, login) |    0.19 secs   | 0.19 secs      | +0x         |
+-----------------------------------------+----------------+----------------+-------------+
| STOR (1 file with 300 idle clients)     |  585.59 MB/sec | 506.55 MB/sec  | **+0.16x**  |
+-----------------------------------------+----------------+----------------+-------------+
| RETR (1 file with 300 idle clients)     | 1497.58 MB/sec | 280.63 MB/sec  | **+4.3x**   |
+-----------------------------------------+----------------+----------------+-------------+
| 300 concurrent clients (RETR 10M file)  |    3.41 secs   | 11.40 secs     | **+2.3x**   |
+-----------------------------------------+----------------+----------------+-------------+
| 300 concurrent clients (STOR 10M file)  |    8.60 secs   | 9.22 secs      | **+0.07x**  |
+-----------------------------------------+----------------+----------------+-------------+
| 300 concurrent clients (QUIT)           |    0.03 secs   | 0.09 secs      | **+2x**     |
+-----------------------------------------+----------------+----------------+-------------+

By using plain *send()*:

+-----------------------------------------+----------------+---------------+--------------+
| *benchmark type*                        | *tpdlib*       | *twisted*     | *speedup*    |
+=========================================+================+===============+==============+
| RETR (server -> client)                 |  894.29 MB/sec | 283.24 MB/sec | **+2.1x**    |
+-----------------------------------------+----------------+---------------+--------------+
| RETR (1 file with 300 idle clients)     |  900.98 MB/sec | 280.63 MB/sec | **+2.1x**    |
+-----------------------------------------+----------------+---------------+--------------+


Memory usage
------------

*Values on UNIX are calculated as (rss - shared).*

+------------------------------------------+-------------+-----------------+----------------+----------------+
| *benchmark type*                         | *pyftpdlib* | *proftpd 1.3.4* | *vsftpd 2.3.5* | *twisted 12.3* |
+==========================================+=============+=================+================+================+
| Starting with                            | 6.7M        | 1.4M            | 352.0K         | 13.4M          |
+------------------------------------------+-------------+-----------------+----------------+----------------+
| STOR (1 client)                          | 6.7M        | 8.5M            | 816.0K         | 13.5M          |
+------------------------------------------+-------------+-----------------+----------------+----------------+
| RETR (1 client)                          | 6.8M        | 8.5M            | 816.0K         | 13.5M          |
+------------------------------------------+-------------+-----------------+----------------+----------------+
| 300 concurrent clients (connect, login)  | **8.8M**    | 568.6M          | 140.9M         | 13.5M          |
+------------------------------------------+-------------+-----------------+----------------+----------------+
| STOR (1 file with 300 idle clients)      | **8.8M**    | 570.6M          | 141.4M         | 13.5M          |
+------------------------------------------+-------------+-----------------+----------------+----------------+
| RETR (1 file with 300 idle clients)      | **8.8M**    | 570.6M          | 141.4M         | 13.5M          |
+------------------------------------------+-------------+-----------------+----------------+----------------+
| 300 concurrent clients (RETR 10.0M file) | **10.8M**   | 568.6M          | 140.9M         | 24.5M          |
+------------------------------------------+-------------+-----------------+----------------+----------------+
| 300 concurrent clients (STOR 10.0M file) | **12.6**    | 568.7M          | 140.9M         | 24.7M          |
+------------------------------------------+-------------+-----------------+----------------+----------------+

Interpreting the results
------------------------

pyftpdlib and `proftpd <http://www.proftpd.org/>`__ / `vsftpd <https://security.appspot.com/vsftpd.html>`__
look pretty much equally fast. The huge difference is noticeable in scalability
though, because of the concurrency model adopted.
Both proftpd and vsftpd spawn a new process for every connected client, where
pyftpdlib doesn't (see `the C10k problem <http://www.kegel.com/c10k.html>`__).
The outcome is well noticeable on connect/login benchmarks and memory
benchmarks.

The huge differences between
`0.7.0 <https://pypi.python.org/packages/source/p/pyftpdlib/pyftpdlib-0.7.0.tar.gz>`__ and
`1.0.0 <https://pypi.python.org/packages/source/p/pyftpdlib/pyftpdlib-1.0.0.tar.gz>`__
versions of pyftpdlib are due to fix of issue 203.
On Linux we now use `epoll() <http://linux.die.net/man/4/epoll>`__ which scales
considerably better than `select() <http://linux.die.net/man/2/select>`__.
The fact that we're downloading a file with 300 idle clients doesn't make any
difference for *epoll()*. We might as well had 5000 idle clients and the result
would have been the same.
On Windows, where we still use select(), 1.0.0 still wins hands down as the
asyncore loop was reimplemented from scratch in order to support fd
un/registration and modification
(see `issue 203 <https://github.com/giampaolo/pyftpdlib/issues/203>`__).
All the benchmarks were conducted on a Linux Ubuntu 12.04  Intel core duo - 3.1
Ghz box.

Setup
-----

The following setup was used before running every benchmark:

proftpd
^^^^^^^

::

    # /etc/proftpd/proftpd.conf

    MaxInstances        2000


...followed by:

::

    $ sudo service proftpd restart


vsftpd
^^^^^^

::

    # /etc/vsftpd.conf

    local_enable=YES
    write_enable=YES
    max_clients=2000
    max_per_ip=2000


...followed by:

::

    $ sudo service vsftpd restart


twisted FTP server
^^^^^^^^^^^^^^^^^^

::

    from twisted.protocols.ftp import FTPFactory, FTPRealm
    from twisted.cred.portal import Portal
    from twisted.cred.checkers import AllowAnonymousAccess, FilePasswordDB
    from twisted.internet import reactor
    import resource

    soft, hard = resource.getrlimit(resource.RLIMIT_NOFILE)
    resource.setrlimit(resource.RLIMIT_NOFILE, (hard, hard))
    open('pass.dat', 'w').write('user:some-passwd')
    p = Portal(FTPRealm('./'),
    [AllowAnonymousAccess(), FilePasswordDB("pass.dat")])
    f = FTPFactory(p)
    reactor.listenTCP(21, f)
    reactor.run()


...followed by:

::

    $ sudo python twist_ftpd.py



pyftpdlib
^^^^^^^^^

The following patch was applied first:

::

    Index: pyftpdlib/servers.py
    ===================================================================
    --- pyftpdlib/servers.py    (revisione 1154)
    +++ pyftpdlib/servers.py    (copia locale)
    @@ -494,3 +494,10 @@

    def _map_len(self):
    return len(multiprocessing.active_children())
    +
    +import resource
    +soft, hard = resource.getrlimit(resource.RLIMIT_NOFILE)
    +resource.setrlimit(resource.RLIMIT_NOFILE, (hard, hard))
    +FTPServer.max_cons = 0


...followed by:

::

    $ sudo python demo/unix_daemon.py


The `benchmark script <https://github.com/giampaolo/pyftpdlib/blob/master/scripts/ftpbench>`__
was run as:

::

    python scripts/ftpbench -u USERNAME -p PASSWORD -b all -n 300


...and for the memory test:

::

    python scripts/ftpbench -u USERNAME -p PASSWORD -b all -n 300 -k FTP_SERVER_PID
