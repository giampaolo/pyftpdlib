====
FAQs
====

.. contents:: Table of Contents

Introduction
============

What is pyftpdlib?
------------------

pyftpdlib is a high-level library to easily write asynchronous portable FTP
servers with `Python <http://www.python.org/>`__.

What is Python?
---------------

Python is an interpreted, interactive, object-oriented, easy-to-learn
programming language. It is often compared to *Tcl, Perl, Scheme* or *Java*.

I'm not a python programmer. Can I use it anyway?
-------------------------------------------------

Yes. pyftpdlib is a fully working FTP server implementation that can be run
"as is". For example you could run an anonymous ftp server from cmd-line by
running:

.. code-block:: sh

    $ sudo python -m pyftpdlib
    [I 13-02-20 14:16:36] >>> starting FTP server on 0.0.0.0:8021 <<<
    [I 13-02-20 14:16:36] poller: <class 'pyftpdlib.ioloop.Epoll'>
    [I 13-02-20 14:16:36] masquerade (NAT) address: None
    [I 13-02-20 14:16:36] passive ports: None
    [I 13-02-20 14:16:36] use sendfile(2): True

This is useful in case you want a quick and dirty way to share a directory
without, say, installing and configuring samba. Starting from version 0.6.0
options can be passed to the command line (see ``python -m pyftpdlib --help``
to see all available options). Examples:

Anonymous FTP server with write access:

.. code-block:: sh

    $ sudo python -m pyftpdlib -w
    ~pyftpdlib-1.3.1-py2.7.egg/pyftpdlib/authorizers.py:265: RuntimeWarning: write permissions assigned to anonymous user.
    [I 13-02-20 14:16:36] >>> starting FTP server on 0.0.0.0:8021 <<<
    [I 13-02-20 14:16:36] poller: <class 'pyftpdlib.ioloop.Epoll'>
    [I 13-02-20 14:16:36] masquerade (NAT) address: None
    [I 13-02-20 14:16:36] passive ports: None
    [I 13-02-20 14:16:36] use sendfile(2): True

Listen on a different ip/port:

.. code-block:: sh

    $ python -m pyftpdlib -i 127.0.0.1 -p 8021
    [I 13-02-20 14:16:36] >>> starting FTP server on 0.0.0.0:8021 <<<
    [I 13-02-20 14:16:36] poller: <class 'pyftpdlib.ioloop.Epoll'>
    [I 13-02-20 14:16:36] masquerade (NAT) address: None
    [I 13-02-20 14:16:36] passive ports: None
    [I 13-02-20 14:16:36] use sendfile(2): True


Customizing ftpd for basic tasks like adding users or deciding where log file
should be placed is mostly simply editing variables. This is basically like
learning how to edit a common unix ftpd.conf file and doesn't really require
Python knowledge. Customizing ftpd more deeply requires a python script which
imports pyftpdlib to be written separately. An example about how this could be
done are the scripts contained in the
`demo directory <https://github.com/giampaolo/pyftpdlib/tree/master/demo>`__.

Getting help
------------

There's a mailing list available at:
http://groups.google.com/group/pyftpdlib/topics

Installing and compatibility
============================

How do I install pyftpdlib?
---------------------------

If you are not new to Python you probably don't need that, otherwise follow the
`install instructions <install.html>`__.

Which Python versions are compatible?
-------------------------------------

From *2.6* to *3.X*.

On which platforms can pyftpdlib be used?
-----------------------------------------

pyftpdlib should work on any platform where **select()**, **poll()**,
**epoll()** or **kqueue()** system calls are available and on any Python
implementation which refers to *cPython 2.6* or superior.
The development team has mainly tested it under various *Linux*, *Windows*,
*OSX* and *FreeBSD* systems.
For FreeBSD is also available a
`pre-compiled package <http://www.freshports.org/ftp/py-pyftpdlib/>`__
maintained by Li-Wen Hsu (lwhsu@freebsd.org).
Other Python implementation like
`PythonCE <http://pythonce.sourceforge.net/>`__ are known to work with
pyftpdlib and every new version is usually tested against it.
pyftpdlib currently does not work on `Jython <http://www.jython.org/>`__
since the latest Jython release refers to CPython 2.2.x serie. The best way
to know whether pyftpdlib works on your platform is installing it and running
its test suite.

Usage
=====

How can I run long-running tasks without blocking the server?
-------------------------------------------------------------

pyftpdlib is an *asynchronous* FTP server. That means that if you need to run a
time consuming task you have to use a separate Python process or thread for the
actual processing work otherwise the entire asynchronous loop will be blocked.

Let's suppose you want to implement a long-running task every time the server
receives a file. The code snippet below shows the correct way to do it by using
a thread.

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

