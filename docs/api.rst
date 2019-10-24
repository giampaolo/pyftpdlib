=============
API reference
=============

.. contents:: Table of Contents

pyftpdlib implements the server side of the FTP protocol as defined in
`RFC-959 <http://www.faqs.org/rfcs/rfc959.html>`_. This document is intended to
serve as a simple API reference of most important classes and functions.
After reading this you will probably want to read the
`tutorial <tutorial.html>`_ including customization through the use of some
example scripts.

Modules and classes hierarchy
=============================

::

  pyftpdlib.authorizers
  pyftpdlib.authorizers.AuthenticationFailed
  pyftpdlib.authorizers.DummyAuthorizer
  pyftpdlib.authorizers.UnixAuthorizer
  pyftpdlib.authorizers.WindowsAuthorizer
  pyftpdlib.handlers
  pyftpdlib.handlers.FTPHandler
  pyftpdlib.handlers.TLS_FTPHandler
  pyftpdlib.handlers.DTPHandler
  pyftpdlib.handlers.TLS_DTPHandler
  pyftpdlib.handlers.ThrottledDTPHandler
  pyftpdlib.filesystems
  pyftpdlib.filesystems.FilesystemError
  pyftpdlib.filesystems.AbstractedFS
  pyftpdlib.filesystems.UnixFilesystem
  pyftpdlib.servers
  pyftpdlib.servers.FTPServer
  pyftpdlib.servers.ThreadedFTPServer
  pyftpdlib.servers.MultiprocessFTPServer
  pyftpdlib.ioloop
  pyftpdlib.ioloop.IOLoop
  pyftpdlib.ioloop.Connector
  pyftpdlib.ioloop.Acceptor
  pyftpdlib.ioloop.AsyncChat

Users
=====

.. class:: pyftpdlib.authorizers.DummyAuthorizer()

  Basic "dummy" authorizer class, suitable for subclassing to create your own
  custom authorizers. An "authorizer" is a class handling authentications and
  permissions of the FTP server. It is used inside
  :class:`pyftpdlib.handlers.FTPHandler` class for verifying user's password,
  getting users home directory, checking user permissions when a filesystem
  read/write event occurs and changing user before accessing the filesystem.
  DummyAuthorizer is the base authorizer, providing a platform independent
  interface for managing "virtual" FTP users. Typically the first thing you
  have to do is create an instance of this class and start adding ftp users:

  >>> from pyftpdlib.authorizers import DummyAuthorizer
  >>> authorizer = DummyAuthorizer()
  >>> authorizer.add_user('user', 'password', '/home/user', perm='elradfmwMT')
  >>> authorizer.add_anonymous('/home/nobody')

  .. method:: add_user(username, password, homedir, perm="elr", msg_login="Login successful.", msg_quit="Goodbye.")

    Add a user to the virtual users table. AuthorizerError exception is raised
    on error conditions such as insufficient permissions or duplicate usernames.
    Optional *perm* argument is a set of letters referencing the user's
    permissions. Every letter is used to indicate that the access rights the
    current FTP user has over the following specific actions are granted. The
    available permissions are the following listed below:

    Read permissions:

    - ``"e"`` = change directory (CWD, CDUP commands)
    - ``"l"`` = list files (LIST, NLST, STAT, MLSD, MLST, SIZE commands)
    - ``"r"`` = retrieve file from the server (RETR command)

    Write permissions:

    - ``"a"`` = append data to an existing file (APPE command)
    - ``"d"`` = delete file or directory (DELE, RMD commands)
    - ``"f"`` = rename file or directory (RNFR, RNTO commands)
    - ``"m"`` = create directory (MKD command)
    - ``"w"`` = store a file to the server (STOR, STOU commands)
    - ``"M"`` = change file mode / permission (SITE CHMOD command) *New in 0.7.0*
    - ``"T"`` = change file modification time (SITE MFMT command) *New in 1.5.3*

    Optional *msg_login* and *msg_quit* arguments can be specified to provide
    customized response strings when user log-in and quit. The *perm* argument
    of the :meth:`add_user()` method refers to user's permissions. Every letter
    is used to indicate that the access rights the current FTP user has over
    the following specific actions are granted.

  .. method:: add_anonymous(homedir, **kwargs)

    Add an anonymous user to the virtual users table. AuthorizerError exception
    is raised on error conditions such as insufficient permissions, missing
    home directory, or duplicate anonymous users. The keyword arguments in
    kwargs are the same expected by :meth:`add_user()` method: *perm*,
    *msg_login* and *msg_quit*. The optional perm keyword argument is a string
    defaulting to "elr" referencing "read-only" anonymous user's permission.
    Using a "write" value results in a RuntimeWarning.

  .. method:: override_perm(username, directory, perm, recursive=False)

    Override user permissions for a given directory.

  .. method:: validate_authentication(username, password, handler)

    Raises :class:`pyftpdlib.authorizers.AuthenticationFailed` if the supplied
    username and password doesn't match the stored credentials.

    *Changed in 1.0.0: new handler parameter.*

    *Changed in 1.0.0: an exception is now raised for signaling a failed authenticaiton as opposed to returning a bool.*

  .. method:: impersonate_user(username, password)

    Impersonate another user (noop). It is always called before accessing the
    filesystem. By default it does nothing. The subclass overriding this method
    is expected to provide a mechanism to change the current user.

  .. method:: terminate_impersonation(username)

    Terminate impersonation (noop). It is always called after having accessed
    the filesystem. By default it does nothing. The subclass overriding this
    method is expected to provide a mechanism to switch back to the original
    user.

  .. method:: remove_user(username)

    Remove a user from the virtual user table.

