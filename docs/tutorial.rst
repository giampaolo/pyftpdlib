========
Tutorial
========

.. contents:: Table of Contents

Below is a set of example scripts showing some of the possible customizations
that can be done with pyftpdlib.  Some of them are included in
`demo <https://github.com/giampaolo/pyftpdlib/blob/master/demo/>`__
directory of pyftpdlib source distribution.

A Base FTP server
=================

The script below uses a basic configuration and it's probably the best
starting point to understand how things work. It uses the base
`DummyAuthorizer <api.html#pyftpdlib.authorizers.DummyAuthorizer>`__
for adding a bunch of "virtual" users, sets a limit for
`incoming connections <api.html#pyftpdlib.servers.FTPServer.max_cons>`__
and a range of `passive ports <api.html#pyftpdlib.handlers.FTPHandler.passive_ports>`__.

`source code <https://github.com/giampaolo/pyftpdlib/blob/master/demo/basic_ftpd.py>`__

.. code-block:: python

    import os

    from pyftpdlib.authorizers import DummyAuthorizer
    from pyftpdlib.handlers import FTPHandler
    from pyftpdlib.servers import FTPServer

    def main():
        # Instantiate a dummy authorizer for managing 'virtual' users
        authorizer = DummyAuthorizer()

        # Define a new user having full r/w permissions and a read-only
        # anonymous user
        authorizer.add_user('user', '12345', '.', perm='elradfmwMT')
        authorizer.add_anonymous(os.getcwd())

        # Instantiate FTP handler class
        handler = FTPHandler
        handler.authorizer = authorizer

        # Define a customized banner (string returned when client connects)
        handler.banner = "pyftpdlib based ftpd ready."

        # Specify a masquerade address and the range of ports to use for
        # passive connections.  Decomment in case you're behind a NAT.
        #handler.masquerade_address = '151.25.42.11'
        #handler.passive_ports = range(60000, 65535)

        # Instantiate FTP server class and listen on 0.0.0.0:2121
        address = ('', 2121)
        server = FTPServer(address, handler)

        # set a limit for connections
        server.max_cons = 256
        server.max_cons_per_ip = 5

        # start ftp server
        server.serve_forever()

    if __name__ == '__main__':
        main()


Logging management
==================

pyftpdlib uses the
`logging <http://docs.python.org/library/logging.html logging>`__
module to handle logging. If you don't configure logging pyftpdlib will write
logs to stderr.
In order to configure logging you should do it *before* calling serve_forever().
Example logging to a file:

.. code-block:: python

    import logging

    from pyftpdlib.handlers import FTPHandler
    from pyftpdlib.servers import FTPServer
    from pyftpdlib.authorizers import DummyAuthorizer

    authorizer = DummyAuthorizer()
    authorizer.add_user('user', '12345', '.', perm='elradfmwMT')
    handler = FTPHandler
    handler.authorizer = authorizer

    logging.basicConfig(filename='/var/log/pyftpd.log', level=logging.INFO)

    server = FTPServer(('', 2121), handler)
    server.serve_forever()

DEBUG logging
^^^^^^^^^^^^^

You may want to enable DEBUG logging to observe commands and responses
exchanged by client and server. DEBUG logging will also log internal errors
which may occur on socket related calls such as ``send()`` and ``recv()``.
To enable DEBUG logging from code use:

.. code-block:: python

    logging.basicConfig(level=logging.DEBUG)

To enable DEBUG logging from command line use:

.. code-block:: bash

    python -m pyftpdlib -D

DEBUG logs look like this:

::

    [I 2017-11-07 12:03:44] >>> starting FTP server on 0.0.0.0:2121, pid=22991 <<<
    [I 2017-11-07 12:03:44] concurrency model: async
    [I 2017-11-07 12:03:44] masquerade (NAT) address: None
    [I 2017-11-07 12:03:44] passive ports: None
    [D 2017-11-07 12:03:44] poller: 'pyftpdlib.ioloop.Epoll'
    [D 2017-11-07 12:03:44] authorizer: 'pyftpdlib.authorizers.DummyAuthorizer'
    [D 2017-11-07 12:03:44] use sendfile(2): True
    [D 2017-11-07 12:03:44] handler: 'pyftpdlib.handlers.FTPHandler'
    [D 2017-11-07 12:03:44] max connections: 512
    [D 2017-11-07 12:03:44] max connections per ip: unlimited
    [D 2017-11-07 12:03:44] timeout: 300
    [D 2017-11-07 12:03:44] banner: 'pyftpdlib 1.5.4 ready.'
    [D 2017-11-07 12:03:44] max login attempts: 3
    [I 2017-11-07 12:03:44] 127.0.0.1:37303-[] FTP session opened (connect)
    [D 2017-11-07 12:03:44] 127.0.0.1:37303-[] -> 220 pyftpdlib 1.0.0 ready.
    [D 2017-11-07 12:03:44] 127.0.0.1:37303-[] <- USER user
    [D 2017-11-07 12:03:44] 127.0.0.1:37303-[] -> 331 Username ok, send password.
    [D 2017-11-07 12:03:44] 127.0.0.1:37303-[user] <- PASS ******
    [D 2017-11-07 12:03:44] 127.0.0.1:37303-[user] -> 230 Login successful.
    [I 2017-11-07 12:03:44] 127.0.0.1:37303-[user] USER 'user' logged in.
    [D 2017-11-07 12:03:44] 127.0.0.1:37303-[user] <- TYPE I
    [D 2017-11-07 12:03:44] 127.0.0.1:37303-[user] -> 200 Type set to: Binary.
    [D 2017-11-07 12:03:44] 127.0.0.1:37303-[user] <- PASV
    [D 2017-11-07 12:03:44] 127.0.0.1:37303-[user] -> 227 Entering passive mode (127,0,0,1,233,208).
    [D 2017-11-07 12:03:44] 127.0.0.1:37303-[user] <- RETR tmp-pyftpdlib
    [D 2017-11-07 12:03:44] 127.0.0.1:37303-[user] -> 125 Data connection already open. Transfer starting.
    [D 2017-11-07 12:03:44] 127.0.0.1:37303-[user] -> 226 Transfer complete.
    [I 2017-11-07 12:03:44] 127.0.0.1:37303-[user] RETR /home/giampaolo/IMG29312.JPG completed=1 bytes=1205012 seconds=0.003
    [D 2017-11-07 12:03:44] 127.0.0.1:37303-[user] <- QUIT
    [D 2017-11-07 12:03:44] 127.0.0.1:37303-[user] -> 221 Goodbye.
    [I 2017-11-07 12:03:44] 127.0.0.1:37303-[user] FTP session closed (disconnect).


Changing log line prefix
^^^^^^^^^^^^^^^^^^^^^^^^

.. code-block:: python

    handler = FTPHandler
    handler.log_prefix = 'XXX [%(username)s]@%(remote_ip)s'
    server = FTPServer(('localhost', 2121), handler)
    server.serve_forever()

Logs will now look like this:

::

    [I 13-02-01 19:12:26] XXX []@127.0.0.1 FTP session opened (connect)
    [I 13-02-01 19:12:26] XXX [user]@127.0.0.1 USER 'user' logged in.


Storing passwords as hash digests
=================================

Using FTP server library with the default
`DummyAuthorizer <api.html#pyftpdlib.authorizers.DummyAuthorizer>`__ means that
passwords will be stored in clear-text. An end-user ftpd using the default
dummy authorizer would typically require a configuration file for
authenticating users and their passwords but storing clear-text passwords is of
course undesirable. The most common way to do things in such case would be
first creating new users and then storing their usernames + passwords as hash
digests into a file or wherever you find it convenient. The example below shows
how to store passwords as one-way hashes by using md5 algorithm.

`source code <https://github.com/giampaolo/pyftpdlib/blob/master/demo/md5_ftpd.py>`__

