=============
API reference
=============

.. contents:: Table of Contents

pyftpdlib implements the server side of the FTP protocol as defined in
`RFC-959 <https://datatracker.ietf.org/doc/html/rfc959.html>`_. This document is intended to
serve as a simple API reference of most important classes and functions.
Also see the `tutorial <tutorial.html>`_ document.

Modules and classes hierarchy
=============================

::

  pyftpdlib.authorizers.AuthenticationFailed
  pyftpdlib.authorizers.DummyAuthorizer
  pyftpdlib.authorizers.UnixAuthorizer
  pyftpdlib.authorizers.WindowsAuthorizer
  pyftpdlib.handlers.FTPHandler
  pyftpdlib.handlers.TLS_FTPHandler
  pyftpdlib.handlers.DTPHandler
  pyftpdlib.handlers.TLS_DTPHandler
  pyftpdlib.handlers.ThrottledDTPHandler
  pyftpdlib.filesystems.FilesystemError
  pyftpdlib.filesystems.AbstractedFS
  pyftpdlib.filesystems.UnixFilesystem
  pyftpdlib.servers.FTPServer
  pyftpdlib.servers.ThreadedFTPServer
  pyftpdlib.servers.MultiprocessFTPServer
  pyftpdlib.ioloop.IOLoop
  pyftpdlib.ioloop.Connector
  pyftpdlib.ioloop.Acceptor
  pyftpdlib.ioloop.AsyncChat

Users
=====

.. class:: pyftpdlib.authorizers.DummyAuthorizer()

  Basic "dummy" authorizer class which lets you create virtual users.
  It is also  suitable for subclassing to create your own custom authorizer.
  The "authorizer" is a class handling authentications and
  permissions of the FTP server. It is used by
  :class:`pyftpdlib.handlers.FTPHandler` class for verifying user passwords,
  getting users home directory and checking user permissions when a filesystem
  event occurs. Example usage:

  >>> from pyftpdlib.authorizers import DummyAuthorizer
  >>> authorizer = DummyAuthorizer()
  >>> authorizer.add_user('user', 'password', '/home/user', perm='elradfmwMT')
  >>> authorizer.add_anonymous('/home/nobody')

  .. method:: add_user(username, password, homedir, perm="elr", msg_login="Login successful.", msg_quit="Goodbye.")

    Add a user to the virtual users table. ``AuthorizerError`` exception is raised
    on error conditions such as insufficient permissions or duplicate usernames.
    The *perm* argument is a set of letters indicating the user's
    permissions:

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

    *msg_login* and *msg_quit* arguments can be specified to provide
    customized response strings when the user logs in and quits.

  .. method:: add_anonymous(homedir, **kwargs)

    Add an anonymous user to the virtual users table.
    The keyword arguments are the same expected by :meth:`add_user()` method.
    The only difference is that if write permissions are passed as *perm*
    a ``RuntimeWarning`` will be raised.

  .. method:: override_perm(username, directory, perm, recursive=False)

    Override user permissions for a specific directory.

  .. method:: validate_authentication(username, password, handler)

    Raises :class:`pyftpdlib.authorizers.AuthenticationFailed` if the supplied
    username and password don't match the stored credentials.

    *Changed in 1.0.0: new handler parameter.*

    *Changed in 1.0.0: an exception is now raised for signaling a failed authenticaiton as opposed to returning a bool.*

  .. method:: impersonate_user(username, password)

    Impersonate another user (noop). It is always called before accessing the
    filesystem. By default it does nothing. The subclass overriding this method
    may provide a mechanism to change the current user.

  .. method:: terminate_impersonation(username)

    Terminate impersonation (noop). It is always called after having accessed
    the filesystem. By default it does nothing. The subclass overriding this
    method may provide a mechanism to switch back to the original user.

  .. method:: remove_user(username)

    Remove a user from the virtual user table.

Control connection
==================