Control connection
==================

.. class:: pyftpdlib.handlers.FTPHandler(conn, server)

  This class implements the FTP server Protocol Interpreter (see
  `RFC-959 <http://www.faqs.org/rfcs/rfc959.html>`_), handling commands received
  from the client on the control channel by calling the command's corresponding
  method (e.g. for received command "MKD pathname", ftp_MKD() method is called
  with pathname as the argument). All relevant session information are stored
  in instance variables. conn is the underlying socket object instance of the
  newly established connection, server is the
  :class:`pyftpdlib.servers.FTPServer` class instance. Basic usage simply
  requires creating an instance of FTPHandler class and specify which
  authorizer instance it will going to use:

  >>> from pyftpdlib.handlers import FTPHandler
  >>> handler = FTPHandler
  >>> handler.authorizer = authorizer

  All relevant session information is stored in class attributes reproduced
  below and can be modified before instantiating this class:

  .. data:: timeout

    The timeout which is the maximum time a remote client may spend between FTP
    commands. If the timeout triggers, the remote client will be kicked off
    (defaults to ``300`` seconds).

    *New in version 5.0*

  .. data:: banner

    String sent when client connects (default
    ``"pyftpdlib %s ready." %__ver__``).

  .. data:: max_login_attempts

    Maximum number of wrong authentications before disconnecting (default
    ``3``).

  .. data:: permit_foreign_addresses

    Whether enable FXP feature (default ``False``).

  .. data:: permit_privileged_ports

    Set to ``True`` if you want to permit active connections (PORT) over
    privileged ports (not recommended, default ``False``).

  .. data:: masquerade_address

    The "masqueraded" IP address to provide along PASV reply when pyftpdlib is
    running behind a NAT or other types of gateways. When configured pyftpdlib
    will hide its local address and instead use the public address of your NAT
    (default None).

  .. data:: masquerade_address_map

    In case the server has multiple IP addresses which are all behind a NAT
    router, you may wish to specify individual masquerade_addresses for each of
    them. The map expects a dictionary containing private IP addresses as keys,
    and their corresponding public (masquerade) addresses as values (defaults
    to ``{}``). *New in version 0.6.0*

  .. data:: passive_ports

    What ports ftpd will use for its passive data transfers. Value expected is
    a list of integers (e.g. ``range(60000, 65535)``). When configured
    pyftpdlib will no longer use kernel-assigned random ports (default
    ``None``).

  .. data:: use_gmt_times

    When ``True`` causes the server to report all ls and MDTM times in GMT and
    not local time (default ``True``). *New in version 0.6.0*

  .. data:: tcp_no_delay

    Controls the use of the TCP_NODELAY socket option which disables the Nagle
    algorithm resulting in significantly better performances (default ``True``
    on all platforms where it is supported). *New in version 0.6.0*

  .. data:: use_sendfile

    When ``True`` uses sendfile(2) system call to send a file resulting in
    faster uploads (from server to client). Works on UNIX only and requires
    `pysendfile <https://github.com/giampaolo/pysendfile>`__ module to be
    installed separately.

    *New in version 0.7.0*

  .. data:: auth_failed_timeout

    The amount of time the server waits before sending a response in case of
    failed authentication.

    *New in version 1.5.0*

  Follows a list of callback methods that can be overridden in a subclass. For
  blocking operations read the FAQ on how to run time consuming tasks.

  .. method:: on_connect()

    Called when client connects.

    *New in version 1.0.0*

  .. method:: on_disconnect()

    Called when connection is closed.

    *New in version 1.0.0*

  .. method:: on_login(username)

    Called on user login.

    *New in version 0.6.0*

  .. method:: on_login_failed(username, password)

    Called on failed user login.

    *New in version 0.7.0*

  .. method:: on_logout(username)

    Called when user logs out due to QUIT or USER issued twice. This is not
    called if client just disconnects without issuing QUIT first.

    *New in version 0.6.0*

  .. method:: on_file_sent(file)

    Called every time a file has been successfully sent. *file* is the
    absolute name of that file.

  .. method:: on_file_received(file)

    Called every time a file has been successfully received. *file* is the
    absolute name of that file.

  .. method:: on_incomplete_file_sent(file)

    Called every time a file has not been entirely sent (e.g. transfer aborted
    by client). *file* is the absolute name of that file.

    *New in version 0.6.0*

  .. method:: on_incomplete_file_received(file)

    Called every time a file has not been entirely received (e.g. transfer
    aborted by client). *file* is the absolute name of that file. *New in
    version 0.6.0*

