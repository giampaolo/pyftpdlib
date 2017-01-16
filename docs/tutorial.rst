========
Tutorial
========

.. contents:: Table of Contents

Below is a set of example scripts showing some of the possible customizations
that can be done with pyftpdlib.  Some of them are included in
`demo <https://github.com/giampaolo/pyftpdlib/blob/master/demo/>`__
directory of pyftpdlib source distribution.

Building a Base FTP server
==========================

The script below is a basic configuration, and it's probably the best starting
point for understanding how things work. It uses the base
`DummyAuthorizer <api.html#pyftpdlib.authorizers.DummyAuthorizer>`__
for adding a bunch of "virtual" users. It also sets a limit for connections by
overriding
`FTPServer.max_cons <api.html#pyftpdlib.servers.FTPServer.max_cons>`__
and
`FTPServer.max_cons_per_ip <api.html#pyftpdlib.servers.FTPServer.max_cons_per_ip>`__,
attributes which are intended to set limits for maximum connections to handle
simultaneously and maximum connections from the same IP address. Overriding
these variables is always a good idea (they default to ``0``, or "no limit")
since they are a good workaround for avoiding DoS attacks.

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
        authorizer.add_user('user', '12345', '.', perm='elradfmwM')
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

Starting from version 1.0.0 pyftpdlib uses
`logging <http://docs.python.org/library/logging.html logging>`__
module to handle logging. If you don't configure logging pyftpdlib will write
it to stderr by default (coloured if you're on POSIX). You can override the
default behavior and, say, log to a file. What you have to bear in mind is that
you should do that *before* calling serve_forever(). Examples.

Logging to a file
^^^^^^^^^^^^^^^^^

.. code-block:: python

    import logging

    from pyftpdlib.handlers import FTPHandler
    from pyftpdlib.servers import FTPServer
    from pyftpdlib.authorizers import DummyAuthorizer

    authorizer = DummyAuthorizer()
    authorizer.add_user('user', '12345', '.', perm='elradfmwM')
    handler = FTPHandler
    handler.authorizer = authorizer

    logging.basicConfig(filename='/var/log/pyftpd.log', level=logging.INFO)

    server = FTPServer(('', 2121), handler)
    server.serve_forever()


Differences between logging.INFO and logging.DEBUG
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

Starting from  1.0.0 logs are a lot less verbose than before. By default they
look like this:

::

    [I 13-02-01 19:04:56] 127.0.0.1:49243-[] FTP session opened (connect)
    [I 13-02-01 19:04:56] 127.0.0.1:49243-[user] USER 'user' logged in.
    [I 13-02-01 19:04:56] 127.0.0.1:49243-[user] RETR /home/giampaolo/svn/pyftpdlib/tmp-pyftpdlib completed=1 bytes=9803392 seconds=0.025
    [I 13-02-01 19:04:56] 127.0.0.1:49243-[user] FTP session closed (disconnect).


To get the old behavior and log all commands and responses exchanged by client
and server use:

.. code-block:: python

    logging.basicConfig(level=logging.DEBUG)


Now they will look like this:

::

    [I 13-02-01 19:05:42] 127.0.0.1:37303-[] FTP session opened (connect)
    [D 13-02-01 19:05:42] 127.0.0.1:37303-[] -> 220 pyftpdlib 1.0.0 ready.
    [D 13-02-01 19:05:42] 127.0.0.1:37303-[] <- USER user
    [D 13-02-01 19:05:42] 127.0.0.1:37303-[] -> 331 Username ok, send password.
    [D 13-02-01 19:05:42] 127.0.0.1:37303-[user] <- PASS ******
    [D 13-02-01 19:05:42] 127.0.0.1:37303-[user] -> 230 Login successful.
    [I 13-02-01 19:05:42] 127.0.0.1:37303-[user] USER 'user' logged in.
    [D 13-02-01 19:05:42] 127.0.0.1:37303-[user] <- TYPE I
    [D 13-02-01 19:05:42] 127.0.0.1:37303-[user] -> 200 Type set to: Binary.
    [D 13-02-01 19:05:42] 127.0.0.1:37303-[user] <- PASV
    [D 13-02-01 19:05:42] 127.0.0.1:37303-[user] -> 227 Entering passive mode (127,0,0,1,233,208).
    [D 13-02-01 19:05:42] 127.0.0.1:37303-[user] <- retr tmp-pyftpdlib
    [D 13-02-01 19:05:42] 127.0.0.1:37303-[user] -> 125 Data connection already open. Transfer starting.
    [D 13-02-01 19:05:42] 127.0.0.1:37303-[user] -> 226 Transfer complete.
    [I 13-02-01 19:05:42] 127.0.0.1:37303-[user] RETR /home/giampaolo/svn/pyftpdlib/tmp-pyftpdlib completed=1 bytes=1000000 seconds=0.003
    [D 13-02-01 19:05:42] 127.0.0.1:54516-[user] <- QUIT
    [D 13-02-01 19:05:42] 127.0.0.1:54516-[user] -> 221 Goodbye.
    [I 13-02-01 19:05:42] 127.0.0.1:54516-[user] FTP session closed (disconnect).


Changing log line prefix
^^^^^^^^^^^^^^^^^^^^^^^^

.. code-block:: python

    ...
    handler = FTPHandler
    handler.log_prefix = 'XXX [%(username)s]@%(remote_ip)s'
    ...


...log will now look like this:

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
how to easily create an encrypted account storage system by storing passwords
as one-way hashes by using md5 algorithm. This could be easily done by using
the *hashlib* module included with Python stdlib and by sub-classing the
original `DummyAuthorizer <api.html#pyftpdlib.authorizers.DummyAuthorizer>`__
class overriding its
`validate_authentication() <api.html#pyftpdlib.authorizers.DummyAuthorizer.validate_authentication>`__
method.

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
                password = md5(password.encode('latin1'))
            hash = md5(password).hexdigest()
            try:
                if self.user_table[username]['pwd'] != hash:
                    raise KeyError
            except KeyError:
                raise AuthenticationFailed


    def main():
        # get a hash digest from a clear-text password
        hash = md5('12345').hexdigest()
        authorizer = DummyMD5Authorizer()
        authorizer.add_user('user', hash, os.getcwd(), perm='elradfmw')
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


Changing the concurrency model
==============================

By nature pyftpdlib is asynchronous. This means it uses a single process/thread
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
Starting from version 1.0.0 pyftpdlib supports 2 new classes which changes the
default concurrency model by introducing multiple threads or processes. In
technical terms this means that every time a client connects a separate
thread/process is spawned and internally it will run its own IO loop. In
practical terms this means that you can block as long as you want.
Changing the concurrency module is easy: you just need to import a substitute
for `FTPServer <api.html#pyftpdlib.servers.FTPServer>`__. class:

Thread-based example:

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


Multiple process example:

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
        authorizer.add_user('user', '12345', os.getcwd(), perm='elradfmw')
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
`Apache FAQs <http://www.modssl.org/docs/2.7/ssl*faq.html#ToC24>`__ provide
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
        authorizer.add_user('user', '12345', '.', perm='elradfmw')
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
        authorizer.add_user('user', '12345', homedir='.', perm='elradfmw')
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