.. class:: pyftpdlib.handlers.FTPHandler(conn, server)

  This class implements the "FTP server Protocol Interpreter" as defined in
  `RFC-959 <https://datatracker.ietf.org/doc/html/rfc959.html>`_, commonly known as
  the FTP "control connection".
  It handles the commands received from the client.
  E.g. if command "MKD pathname" is received, ``ftp_MKD()`` method is called
  with ``pathname`` as the argument.
  ``conn`` argument is a socket object instance of the newly established connection.
  ``server`` is a reference to the :class:`pyftpdlib.servers.FTPServer` class
  instance.
  Basic usage requires creating an instance of this class and specify which
  authorizer it is going to use:

  >>> from pyftpdlib.handlers import FTPHandler
  >>> handler = FTPHandler
  >>> handler.authorizer = authorizer

  Configurable class attributes:

  .. data:: timeout

    The timeout which is the maximum time a remote client may spend between FTP
    commands. If the timeout triggers, the remote client will be kicked off.
    Default: ``300`` seconds.

    *New in version 5.0*

  .. data:: banner

    The string sent when client connects. The default is
    ``"pyftpdlib %s ready." %__ver__``. If you want to make this dynamic you
    can define this as a `property <https://docs.python.org/3/library/functions.html#property>`__.

  .. data:: max_login_attempts

    Maximum number of wrong authentications before disconnecting (default
    ``3``).

  .. data:: permit_foreign_addresses

    Also known as "FXP" or "site-to-site transfer feature". If ``True``
    it allows for transferring a file between two remote FTP servers,
    without the transfer going through the client's host. This is not
    recommended for security reasons as described in RFC-2577.
    Having this attribute set to ``False`` means that all data
    connections from/to remote IP addresses which do not match the
    client's IP address will be dropped. Default: ``False``.

  .. data:: permit_privileged_ports

    Set to ``True`` if you want to permit active connections (PORT) over
    privileged ports. Not recommended for security reason. Default: ``False``.

  .. data:: masquerade_address

    The "masqueraded" IP address to provide along PASV reply when pyftpdlib is
    running behind a NAT or other types of gateways. When configured pyftpdlib
    will hide its local address and instead use the public address of your NAT.
    Use this if you're behing a NAT. Default: ``None``.

  .. data:: masquerade_address_map

    In case the server has multiple IP addresses which are all behind a NAT,
    you may wish to specify individual masquerade addresses for each of
    them. The map expects a dictionary containing private IP addresses as keys,
    and their corresponding public (masquerade) addresses as values.
    Default: ``{}`` (empty dict).

    *New in version 0.6.0*

  .. data:: passive_ports

    What TCP ports the FTP server will use for passive (PASV) data transfers.
    The value expected is a list of integers (e.g. ``list(range(60000, 65535))``).
    When configured, pyftpdlib will no longer use kernel-assigned random TCP ports.
    Default: ``None``.

  .. data:: use_gmt_times

    When ``True`` causes the FTP server to report all times as GMT. This
    affects MDTM, MFMT, LIST, MLSD and MLST commands.
    If set to ``False``, the times will be expressed in the server local time
    (not recommended). Default: ``True``.

    *New in version 0.6.0*

  .. data:: tcp_no_delay

    Controls the use of the TCP_NODELAY socket option, which disables the Nagle
    algorithm. It usually result in significantly better performances.
    Default ``True`` on all platforms where it is supported.

    *New in version 0.6.0*

  .. data:: use_sendfile

    When ``True`` uses the ``sendfile(2)`` system call when sending file,
    resulting in considerable faster uploads (from server to client).
    Works on Linux only, and only for clear-text (non FTPS) transfers.
    Default: ``True`` on Linux.

    *New in version 0.7.0*

  .. data:: encoding

    The encoding used for client / server communication. Defaults to
    ``'utf-8'``.

    *New in version 2.0.0*

  .. data:: auth_failed_timeout

    The amount of time the server waits before sending a response in case of
    failed authentication. This is useful to prevent password-guessing attacks.
    Default: ``3`` seconds.

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

    Called when user logs out due to QUIT or USER commands issued twice. This
    is not called if the client just disconnects without issuing QUIT first.

    *New in version 0.6.0*

  .. method:: on_file_sent(file)

    Called when a file has been successfully sent. ``file`` is the absolute
    path of that file.

  .. method:: on_file_received(file)

    Called when a file has been successfully received. ``file`` is the
    absolute path of that file.

  .. method:: on_incomplete_file_sent(file)

    Called when time a file has not been entirely sent (e.g. transfer aborted
    by client). ``file`` is the absolute path of that file.

    *New in version 0.6.0*

  .. method:: on_incomplete_file_received(file)

    Called when a file has not been entirely received (e.g. transfer
    aborted by client). *file* is the absolute path of that file.

    *New in version 0.6.0*

Data connection
===============