Data connection
===============

.. class:: pyftpdlib.handlers.DTPHandler(sock_obj, cmd_channel)

  This class handles the server-data-transfer-process (server-DTP, see `RFC-959
  <http://www.faqs.org/rfcs/rfc959.html>`_) managing all transfer operations
  regarding the data channel. *sock_obj* is the underlying socket object
  instance of the newly established connection, cmd_channel is the
  :class:`pyftpdlib.handlers.FTPHandler` class instance.

  *Changed in version 1.0.0: added ioloop argument.*

  .. data:: timeout

    The timeout which roughly is the maximum time we permit data transfers to
    stall for with no progress. If the timeout triggers, the remote client will
    be kicked off (default ``300`` seconds).

  .. data:: ac_in_buffer_size
  .. data:: ac_out_buffer_size

    The buffer sizes to use when receiving and sending data (both defaulting to
    ``65536`` bytes). For LANs you may want this to be fairly large. Depending
    on available memory and number of connected clients setting them to a lower
    value can result in better performances.


.. class:: pyftpdlib.handlers.ThrottledDTPHandler(sock_obj, cmd_channel)

  A :class:`pyftpdlib.handlers.DTPHandler` subclass which wraps sending and
  receiving in a data counter and temporarily "sleeps" the channel so that you
  burst to no more than x Kb/sec average. Use it instead of
  :class:`pyftpdlib.handlers.DTPHandler` to set transfer rates limits for both
  downloads and/or uploads (see the
  `demo script <https://github.com/giampaolo/pyftpdlib/blob/master/demo/throttled_ftpd.py>`__
  showing the example usage).

  .. data:: read_limit

    The maximum number of bytes to read (receive) in one second (defaults to
    ``0`` == no limit)

  .. data:: write_limit

    The maximum number of bytes to write (send) in one second (defaults to
    ``0`` == no limit).

Server (acceptor)
=================