.. code-block:: python

    import os
    import sys
    from hashlib import md5

    from pyftpdlib.handlers import FTPHandler
    from pyftpdlib.servers import FTPServer
    from pyftpdlib.authorizers import DummyAuthorizer, AuthenticationFailed


    class DummyMD5Authorizer(DummyAuthorizer):

        def validate_authentication(self, username, password, handler):
            if sys.version_info >= (3, 0):
                password = password.encode('latin1')
            hash = md5(password).hexdigest()
            try:
                if self.user_table[username]['pwd'] != hash:
                    raise KeyError
            except KeyError:
                raise AuthenticationFailed


    def main():
        # get a hash digest from a clear-text password
        password = '12345'
        if sys.version_info >= (3, 0):
            password = password.encode('latin1')
        hash = md5(password).hexdigest()
        authorizer = DummyMD5Authorizer()
        authorizer.add_user('user', hash, os.getcwd(), perm='elradfmwMT')
        authorizer.add_anonymous(os.getcwd())
        handler = FTPHandler
        handler.authorizer = authorizer
        server = FTPServer(('', 2121), handler)
        server.serve_forever()

    if __name__ == "__main__":
        main()



Unix FTP Server
===============

If you're running a Unix system you may want to configure your ftpd to include
support for "real" users existing on the system and navigate the real
filesystem. The example below uses
`UnixAuthorizer <api.html#pyftpdlib.authorizers.UnixAuthorizer>`__ and
`UnixFilesystem <api.html#pyftpdlib.filesystems.UnixFilesystem>`__
classes to do so.

.. code-block:: python

    from pyftpdlib.handlers import FTPHandler
    from pyftpdlib.servers import FTPServer
    from pyftpdlib.authorizers import UnixAuthorizer
    from pyftpdlib.filesystems import UnixFilesystem

    def main():
        authorizer = UnixAuthorizer(rejected_users=["root"], require_valid_shell=True)
        handler = FTPHandler
        handler.authorizer = authorizer
        handler.abstracted_fs = UnixFilesystem
        server = FTPServer(('', 21), handler)
        server.serve_forever()

    if __name__ == "__main__":
        main()


Windows FTP Server
==================

The following code shows how to implement a basic authorizer for a Windows NT
workstation to authenticate against existing Windows user accounts. This code
requires Mark Hammond's
`pywin32 <http://starship.python.net/crew/mhammond/win32/>`__ extension to be
installed.

`source code <https://github.com/giampaolo/pyftpdlib/blob/master/demo/winnt_ftpd.py>`__

.. code-block:: python

    from pyftpdlib.handlers import FTPHandler
    from pyftpdlib.servers import FTPServer
    from pyftpdlib.authorizers import WindowsAuthorizer

    def main():
        authorizer = WindowsAuthorizer()
        # Use Guest user with empty password to handle anonymous sessions.
        # Guest user must be enabled first, empty password set and profile
        # directory specified.
        #authorizer = WindowsAuthorizer(anonymous_user="Guest", anonymous_password="")
        handler = FTPHandler
        handler.authorizer = authorizer
        server = FTPServer(('', 2121), handler)
        server.serve_forever()

    if __name__ == "__main__":
        main()

.. _changing-the-concurrency-model:

Changing the concurrency model
==============================

By nature pyftpdlib is asynchronous. That means it uses a single process/thread
to handle multiple client connections and file transfers. This is why it is so
fast, lightweight and scalable (see `benchmarks <benchmarks.html>`__). The
async model has one big drawback though: the code cannot contain instructions
which blocks for a long period of time, otherwise the whole FTP server will
hang.
As such the user should avoid calls such as ``time.sleep(3)``, heavy db
queries, etc.  Moreover, there are cases where the async model is not
appropriate, and that is when you're dealing with a particularly slow
filesystem (say a network filesystem such as samba). If the filesystem is slow
(say, a ``open(file, 'r').read(8192)`` takes 2 secs to complete) then you are
stuck.
Starting from version 1.0.0 pyftpdlib can change the concurrency model by using
multiple processes or threads instead.
In technical (internal) terms that means that every time a client connects a
separate thread/process is spawned and internally it will run its own IO loop.
In practical terms this means that you can block as long as you want.
Changing the concurrency module is easy: you just need to import a substitute
for `FTPServer <api.html#pyftpdlib.servers.FTPServer>`__. class:

Multiple threads
^^^^^^^^^^^^^^^^