.. class:: pyftpdlib.handlers.DTPHandler(sock_obj, cmd_channel)

  This class handles the server-data-transfer-process (server-DTP) as defined
  in `RFC-959 <https://datatracker.ietf.org/doc/html/rfc959.html>`_, commonly known as
  "data connection".
  It manages all the transfer operations like sending or receiving files and
  also transmitting the directory listing.
  ``sock_obj`` is the underlying socket object instance of the newly established
  connection, ``cmd_channel`` is the
  corresponding :class:`pyftpdlib.handlers.FTPHandler` class instance.

  *Changed in version 1.0.0: added ioloop argument.*

  .. data:: timeout

    The timeout which roughly is the maximum time we permit data transfers to
    stall for with no progress. If the timeout triggers, the remote client will
    be kicked off. Default: ``300`` seconds.

  .. data:: ac_in_buffer_size
  .. data:: ac_out_buffer_size

    The buffer sizes to use when receiving and sending data (both defaulting to
    ``65536`` bytes). For LANs you may want this to be fairly large. Depending
    on available memory and number of connected clients, setting them to a lower
    value can result in better performances.

.. class:: pyftpdlib.handlers.ThrottledDTPHandler(sock_obj, cmd_channel)

  A :class:`pyftpdlib.handlers.DTPHandler` subclass which wraps sending and
  receiving in a data counter, and temporarily "sleeps" the transmission of data
  so that you burst to no more than x Kb/sec average. Use it instead of
  :class:`pyftpdlib.handlers.DTPHandler` to set transfer rates limits for both
  downloads and/or uploads (see the
  `demo script <https://github.com/giampaolo/pyftpdlib/blob/master/demo/throttled_ftpd.py>`__
  showing the example usage).

  .. data:: read_limit

    The maximum number of bytes to read (receive) in one second. Defaults to
    ``0``, meaning no limit.

  .. data:: write_limit

    The maximum number of bytes to write (send) in one second. Defaults to
    ``0``, meaning no limit.

Server (acceptor)
=================

.. class:: pyftpdlib.servers.FTPServer(address_or_socket, handler, ioloop=None, backlog=100)

  Creates a socket listening on ``address`` (an ``(host, port)`` tuple) or a
  pre-existing socket object, dispatching the requests to ``handler`` (typically
  a :class:`pyftpdlib.handlers.FTPHandler` class). Also, it starts the main asynchronous
  IO loop. ``backlog`` is the maximum number of queued connections passed to
  `socket.listen() <https://docs.python.org/library/socket.html#socket.socket.listen>`_.

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

  ``FTPServer`` can also be used as a context manager. Exiting the context manager is
  equivalent to calling :meth:`close_all`.

  >>> with FTPServer(address, handler) as server:
  ...     server.serve_forever()

  .. data:: max_cons

    The number of maximum simultaneous connections accepted by the server
    (both control and data connections). Default: ``512``.

  .. data:: max_cons_per_ip

    Then number of maximum connections accepted for the same IP address.
    Default: ``0``, meaning no limit.

  .. method:: serve_forever(timeout=None, blocking=True, handle_exit=True, worker_processes=1)

    Starts the asynchronous IO loop.

    - ``timeout``: the timeout passed to the underlying IO
      loop expressed in seconds.

    - ``blocking``: if ``False`` loop once and then return the
      timeout of the next scheduled call next to expire soonest
      (if any).

    - ``handle_exit``: when ``True`` catches ``KeyboardInterrupt`` and
      ``SystemExit`` exceptions (caused by SIGTERM / SIGINT signals) and
      gracefully exits after cleaning up resources.
      Also, logs server start and stop.

    - ``worker_processes``: pre-forks a certain number of child
      processes before starting. See: :ref:`pre-fork-model` for more info.
      Each child process will keep using a 1-thread, async
      concurrency model, handling multiple concurrent connections.
      If the number is ``None`` or <= ``0``, the number of usable CPUs
      available on this machine is detected and used.
      It is a good idea to use this option in case the server risks
      blocking for too long on a single function call, typically if the
      filesystem is slow or the are long DB query executed on user login.
      By splitting the work load over multiple processes the delay
      introduced by a blocking function call is amortized and divided
      by the number of the worker processes.

    *Changed in version 1.0.0*: no longer a classmethod

    *Changed in version 1.0.0*: ``use_poll`` and ``count`` parameters were removed

    *Changed in version 1.0.0*: ``blocking`` and ``handle_exit`` parameters were
    added

  .. method:: close()

    Stop accepting connections without disconnecting the clients currently
    connected. :meth:`server_forever` loop will automatically stop when the last
    client disconnects.

  .. method:: close_all()

    Disconnect all clients, tell :meth:`server_forever` loop to stop and wait
    until it does.

    *Changed in version 1.0.0: ``map`` and ``ignore_all`` parameters were removed.*