.. class:: pyftpdlib.servers.FTPServer(address_or_socket, handler, ioloop=None, backlog=100)

  Creates a socket listening on *address* (an ``(host, port)`` tuple) or a
  pre- existing socket object, dispatching the requests to *handler* (typically
  :class:`pyftpdlib.handlers.FTPHandler` class). Also, starts the asynchronous
  IO loop. *backlog* is the maximum number of queued connections passed to
  `socket.listen() <http://docs.python.org/library/socket.html#socket.socket.listen>`_.
  If a connection request arrives when the queue is full the client may raise
  ECONNRESET.

  *Changed in version 1.0.0: added ioloop argument.*

  *Changed in version 1.2.0: address can also be a pre-existing socket object.*

  *Changed in version 1.2.0: Added backlog argument.*

  *Changed in version 1.5.4: Support for the context manager protocol was
  added. Exiting the context manager is equivalent to calling
  :meth:`close_all`.*

  >>> from pyftpdlib.servers import FTPServer
  >>> address = ('127.0.0.1', 21)
  >>> server = FTPServer(address, handler)
  >>> server.serve_forever()

  It can also be used as a context manager. Exiting the context manager is
  equivalent to calling :meth:`close_all`.

  >>> with FTPServer(address, handler) as server:
  ...     server.serve_forever()

  .. data:: max_cons

    Number of maximum simultaneous connections accepted (default ``512``).

  .. data:: max_cons_per_ip

    Number of maximum connections accepted for the same IP address (default
    ``0`` == no limit).

  .. method:: serve_forever(timeout=None, blocking=True, handle_exit=True, worker_processes=1)

    Starts the asynchronous IO loop.

    - (float) timeout: the timeout passed to the underlying IO
      loop expressed in seconds.

    - (bool) blocking: if False loop once and then return the
      timeout of the next scheduled call next to expire soonest
      (if any).

    - (bool) handle_exit: when True catches ``KeyboardInterrupt`` and
      ``SystemExit`` exceptions (caused by SIGTERM / SIGINT signals) and
      gracefully exits after cleaning up resources. Also, logs server start and
      stop.

    - (int) worker_processes: pre-fork a certain number of child
      processes before starting. See: :ref:`pre-fork-model`.
      Each child process will keep using a 1-thread, async
      concurrency model, handling multiple concurrent connections.
      If the number is None or <= 0 the number of usable cores
      available on this machine is detected and used.
      It is a good idea to use this option in case the app risks
      blocking for too long on a single function call (e.g.
      hard-disk is slow, long DB query on auth etc.).
      By splitting the work load over multiple processes the delay
      introduced by a blocking function call is amortized and divided
      by the number of worker processes.

    *Changed in version 1.0.0*: no longer a classmethod

    *Changed in version 1.0.0*: 'use_poll' and 'count' parameters were removed

    *Changed in version 1.0.0*: 'blocking' and 'handle_exit' parameters were
    added

  .. method:: close()

    Stop accepting connections without disconnecting currently connected
    clients. :meth:`server_forever` loop will automatically stop when there are
    no more connected clients.

  .. method:: close_all()

    Disconnect all clients, tell :meth:`server_forever` loop to stop and wait
    until it does.

    *Changed in version 1.0.0: 'map' and 'ignore_all' parameters were removed.*

Filesystem
==========

.. class:: pyftpdlib.filesystems.FilesystemError

  Exception class which can be raised from within
  :class:`pyftpdlib.filesystems.AbstractedFS` in order to send custom error
  messages to client. *New in version 1.0.0*

.. class:: pyftpdlib.filesystems.AbstractedFS(root, cmd_channel)

  A class used to interact with the file system, providing a cross-platform
  interface compatible with both Windows and UNIX style filesystems where all
  paths use ``"/"`` separator. AbstractedFS distinguishes between "real"
  filesystem paths and "virtual" ftp paths emulating a UNIX chroot jail where
  the user can not escape its home directory (example: real "/home/user" path
  will be seen as "/" by the client). It also provides some utility methods and
  wraps around all os.* calls involving operations against the filesystem like
  creating files or removing directories. The contructor accepts two arguments:
  root which is the user "real" home directory (e.g. '/home/user') and
  cmd_channel which is the :class:`pyftpdlib.handlers.FTPHandler` class
  instance.

  *Changed in version 0.6.0: root and cmd_channel arguments were added.*

  .. data:: root

    User's home directory ("real"). *Changed in version 0.7.0: support
    setattr()*

  .. data:: cwd

    User's current working directory ("virtual").

    *Changed in version 0.7.0: support setattr()*

  .. method:: ftpnorm(ftppath)

    Normalize a "virtual" ftp pathname depending on the current working
    directory (e.g. having ``"/foo"`` as current working directory ``"bar"``
    becomes ``"/foo/bar"``).

  .. method:: ftp2fs(ftppath)

    Translate a "virtual" ftp pathname into equivalent absolute "real"
    filesystem pathname (e.g. having ``"/home/user"`` as root directory
    ``"foo"`` becomes ``"/home/user/foo"``).

  .. method:: fs2ftp(fspath)

    Translate a "real" filesystem pathname into equivalent absolute "virtual"
    ftp pathname depending on the user's root directory (e.g. having
    ``"/home/user"`` as root directory ``"/home/user/foo"`` becomes ``"/foo"``.

  .. method:: validpath(path)

    Check whether the path belongs to user's home directory. Expected argument
    is a "real" filesystem path. If path is a symbolic link it is resolved to
    check its real destination. Pathnames escaping from user's root directory
    are considered not valid (return ``False``).

  .. method:: open(filename, mode)

    Wrapper around
    `open() <http://docs.python.org/library/functions.html#open>`_ builtin.

  .. method:: mkdir(path)
  .. method:: chdir(path)
  .. method:: rmdir(path)
  .. method:: remove(path)
  .. method:: rename(src, dst)
  .. method:: chmod(path, mode)
  .. method:: stat(path)
  .. method:: lstat(path)
  .. method:: readlink(path)

    Wrappers around corresponding
    `os <http://docs.python.org/library/os.html>`_ module functions.

  .. method:: isfile(path)
  .. method:: islink(path)
  .. method:: isdir(path)
  .. method:: getsize(path)
  .. method:: getmtime(path)
  .. method:: realpath(path)
  .. method:: lexists(path)

    Wrappers around corresponding
    `os.path <http://docs.python.org/library/os.path.html>`_ module functions.

  .. method:: mkstemp(suffix='', prefix='', dir=None, mode='wb')

    Wrapper around
    `tempfile.mkstemp <http://docs.python.org/library/tempfile.html#tempfile.mkstemp>`_.

  .. method:: listdir(path)

    Wrapper around
    `os.listdir <http://docs.python.org/library/os.html#os.listdir>`_.
    It is expected to return a list of unicode strings or a generator yielding
    unicode strings.

    .. versionchanged:: 1.6.0 can also return a generator.