.. code-block:: python

    from pyftpdlib.handlers import FTPHandler
    from pyftpdlib.servers import ThreadedFTPServer  # <-
    from pyftpdlib.authorizers import DummyAuthorizer

    def main():
        authorizer = DummyAuthorizer()
        authorizer.add_user('user', '12345', '.')
        handler = FTPHandler
        handler.authorizer = authorizer
        server = ThreadedFTPServer(('', 2121), handler)
        server.serve_forever()

    if __name__ == "__main__":
        main()


Multiple processes
^^^^^^^^^^^^^^^^^^

.. code-block:: python

    from pyftpdlib.handlers import FTPHandler
    from pyftpdlib.servers import MultiprocessFTPServer  # <-
    from pyftpdlib.authorizers import DummyAuthorizer

    def main():
        authorizer = DummyAuthorizer()
        authorizer.add_user('user', '12345', '.')
        handler = FTPHandler
        handler.authorizer = authorizer
        server = MultiprocessFTPServer(('', 2121), handler)
        server.serve_forever()

    if __name__ == "__main__":
        main()

.. _pre-fork:

Pre-fork
^^^^^^^^

There also exists a third option (UNIX only): the pre-fork model.
Pre-fork means that a certain number of worker processes are ``spawn()``ed
before starting the server.
Each worker process will keep using a 1-thread, async concurrency model,
handling multiple concurrent connections, but the workload is split.
This way the delay introduced by a blocking function call is amortized and
divided by the number of workers, and thus also the disk I/O latency is
minimized.
Every time a new connection comes in, the parent process will automatically
delegate the connection to one of the subprocesses, so from the app standpoint
this is completely transparent.
As a general rule, it is always a good idea to use this model in production.
The optimal value depends on many factors including (but not limited to) the
number of CPU cores, the number of hard disk drives that store data, and load
pattern. When one is in doubt, setting it to the number of available CPU cores
would be a good start.

.. code-block:: python

    from pyftpdlib.handlers import FTPHandler
    from pyftpdlib.servers import FTPServer
    from pyftpdlib.authorizers import DummyAuthorizer

    def main():
        authorizer = DummyAuthorizer()
        authorizer.add_user('user', '12345', '.')
        handler = FTPHandler
        handler.authorizer = authorizer
        server = FTPServer(('', 2121), handler)
        server.serve_forever(worker_processes=4)  # <-

    if __name__ == "__main__":
        main()

Throttle bandwidth
==================

An important feature for an ftpd is limiting the speed for downloads and
uploads affecting the data channel.
`ThrottledDTPHandler.banner <api.html#pyftpdlib.handlers.ThrottledDTPHandler>`__
can be used to set such limits.
The basic idea behind ``ThrottledDTPHandler`` is to wrap sending and receiving
in a data counter and temporary "sleep" the data channel so that you burst to
no more than x Kb/sec average. When it realizes that more than x Kb in a second
are being transmitted it temporary blocks the transfer for a certain number of
seconds.

.. code-block:: python

    import os

    from pyftpdlib.handlers import FTPHandler, ThrottledDTPHandler
    from pyftpdlib.servers import FTPServer
    from pyftpdlib.authorizers import DummyAuthorizer

    def main():
        authorizer = DummyAuthorizer()
        authorizer.add_user('user', '12345', os.getcwd(), perm='elradfmwMT')
        authorizer.add_anonymous(os.getcwd())

        dtp_handler = ThrottledDTPHandler
        dtp_handler.read_limit = 30720  # 30 Kb/sec (30 * 1024)
        dtp_handler.write_limit = 30720  # 30 Kb/sec (30 * 1024)

        ftp_handler = FTPHandler
        ftp_handler.authorizer = authorizer
        # have the ftp handler use the alternative dtp handler class
        ftp_handler.dtp_handler = dtp_handler

        server = FTPServer(('', 2121), ftp_handler)
        server.serve_forever()

    if __name__ == '__main__':
        main()


FTPS (FTP over TLS/SSL) server
==============================