Filesystem
==========

.. class:: pyftpdlib.filesystems.FilesystemError

  Exception class which can be raised from within
  :class:`pyftpdlib.filesystems.AbstractedFS` in order to send a custom error
  messages to the client.

  *New in version 1.0.0*

.. class:: pyftpdlib.filesystems.AbstractedFS(root, cmd_channel)

  A class used to interact with the filesystem, providing a cross-platform
  interface compatible with both Windows and UNIX paths. All paths use ``"/"``
  as the separator, including on Windows. ``AbstractedFS`` distinguishes
  between "real" filesystem paths and "virtual" FTP paths, emulating a UNIX
  chroot jail where the user can not escape his/her home directory (example:
  real "/home/user" path will be seen as "/" by the client). It also provides
  wrappers around all ``os.*`` calls (``mkdir``, ``rename``, etc) and ``open``
  builtin. The contructor accepts two arguments which are passed by the
  ``FTPHandler``: ``root``, which is the user "real" home
  directory (e.g. '/home/user') and ``cmd_channel`` which is a
  :class:`pyftpdlib.handlers.FTPHandler` class instance.

  *Changed in version 0.6.0: root and cmd_channel arguments were added.*

  .. data:: root

    User's home directory ("real").

    *Changed in version 0.7.0: support setattr()*

  .. data:: cwd

    User's current working directory ("virtual").

    *Changed in version 0.7.0: support setattr()*

  .. method:: ftpnorm(ftppath)

    Normalize a "virtual" FTP pathname depending on the current working
    directory. E.g. having ``"/foo"`` as current working directory, ``"bar"``
    is translated to ``"/foo/bar"``.

  .. method:: ftp2fs(ftppath)

    Translate a "virtual" FTP pathname into the equivalent absolute "real"
    filesystem pathname. E.g. having ``"/home/user"`` as the root directory,
    ``"foo"`` is translated to ``"/home/user/foo"``.

  .. method:: fs2ftp(fspath)

    Translate a "real" filesystem pathname into equivalent absolute "virtual"
    FTP pathname depending on the user's root directory. E.g. having
    ``"/home/user"`` as root directory, ``"/home/user/foo"`` is translated to
    ``"/foo"``.

  .. method:: validpath(path)

    Check whether the path belongs to the user's home directory. Expected
    argument is a "real" filesystem path. If path is a symbolic link it is
    resolved to check its real destination. Resolved symlinks which escape the
    user's root directory are considered not valid (return ``False``).
  .. method:: open(filename, mode)

    Wrapper around
    `open() <https://docs.python.org/library/functions.html#open>`_ builtin.

  .. method:: mkdir(path)
  .. method:: chdir(path)
  .. method:: rmdir(path)
  .. method:: remove(path)
  .. method:: rename(src, dst)
  .. method:: chmod(path, mode)
  .. method:: stat(path)
  .. method:: lstat(path)
  .. method:: readlink(path)

    Wrappers around the corresponding
    `os <https://docs.python.org/library/os.html>`_ module functions.

  .. method:: isfile(path)
  .. method:: islink(path)
  .. method:: isdir(path)
  .. method:: getsize(path)
  .. method:: getmtime(path)
  .. method:: realpath(path)
  .. method:: lexists(path)

    Wrappers around the corresponding
    `os.path <https://docs.python.org/library/os.path.html>`_ module functions.

  .. method:: mkstemp(suffix='', prefix='', dir=None, mode='wb')

    Wrapper around
    `tempfile.mkstemp <https://docs.python.org/library/tempfile.html#tempfile.mkstemp>`_.

  .. method:: listdir(path)

    Wrapper around
    `os.listdir <https://docs.python.org/library/os.html#os.listdir>`_.
    It is expected to return a list of strings or a generator yielding strings.

    .. versionchanged:: 1.6.0 can also return a generator.

Extended classes
================

  Classes that require third-party modules to be installed separately, or a
  specific to a given operating system.

Extended handlers
-----------------