Why do I get socket.error "Permission denied" error on ftpd starting?
---------------------------------------------------------------------

Probably because you're on a Unix system and you're trying to start ftpd as an
unprivileged user. FTP servers bind on port 21 by default and only super-user
account  (e.g. root) can bind sockets on such ports. If you want to bind
ftpd as non-privileged user you should set a port higher than 1024.

How can I prevent the server version from being displayed?
----------------------------------------------------------

Just modify `FTPHandler.banner <api.html#pyftpdlib.handlers.FTPHandler.banner>`__.

Can control upload/download ratios?
-----------------------------------

Yes. Starting from version 0.5.2 pyftpdlib provides a new class called
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

`FTPServer <api.html#pyftpdlib.servers.FTPServer>`__. class comes with two
overridable attributes defaulting to zero
(no limit): `max_cons <api.html#pyftpdlib.servers.FTPServer.max_cons>`__,
which sets a limit for maximum simultaneous
connection to handle by ftpd and
`max_cons_per_ip <api.html#pyftpdlib.servers.FTPServer.max_cons_per_ip>`__
which set a limit for connections from the same IP address. Overriding these
variables is always recommended to avoid DoS attacks.

I'm behind a NAT / gateway
--------------------------

When behind a NAT a ftp server needs to replace the IP local address displayed
in PASV replies and instead use the public address of the NAT to allow client
to connect.  By overriding
`masquerade_address <api.html#pyftpdlib.handlers.FTPHandler.masquerade_address>`__
attribute of `FTPHandler <api.html#pyftpdlib.handlers.FTPHandler.masquerade_address>`__
class you will force pyftpdlib to do such replacement. However, one problem
still exists.  The passive FTP connections will use ports from 1024 and up,
which means that you must forward all ports 1024-65535 from the NAT to the FTP
server!  And you have to allow many (possibly) dangerous ports in your
firewalling rules!  To resolve this, simply override
`passive_ports <api.html#pyftpdlib.handlers.FTPHandler.passive_ports>`__
attribute of `FTPHandler <api.html#pyftpdlib.handlers.FTPHandler.masquerade_address>`__
class to control what ports pyftpdlib will use for its passive data transfers.
Value expected by `passive_ports <api.html#pyftpdlib.handlers.FTPHandler.passive_ports>`__
attribute is a list of integers (e.g. range(60000, 65535)) indicating which
ports will be used for initializing the passive data channel. In case you run a
FTP server with multiple private IP addresses behind a NAT firewall with
multiple public IP addresses you can use
`passive_ports <api.html#pyftpdlib.handlers.FTPHandler.passive_ports>`__ option
which allows you to define multiple 1 to 1 mappings (**New in 0.6.0**).

What is FXP?
------------

FXP is part of the name of a popular Windows FTP client:
`http://www.flashfxp.com <http://www.flashfxp.com>`__. This client has made the
name "FXP" commonly used as a synonym for site-to-site FTP transfers, for
transferring a file between two remote FTP servers without the transfer going
through the client's host.  Sometimes "FXP" is referred to as a protocol; in
fact, it is not. The site-to-site transfer capability was deliberately designed
into `RFC-959 <http://www.faqs.org/rfcs/rfc959.html>`__. More info can be found
here: `http://www.proftpd.org/docs/howto/FXP.html
<http://www.proftpd.org/docs/howto/FXP.html>`__.

Does pyftpdlib support FXP?
---------------------------

Yes. It is disabled by default for security reasons (see
`RFC-2257 <http://tools.ietf.org/html/rfc2577>`__ and
`FTP bounce attack description <http://www.cert.org/advisories/CA-1997-27.html>`__)
but in case you want to enable it just set to True the
`permit_foreign_addresses <api.html#pyftpdlib.handlers.FTPHandler.permit_foreign_addresses>`__
attribute of `FTPHandler <api.html#pyftpdlib.handlers.FTPHandler.masquerade_address>`__ class.

Why timestamps shown by MDTM and ls commands (LIST, MLSD, MLST) are wrong?
--------------------------------------------------------------------------

If by "wrong" you mean "different from the timestamp of that file on my client
machine", then that is the expected behavior.
Starting from version 0.6.0 pyftpdlib uses
`GMT times <http://en.wikipedia.org/wiki/Greenwich*Mean*Time>`__ as recommended
in `RFC-3659 <http://tools.ietf.org/html/rfc3659>`__.
In case you want such commands to report local times instead just set the
`use_gmt_times <api.html#pyftpdlib.handlers.FTPHandler.use_gmt_times>`__ attribute to ``False``.
For further information you might want to take a look at
`this <http://www.proftpd.org/docs/howto/Timestamps.html>`__

Implementation
==============

sendfile()
----------

