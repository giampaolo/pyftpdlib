====
FAQs
====

.. contents:: Table of Contents

Introduction
============

What is pyftpdlib?
------------------

pyftpdlib is a high-level library to easily write asynchronous portable FTP
servers with `Python <https://www.python.org/>`__.

I'm not a python programmer. Can I use it anyway?
-------------------------------------------------

Yes. Pyftpdlib is a fully working FTP server implementation that can be run
"as is". For example, you could run an anonymous FTP server with write access
from command line by running:

.. code-block:: sh

    $ python3 -m pyftpdlib -w
    RuntimeWarning: write permissions assigned to anonymous user.
    [I 13-02-20 14:16:36] >>> starting FTP server on 0.0.0.0:2121 <<<
    [I 13-02-20 14:16:36] poller: <class 'pyftpdlib.ioloop.Epoll'>
    [I 13-02-20 14:16:36] masquerade (NAT) address: None
    [I 13-02-20 14:16:36] passive ports: None
    [I 13-02-20 14:16:36] use sendfile(2): True

This is useful in case you want a quick and dirty way to share a directory
without, say, installing and configuring Samba.

Installing and compatibility
============================

How do I install pyftpdlib?
---------------------------

.. code-block:: sh

    $ python3 -m pip install pyftpdlib

Also see  `install instructions <install.html>`__.

Which Python versions are compatible?
-------------------------------------

Python *3.X*. Anything above 3.8 should be good to go. Pypy should also work.

What about Python 2.7?
----------------------

Latest pyftpdlib version supporting Python 2.7 is 1.5.10. You can install it
with:

.. code-block:: sh

    python2 -m pip install pyftpdlib==1.5.10

On which platforms can pyftpdlib be used?
-----------------------------------------

pyftpdlib should work on any platform where **select()**, **poll()**,
**epoll()** or **kqueue()** system calls are available, namely UNIX and
Windows.

Usage
=====

How can I run long-running tasks without blocking the server?
-------------------------------------------------------------

pyftpdlib is an *asynchronous* FTP server. That means that if you need to run a
time consuming task you have to use a separate Python process or thread,
otherwise the entire asynchronous loop will be blocked.

Let's suppose you want to implement a long-running task every time the server
receives a file. The code snippet below shows how.
With ``self.del_channel()`` we temporarily "sleep" the connection handler which
will be removed from the async IO poller loop and won't be able to send or
receive any more data. It won't be closed (disconnected) as long as we don't
invoke ``self.add_channel()``. This is fundamental when working with threads to
avoid race conditions, dead locks etc.

.. code-block:: python

    class MyHandler(FTPHandler):

        def on_file_received(self, file):
            def blocking_task():
                time.sleep(5)
                self.add_channel()

            self.del_channel()
            threading.Thread(target=blocking_task).start()

Another possibility is to
`change the default concurrency model <tutorial.html#changing-the-concurrency-model>`__.

Why do I get "Permission denied" error on startup?
--------------------------------------------------

Probably because you're on a UNIX system and you're trying to start the FTP
server as an unprivileged user. FTP servers bind on port 21 by default, and
only the root user can bind sockets on such ports. If you want to bind the
socket as non-privileged user you should set a port higher than 1024.

Can I control upload/download ratios?
-------------------------------------

Yes. Pyftpdlib provides a new class called
`ThrottledDTPHandler <api.html#pyftpdlib.handlers.ThrottledDTPHandler>`__.
You can set speed limits by modifying
`read_limit <api.html#pyftpdlib.handlers.ThrottledDTPHandler.read_limit>`__
and
`write_limit <api.html#pyftpdlib.handlers.ThrottledDTPHandler.write_limit>`__
class attributes as it is shown in
`throttled_ftpd.py <https://github.com/giampaolo/pyftpdlib/blob/master/demo/throttled_ftpd.py>`__
demo script.

Are there ways to limit connections?
------------------------------------

The `FTPServer <api.html#pyftpdlib.servers.FTPServer>`__. class comes with two
overridable attributes defaulting to zero (no limit):
`max_cons <api.html#pyftpdlib.servers.FTPServer.max_cons>`__,
which sets a limit for maximum simultaneous connection to handle, and
`max_cons_per_ip <api.html#pyftpdlib.servers.FTPServer.max_cons_per_ip>`__
which sets a limit for the connections from the same IP address.

I'm behind a NAT / gateway
--------------------------

The FTP protocol uses 2 TCP connections: a "control" connection to exchange
protocol messages (LIST, RETR, etc.), and a "data" connection for transfering
data (files).
In order to open the data connection the FTP server must communicate its
**public** IP address in the PASV response. If you're behind a NAT, this
address must be explicitly configured by setting the
`masquerade_address <api.html#pyftpdlib.handlers.FTPHandler.masquerade_address>`__
attribute.

You can get your public IP address by using services like
https://www.whatismyip.com/.

In addition, you also probably want to configure a given range of TCP ports
for such incoming "data" connections, otherwise a random TCP port will be
picked up every time.
You can do so by using the `passive_ports <api.html#pyftpdlib.handlers.FTPHandler.passive_ports>`__
attribute.
The value expected by `passive_ports <api.html#pyftpdlib.handlers.FTPHandler.passive_ports>`__
attribute is a list of integers (e.g. ``range(60000, 65535)``).

This also means that you must configure your router so the it will forward
the incoming connections to such TCP ports from the router to your FTP server
behind the NAT.

Why timestamps shown by MDTM and ls commands (LIST, MLSD, MLST) are wrong?
--------------------------------------------------------------------------