.. class:: pyftpdlib.handlers.TLS_FTPHandler(conn, server)

  A :class:`pyftpdlib.handlers.FTPHandler` subclass implementing FTPS (FTP over
  SSL/TLS) as described in `RFC-4217 <https://datatracker.ietf.org/doc/html/rfc4217.html>`_.
  Implements AUTH, PBSZ and PROT commands.
  `PyOpenSSL <https://pypi.org/project/pyOpenSSL>`_ module is required to be
  installed. See :ref:`ftps-server` tutorial.
  Configurable attributes:

  .. data:: certfile

    The path to a file which contains a certificate to be used to identify the
    local side of the connection. This must always be specified, unless
    a :ref`:`ssl_context` is provided instead. See :ref:`ftps-server` on how to
    generate SSL certificates. Default: ``None``.

  .. data:: keyfile

    The path of the file containing the private RSA key. It can be omittetted
    if the :ref`:`certfile` already contains the private key.
    See :ref:`ftps-server` on how to generate SSL certificates.
    Default: ``None``.

  .. data:: ssl_protocol

    The desired SSL protocol version to use. This defaults to
    ``TLS_SERVER_METHOD``, which at the time of writing (year 2024) includes
    TLSv1, TLSv1.1, TLSv1.2 and TLSv1.3. The actual protocol version used will
    be negotiated to the highest version mutually supported by the client and
    the server when the client connects.

     .. versionchanged:: 2.0.0 set default to ``TLS_SERVER_METHOD``

  .. data:: ssl_options

     Specific OpenSSL options. This defaults to: ``OP_NO_SSLv2 | OP_NO_SSLv3 |
     OP_NO_COMPRESSION``, which are all considered unsecure settings. It can be
     set to ``None`` in order to improve compatibilty with older (insecure) FTP
     clients (not recommended).

     .. versionadded:: 1.6.0

  .. data:: ssl_context

      A `SSL.Context <https://www.pyopenssl.org/en/latest/api/ssl.html#context-objects>`__
      instance which was previously configured.
      When specified, :data:`ssl_protocol` and :data:`ssl_options` parameters
      are ignored.

  .. data:: tls_control_required

    If ``True`` it requires the client to secure the control connection with
    TLS before logging in. This means the client will have to issue the AUTH
    command before USER and PASS. Default: ``False``.

  .. data:: tls_data_required

    If ``True`` it requires the client to secure the data connection with TLS
    before logging in. This means the clie will have to issue the PROT command
    before PASV or PORT. Default: ``False``.

Extended authorizers
--------------------

.. class:: pyftpdlib.authorizers.UnixAuthorizer(global_perm="elradfmwMT", allowed_users=None, rejected_users=None, require_valid_shell=True, anonymous_user=None, ,msg_login="Login successful.", msg_quit="Goodbye.")

  An authorizer which interacts with the UNIX password database. Users are no
  longer supposed to be explicitly added as when using the
  :class:`pyftpdlib.authorizers.DummyAuthorizer`. All FTP users (and passwords)
  are the ones already defined on the UNIX system.
  The user home directory is automatically determined when user logins.
  Every time a filesystem
  operation occurs (e.g. a file is created or deleted) the ID of the process is
  temporarily changed to the effective user ID.
  In order to use this class super user privileges (root) are required.

  ``global_perm`` is a series of letters indicating the users permissions. It
  defaults to ``"elradfmwMT"`` which means full read and write access are
  granted to everybody (except the anonymous user).

  ``allowed_users`` and ``rejected_users`` are a list of users which are
  accepted or rejected for authenticating against the FTP server. Both
  parameters default to to ``[]`` (no restrictions).

  ``require_valid_shell`` denies access for those users which do not have a
  valid shell binary listed in /etc/shells. If /etc/shells cannot be found this
  is a no-op. ``anonymous_user`` is not subject to this option, and is free to
  not have a valid shell defined. Defaults to ``True``, meaning a valid shell
  is required for login).

  ``anonymous_user`` can be specified if you intend to provide anonymous
  access. The value expected is a string representing the system user to use
  for managing anonymous sessions. It defaults to ``None``, meaning anonymous
  access is disabled.

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
  ``anonymous_password`` argument which must be specified when defining the
  ``anonymous_user``. Also, ``requires_valid_shell`` option is not available. In
  order to use this class ``pywin32`` extension must be installed.

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

  *Availability: POSIX*