Starting from version 0.7.0 if
`pysendfile <https://github.com/giampaolo/pysendfile/>`__ module is installed
sendfile(2) system call be used when uploading files (from server to client)
via RETR command.
Using sendfile(2) usually results in transfer rates from 2x to 3x faster
and less CPU usage.
Note: use of sendfile() might introduce some unexpected issues with "non
regular filesystems" such as NFS, SMBFS/Samba, CIFS and network mounts in
general, see: http://www.proftpd.org/docs/howto/Sendfile.html. If you bump into
one this problems the fix consists in disabling sendfile() usage via
`FTPHandler.use_sendfile <api.html#pyftpdlib.handlers.FTPHandler.use_sendfile>`__
option:

.. code-block:: python

    from pyftpdlib.handlers import FTPHandler
    handler = FTPHandler
    handler.use_senfile = False
    ...

Globbing / STAT command implementation
--------------------------------------

Globbing is a common Unix shell mechanism for expanding wildcard patterns to
match multiple filenames. When an argument is provided to the *STAT* command,
ftpd should return directory listing over the command channel.
`RFC-959 <http://tools.ietf.org/html/rfc959>`__ does not explicitly mention
globbing; this means that FTP servers are not required to support globbing in
order to be compliant.  However, many FTP servers do support globbing as a
measure of convenience for FTP clients and users. In order to search for and
match the given globbing expression, the code has to search (possibly) many
directories, examine each contained filename, and build a list of matching
files in memory. Since this operation can be quite intensive, both CPU- and
memory-wise, pyftpdlib *does not* support globbing.

ASCII transfers / SIZE command implementation
---------------------------------------------

Properly handling the SIZE command when TYPE ASCII is used would require to
scan the entire file to perform the ASCII translation logic
(file.read().replace(os.linesep, '\r\n')) and then calculating the len of such
data which may be different than the actual size of the file on the server.
Considering that calculating such result could be very resource-intensive it
could be easy for a malicious client to try a DoS attack, thus pyftpdlib
rejects SIZE when the current TYPE is ASCII. However, clients in general should
not be resuming downloads in ASCII mode.  Resuming downloads in binary mode is
the recommended way as specified in
`RFC-3659 <http://tools.ietf.org/html/rfc3659>`__.

IPv6 support
------------

Starting from version 0.4.0 pyftpdlib *supports* IPv6
(`RFC-2428 <http://tools.ietf.org/html/rfc2428>`__). If you use IPv6 and want
your FTP daemon to do so just pass a valid IPv6 address to the
`FTPServer <api.html#pyftpdlib.servers.FTPServer>`__ class constructor.
Example:

.. code-block:: python

    >>> from pyftpdlib.servers import FTPServer
    >>> address = ("::1", 21)  # listen on localhost, port 21
    >>> ftpd = FTPServer(address, FTPHandler)
    >>> ftpd.serve_forever()
    Serving FTP on ::1:21

If your OS (for example: all recent UNIX systems) have an hybrid dual-stack
IPv6/IPv4 implementation the code above will listen on both IPv4 and IPv6 by
using a single IPv6 socket (**New in 0.6.0**).

How do I install IPv6 support on my system?
-------------------------------------------

If you want to install IPv6 support on Linux run "modprobe ipv6", then
"ifconfig". This should display the loopback adapter, with the address "::1".
You should then be able to listen the server on that address, and connect to
it.
On Windows (XP SP2 and higher) run "netsh int ipv6 install". Again, you should
be able to use IPv6 loopback afterwards.

Can pyftpdlib be integrated with "real" users existing on the system?
---------------------------------------------------------------------

Yes. Starting from version 0.6.0 pyftpdlib provides the new `UnixAuthorizer <api.html#pyftpdlib.authorizers.UnixAuthorizer>`__
and `WindowsAuthorizer <api.html#pyftpdlib.authorizers.WindowsAuthorizer>`__ classes. By using them pyftpdlib can look into the
system account database to authenticate users. They also assume the id of real
users every time the FTP server is going to access the filesystem (e.g. for
creating or renaming a file) the authorizer will temporarily impersonate the
currently logged on user, execute the filesystem call and then switch back to
the user who originally started the server. Example UNIX and Windows FTP
servers contained in the
`demo directory <https://github.com/giampaolo/pyftpdlib/tree/master/demo>`__
shows how to use `UnixAuthorizer <api.html#pyftpdlib.authorizers.UnixAuthorizer>`__ and `WindowsAuthorizer <api.html#pyftpdlib.authorizers.WindowsAuthorizer>`__ classes.

Does pyftpdlib support FTP over TLS/SSL (FTPS)?
-----------------------------------------------

Yes, starting from version 0.6.0, see:
`Does pyftpdlib support FTP over TLS/SSL (FTPS)?`_

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