If by "wrong" you mean "different from the timestamp of that file on my client
machine", then that is the expected behavior.
pyftpdlib uses `GMT times <https://en.wikipedia.org/wiki/Greenwich_Mean_Time>`__
as recommended in `RFC-3659 <https://datatracker.ietf.org/doc/html/rfc3659>`__.
Any client complying with RFC-3659 should be able to convert the GMT time to
your local time and show the correct timestamp.
In case you want LIST, MLSD, MLST commands to report local times instead, just set the
`use_gmt_times <api.html#pyftpdlib.handlers.FTPHandler.use_gmt_times>`__ attribute to ``False``.
For further information you might want to take a look at
`this <http://www.proftpd.org/docs/howto/Timestamps.html>`__

Implementation
==============

sendfile()
----------

On Linux, and only when doing transfer in clear text (aka no FTPS), the
``sendfile(2)`` system call be used when uploading files (from server to
client) via RETR command. Using ``sendfile(2)`` is more efficient, and usually
results in transfer rates that are from 2x to 3x faster.

In the past some cases were reported that using ``sendfile(2)`` with "non
regular" filesystems such as NFS, SMBFS/Samba, CIFS or network mounts in
general may cause some issues, see http://www.proftpd.org/docs/howto/Sendfile.html.
If you bump into one these issues you can set
`FTPHandler.use_sendfile <api.html#pyftpdlib.handlers.FTPHandler.use_sendfile>`__ to ``False``:

.. code-block:: python

    from pyftpdlib.handlers import FTPHandler
    handler = FTPHandler
    handler.use_senfile = False
    ...

Globbing / STAT command implementation
--------------------------------------

Globbing is a common UNIX shell mechanism for expanding wildcard patterns to
match multiple filenames. When an argument is provided to the *STAT* command,
the FTP server should return a directory listing over the command channel.
`RFC-959 <https://datatracker.ietf.org/doc/html/rfc959>`__ does not explicitly mention
globbing; this means that FTP servers are not required to support globbing in
order to be compliant.  However, many FTP servers do support globbing as a
measure of convenience for FTP clients and users. In order to search for and
match the given globbing expression, the code has to search (possibly) many
directories, examine each contained filename, and build a list of matching
files in memory. Since this operation can be quite intensive (and slow)
pyftpdlib *does not* support globbing.

ASCII transfers / SIZE command implementation
---------------------------------------------

Properly handling the SIZE command when TYPE ASCII is used would require to
scan the entire file to perform the ASCII translation logic
(file.read().replace(os.linesep, '\r\n')), and then calculating the length of such
data which may be different than the actual size of the file on the server.
Considering that calculating such a result could be resource-intensive, it
could be easy for a malicious client to use this as a DoS attack. As such thus
pyftpdlib rejects SIZE when the current TYPE is ASCII. However, clients in
general should not be resuming downloads in ASCII mode.  Resuming downloads in
binary mode is the recommended way as specified in
`RFC-3659 <https://datatracker.ietf.org/doc/html/rfc3659>`__.

IPv6 support
------------

Pyftpdlib does support IPv6
(`RFC-2428 <https://datatracker.ietf.org/doc/html/rfc2428>`__). If you want your FTP server
to explicitly use IPv6 you can do so by passing a valid IPv6 address to the
`FTPServer <api.html#pyftpdlib.servers.FTPServer>`__ class constructor.
Example:

.. code-block:: python

    >>> from pyftpdlib.servers import FTPServer
    >>> address = ("::1", 21)  # listen on localhost, port 21
    >>> ftpd = FTPServer(address, FTPHandler)
    >>> ftpd.serve_forever()
    Serving FTP on ::1:21

If the OS supports an hybrid dual-stack IPv6/IPv4 implementation (e.g. Linux),
the code above will automatically listen on both IPv4 and IPv6 by using the
same TCP socket.

Can pyftpdlib be integrated with "real" users existing on the system?
---------------------------------------------------------------------

Yes. See `UnixAuthorizer <api.html#pyftpdlib.authorizers.UnixAuthorizer>`__
and `WindowsAuthorizer <api.html#pyftpdlib.authorizers.WindowsAuthorizer>`__ classes.
By using them you can authenticate to the FTP server by using the credentials
of the users defined on the operating system

Furthermore: every time the FTP server accesses the filesystem (e.g. for
creating or renaming a file) the authorizer will temporarily impersonate the
currently logged on user, execute the filesystem call and then switch back to
the user who originally started the server. It will do so by setting the
effective user or group ID of the current process. That means that you
probably want to run the FTP as root. See:

* https://github.com/giampaolo/pyftpdlib/blob/master/demo/unix_ftpd.py
* https://github.com/giampaolo/pyftpdlib/blob/master/demo/winnt_ftpd.py

Does pyftpdlib support FTP over TLS/SSL (FTPS)?
-----------------------------------------------

Yes. Checkout `TLS_FTPHandler <api.html#pyftpdlib.handlers.TLS_FTPHandler>`__.

What about SITE commands?
-------------------------

The only supported SITE command is *SITE CHMOD* (change file mode). The user
willing to add support for other specific SITE commands has to define a new
``ftp_SITE_CMD`` method in the
`FTPHandler <api.html#pyftpdlib.handlers.FTPHandler>`__ subclass and add a new
entry in ``proto_cmds`` dictionary. Example:

.. code-block:: python

    from pyftpdlib.handlers import FTPHandler

    proto_cmds = FTPHandler.proto_cmds.copy()
    proto_cmds.update(
        {'SITE RMTREE': dict(perm='R', auth=True, arg=True,
          help='Syntax: SITE <SP> RMTREE <SP> path (remove directory tree).')}
    )

    class CustomizedFTPHandler(FTPHandler):
        proto_cmds = proto_cmds

    def ftp_SITE_RMTREE(self, line):
        """Recursively remove a directory tree."""
        # implementation here
        # ...