Extended classes
================

  We are about to introduces are extensions (subclasses) of the ones explained
  so far. They usually require third-party modules to be installed separately
  or are specific for a given Python version or operating system.

Extended handlers
-----------------

.. class:: pyftpdlib.handlers.TLS_FTPHandler(conn, server)

  A :class:`pyftpdlib.handlers.FTPHandler` subclass implementing FTPS (FTP over
  SSL/TLS) as described in `RFC-4217 <http://www.faqs.org/rfcs/rfc4217.html>`_
  implementing AUTH, PBSZ and PROT commands.
  `PyOpenSSL <http://pypi.python.org/pypi/pyOpenSSL>`_ module is required to be
  installed. Example below shows how to setup an FTPS server. Configurable
  attributes:

  .. data:: certfile

    The path to a file which contains a certificate to be used to identify the
    local side of the connection. This must always be specified, unless context
    is provided instead.

  .. data:: keyfile

    The path of the file containing the private RSA key; can be omittetted if
    certfile already contains the private key (defaults: ``None``).

  .. data:: ssl_protocol

     The desired SSL protocol version to use. This defaults to
     `SSL.SSLv23_METHOD` which will negotiate the highest protocol that both
     the server and your installation of OpenSSL support.

  .. data:: ssl_options

     specific OpenSSL options. These default to:
     `SSL.OP_NO_SSLv2 | SSL.OP_NO_SSLv3 | SSL.OP_NO_COMPRESSION` disabling
     SSLv2 and SSLv3 versions and SSL compression algorithm which are
     considered insecure.
     Can be set to None in order to improve compatibilty with older (insecure)
     FTP clients.

     .. versionadded:: 1.6.0

  .. data:: ssl_context

      A `SSL.Context <http://pyopenssl.sourceforge.net/pyOpenSSL.html/openssl-context.html>`__
      instance which was previously configured.
      If specified :data:`ssl_protocol` and :data:`ssl_options` parameters will
      be ignored.

  .. data:: tls_control_required

    When True requires SSL/TLS to be established on the control channel, before
    logging in. This means the user will have to issue AUTH before USER/PASS
    (default ``False``).

  .. data:: tls_data_required

    When True requires SSL/TLS to be established on the data channel. This
    means the user will have to issue PROT before PASV or PORT (default
    ``False``).

Extended authorizers
--------------------