Starting from version 0.6.0 pyftpdlib finally includes full FTPS support
implementing both TLS and SSL protocols and *AUTH*, *PBSZ* and *PROT* commands
as defined in `RFC-4217 <http://www.ietf.org/rfc/rfc4217.txt>`__. This has been
implemented by using `PyOpenSSL <http://pypi.python.org/pypi/pyOpenSSL>`__
module, which is required in order to run the code below.
`TLS_FTPHandler <api.html#pyftpdlib.handlers.TLS_FTPHandler>`__
class requires at least a ``certfile`` to be specified and optionally a
``keyfile``.
`Apache FAQs <https://httpd.apache.org/docs/2.4/ssl/ssl_faq.html#selfcert>`__ provide
instructions on how to generate them. If you don't care about having your
personal self-signed certificates you can use the one in the demo directory
which include both and is available
`here <https://github.com/giampaolo/pyftpdlib/blob/master/demo/keycert.pem>`__.

`source code <https://github.com/giampaolo/pyftpdlib/blob/master/demo/tls_ftpd.py>`__

.. code-block:: python

    """
    An RFC-4217 asynchronous FTPS server supporting both SSL and TLS.
    Requires PyOpenSSL module (http://pypi.python.org/pypi/pyOpenSSL).
    """

    from pyftpdlib.servers import FTPServer
    from pyftpdlib.authorizers import DummyAuthorizer
    from pyftpdlib.handlers import TLS_FTPHandler

    def main():
        authorizer = DummyAuthorizer()
        authorizer.add_user('user', '12345', '.', perm='elradfmwMT')
        authorizer.add_anonymous('.')
        handler = TLS_FTPHandler
        handler.certfile = 'keycert.pem'
        handler.authorizer = authorizer
        # requires SSL for both control and data channel
        #handler.tls_control_required = True
        #handler.tls_data_required = True
        server = FTPServer(('', 21), handler)
        server.serve_forever()

    if __name__ == '__main__':
        main()


Event callbacks
===============

A small example which shows how to use callback methods via
`FTPHandler <api.html#pyftpdlib.handlers.FTPHandler>`__ subclassing:

.. code-block:: python

    from pyftpdlib.handlers import FTPHandler
    from pyftpdlib.servers import FTPServer
    from pyftpdlib.authorizers import DummyAuthorizer


    class MyHandler(FTPHandler):

        def on_connect(self):
            print "%s:%s connected" % (self.remote_ip, self.remote_port)

        def on_disconnect(self):
            # do something when client disconnects
            pass

        def on_login(self, username):
            # do something when user login
            pass

        def on_logout(self, username):
            # do something when user logs out
            pass

        def on_file_sent(self, file):
            # do something when a file has been sent
            pass

        def on_file_received(self, file):
            # do something when a file has been received
            pass

        def on_incomplete_file_sent(self, file):
            # do something when a file is partially sent
            pass

        def on_incomplete_file_received(self, file):
            # remove partially uploaded files
            import os
            os.remove(file)


    def main():
        authorizer = DummyAuthorizer()
        authorizer.add_user('user', '12345', homedir='.', perm='elradfmwMT')
        authorizer.add_anonymous(homedir='.')

        handler = MyHandler
        handler.authorizer = authorizer
        server = FTPServer(('', 2121), handler)
        server.serve_forever()

    if __name__ == "__main__":
        main()


Command line usage
==================

Starting from version 0.6.0 pyftpdlib can be run as a simple stand-alone server
via Python's -m option, which is particularly useful when you want to quickly
share a directory. Some examples.
Anonymous FTPd sharing current directory:

.. code-block:: sh

    $ python -m pyftpdlib
    [I 13-04-09 17:55:18] >>> starting FTP server on 0.0.0.0:2121, pid=6412 <<<
    [I 13-04-09 17:55:18] poller: <class 'pyftpdlib.ioloop.Epoll'>
    [I 13-04-09 17:55:18] masquerade (NAT) address: None
    [I 13-04-09 17:55:18] passive ports: None
    [I 13-04-09 17:55:18] use sendfile(2): True

Anonymous FTPd with write permission:

.. code-block:: sh

    $ python -m pyftpdlib -w

Set a different address/port and home directory:

.. code-block:: sh

    $ python -m pyftpdlib -i localhost -p 8021 -d /home/someone

See ``python -m pyftpdlib -h`` for a complete list of options.