.. class:: pyftpdlib.authorizers.UnixAuthorizer(global_perm="elradfmwMT", allowed_users=None, rejected_users=None, require_valid_shell=True, anonymous_user=None, ,msg_login="Login successful.", msg_quit="Goodbye.")

  Authorizer which interacts with the UNIX password database. Users are no
  longer supposed to be explicitly added as when using
  :class:`pyftpdlib.authorizers.DummyAuthorizer`. All FTP users are the same
  defined on the UNIX system so if you access on your system by using
  ``"john"`` as username and ``"12345"`` as password those same credentials can
  be used for accessing the FTP server as well. The user home directories will
  be automatically determined when user logins. Every time a filesystem
  operation occurs (e.g. a file is created or deleted) the id of the process is
  temporarily changed to the effective user id and whether the operation will
  succeed depends on user and file permissions. This is why full read and write
  permissions are granted by default in the class constructors.

  *global_perm* is a series of letters referencing the users permissions;
  defaults to "elradfmwMT" which means full read and write access for everybody
  (except anonymous). *allowed_users* and *rejected_users* options expect a
  list of users which are accepted or rejected for authenticating against the
  FTP server; defaults both to ``[]`` (no restrictions). *require_valid_shell*
  denies access for those users which do not have a valid shell binary listed in
  /etc/shells. If /etc/shells cannot be found this is a no-op. *anonymous user*
  is not subject to this option, and is free to not have a valid shell defined.
  Defaults to ``True`` (a valid shell is required for login). *anonymous_user*
  can be specified if you intend to provide anonymous access. The value
  expected is a string representing the system user to use for managing
  anonymous sessions;
  defaults to ``None`` (anonymous access disabled). Note that in order to use
  this class super user privileges are required.

  *New in version 0.6.0*

  .. method:: override_user(username=None, password=None, homedir=None, perm=None, anonymous_user=None, msg_login=None, msg_quit=None)

    Overrides one or more options specified in the class constructor for a
    specific user. Example:

    >>> from pyftpdlib.authorizers import UnixAuthorizer
    >>> auth = UnixAuthorizer(rejected_users=["root"])
    >>> auth = UnixAuthorizer(allowed_users=["matt", "jay"])
    >>> auth = UnixAuthorizer(require_valid_shell=False)
    >>> auth.override_user("matt", password="foo", perm="elr")

.. class:: pyftpdlib.authorizers.WindowsAuthorizer(global_perm="elradfmwMT", allowed_users=None, rejected_users=None, anonymous_user=None, anonymous_password="", msg_login="Login successful.", msg_quit="Goodbye.")

  Same as :class:`pyftpdlib.authorizers.UnixAuthorizer` except for
  *anonymous_password* argument which must be specified when defining the
  *anonymous_user*. Also requires_valid_shell option is not available. In
  order to use this class pywin32 extension must be installed.

  *New in version 0.6.0*

Extended filesystems
--------------------

.. class:: pyftpdlib.filesystems.UnixFilesystem(root, cmd_channel)

  Represents the real UNIX filesystem. Differently from
  :class:`pyftpdlib.filesystems.AbstractedFS` the client will login into
  /home/<username> and will be able to escape its home directory and navigate
  the real filesystem. Use it in conjuction with
  :class:`pyftpdlib.authorizers.UnixAuthorizer` to implement a "real" UNIX FTP
  server (see
  `demo/unix_ftpd.py <https://github.com/giampaolo/pyftpdlib/blob/master/demo/unix_ftpd.py>`__).

  *New in version 0.6.0*

Extended servers
----------------

.. class:: pyftpdlib.servers.ThreadedFTPServer(address_or_socket, handler, ioloop=None, backlog=5)

  A modified version of base :class:`pyftpdlib.servers.FTPServer` class which
  spawns a thread every time a new connection is established. Differently from
  base FTPServer class, the handler will be free to block without hanging the
  whole IO loop. See :ref:`changing-the-concurrency-model`.

  *New in version 1.0.0*

  *Changed in 1.2.0: added ioloop parameter; address can also be a pre-existing
  *socket.*

.. class:: pyftpdlib.servers.MultiprocessFTPServer(address_or_socket, handler, ioloop=None, backlog=5)

  A modified version of base :class:`pyftpdlib.servers.FTPServer` class which
  spawns a process every time a new connection is established. Differently from
  base FTPServer class, the handler will be free to block without hanging the
  whole IO loop. See :ref:`changing-the-concurrency-model`.

  *New in version 1.0.0*

  *Changed in 1.2.0: added ioloop parameter; address can also be a pre-existing socket.*

  *Availability: POSIX + Python >= 2.6*
