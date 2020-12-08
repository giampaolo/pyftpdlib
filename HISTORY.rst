Bug tracker at https://github.com/giampaolo/pyftpdlib/issues

Version: 1.5.7 - XXXX-XX-XX
===========================

- #544: replace Travis with Github Actions for CI testing.

Version: 1.5.6 - 2020-02-16
===========================

**Enhancements**

- #467: added pre-fork concurrency model, spawn()ing worker processes to split
  load.
- #520: directory LISTing is now 3.7x times faster.

Version: 1.5.5 - 2019-04-04
===========================

**Enhancements**

- #495: colored test output.

**Bug fixes**

- #492: CRLF line endings are replaced with CRCRLF in ASCII mode downloads.
- #496: import error due to multiprocessing.Lock() bug.

Version: 1.5.4 - 2018-05-04
===========================

**Enhancements**

- #463: FTPServer class can now be used as a context manager.

**Bug fixes**

- #431: Ctrl-C doesn't exit `python -m pyftpdlib` on Windows.
- #436: ThreadedFTPServer.max_cons is evaluated threading.activeCount(). If
  the user uses threads of its own it will consume the number of max_cons.
- #447: ThreadedFTPServer and MultiprocessFTPServer do not join() tasks which
  are no longer consuming resources.

Version: 1.5.3 - 2017-11-04
===========================

**Enhancements**

- #201: implemented SITE MFMT command which changes file modification time.
  (patch by Tahir Ijaz)
- #327: add username and password command line options
- #433: documentation moved to readthedocs: http://pyftpdlib.readthedocs.io

**Bug fixes**

- #403: fix duplicated output log. (path by PonyPC)
- #414: Respond successfully to STOR only after closing file handle.

Version: 1.5.2 - 2017-04-06
===========================

**Enhancements**

- #378: SSL security was improved by disabling SSLv2, SSLv3 and SSL_COMPRESSION
  features. New TLS_FTPHandler's ssl_options class attribute was added.
- #380: AbstractedFS.listdir() can now return also a generator (not only a
  list).

**Bug fixes**

- #367: ThreadedFTPServer no longer hangs if close_all() is called.
- #394: ETIMEDOUT is not treated as an alias for "connection lost".
- #400: QUIT can raise KeyError in case the user hasn't logged in yet and sends
  QUIT command.


Version: 1.5.1 - 2016-05-02
===========================

**Bug fixes**

- #381: an extraneous file was accidentally added to the tarball, causing
  issues with Python 3.


Version: 1.5.0 - 2015-12-13
===========================

**Enhancements**

- #304: remove deprecated items from 1.0.0 which were left in place for
  backward compatibility
- #324: FTPHandler.started attribute, to figure out when client connected.
- #340: dropped python 2.4 and 2.5 support.
- #344: bench.py script --ssl option.
- #346: provide more debugging info.
- #348: FTPHandler has a new "auth_failed_timeout" class attribute (previously
  this was called _auth_failed_timeout).
- #350: tests now live in pyftpdlib module namespace.
- #351: fallback on using plain send() if sendfile() fails and no data has been
  transmitted yet.
- #356: sendfile() is now used in case we're using SSL but data connection is
  in clear text.
- #361: benchmark script now allows to benchmark downloads and uploads only
  (instead of both).
- #362: 'ftpbench' script is now installed as a system script on 'setup.py
  install'.
- #365: TLS FTP server is now 25% faster when dealing with clear-text
  connections.

**Bug fixes**

- #302: setup.py should not require pysendfile on Python >= 3.3.
- #313: configuring root logger has no effect on pyftpdlib logging.
- #329: IOLoop throws OSError on Linux.
- #337: MultiprocessFTPServer and ThreadedFTPServer do not accept backlog
  argument.
- #338: benchmark script uses old psutil API.
- #343: recv() does not handle EBUSY.
- #347: SSL WantReadError and WantWriteError errors are not properly taken into
  account.
- #357: python -m pyftpdlib --verbose option doesn't work

**Incompatible API changes**

- FTPHandler._auth_failed_timeout has been renamed to
  FTPHandler.auth_failed_timeout.


Version: 1.4.0 - Date: 2014-06-03
=================================

**Enhancements**

- #284: documentation was turned into RsT and hosted on pythonhosted.org
- #293: project was migrated from Google Code to Github. Code was migrated from
  SVN to GIT.
- #294: use tox to automate testing on multiple python versions.
- #295: use travis-ci for continuous test integration.
- #298: pysendfile and PyOpenSSL are now listed as extra deps in setup.py.

**Bug fixes**

- #296: TypeError when using recent version of PyOpenSSL.
- #297: listen() may raise EBADF in case of many connections.


Version: 1.3.1 - Date: 2014-04-12
=================================

**Enhancements**

- #262: FTPS is now able to load a certificate chain file.  (patch by
  Dmitry Panov)
- #277: added a make file for running tests and for other repetitive tasks
  (also for Windows).
- #281: tarballs are now hosted on PYPI.
- #282: support for /dev/poll on Solaris.
- #285: test suite requires unittest2 module on python < 2.7.

**Bug fixes**

- #261: (FTPS) SSL shutdown does not properly work on Windows.
- #280: (Python 2) unable to complete directory listing with invalid UTF8
  characters. (patch by dn@devicenull.org)
- #283: always use a single 'pyftpdlib' logger.


Version: 1.3.0 - Date: 2013-11-07
=================================

**Enhancements**

- #253: benchmark script's new --timeout option.
- #270: new -V / --verbose cmdline option to enable a more verbose logging.

**Bug fixes**

- #254: bench.py script hadn't been ported to Python 3.
- #263: MultiprocessFTPServer leaks memory and file descriptors.  (patch by
  Juan J. Martinez)
- #265: FTPServer class cannot be used with Circus.
- #272: pyftpdlib fails when imported on OpenBSD because of Python bug
  http://bugs.python.org/issue3770
- #273: IOLoop.fileno() on BSD systems raises AttributeError.  (patch by
  Michael Ross)


Version: 1.2.0 - Date: 2013-04-22
=================================

**Enhancements**

- #250: added FTPServer's backlog argument controlling the queue of accepted
        connections.
- #251: IOLoop.fileno() method for epoll() and kqueue() pollers.
- #252: FTPServer 'address' parameter can also be an existent socket object.

**Bug fixes**

- #245: ThreadedFTPServer hogs all CPU resources after a client connects.


Version: 1.1.0 - Date: 2013-04-09
=================================

**Enhancements**

- #240: enabled "python -m pyftpdlib" cmdline syntax and got rid of
  "python -m pyftpdlib.ftpserver" syntax which was deprecated in 1.0.0.
- #241: empty passwords are now allowed for anonymous and other users.
- #244: pysendfile is no longer a dependency if we're on Python >= 3.3 as
  os.sendfile() will be used instead.
- #247: on python 3.3 use time.monotonic() instead of time.time() so that the
  scheduler won't break in case of system clock updates.
- #248: bench.py memory usage is highly overestimated.

**Bug fixes**

- #238: username is not logged in case of failed authentication.
  (patch by tlockert)
- #243: an erroneous error message is given in case the address passed to
  bind() is already in use.
- #245: ThreadedFTPServer hogs all CPU resources after a client connects.
- #246: ThrottledDTPHandler was broken.

**Incompatible API changes**

- "python -m pyftpdlib.ftpserver" cmdline syntax doesn't work anymore


Version: 1.0.1 - Date: 2013-02-22
=================================

**Bug fixes**

- #236: MultiprocessFTPServer and ThreadedFTPServer hanging in case of failed
  authentication.


Version: 1.0.0 - Date: 2013-02-19
=================================

**Enhancements**

- #76: python 3.x porting.
- #198: full unicode support (RFC-2640).
- #203: asyncore IO loop has been rewritten from scratch and now supports
  epoll() on Linux and kqueue() on OSX/BSD.
  Also select() (Windows) and poll() pollers have been rewritten
  resulting in pyftpdlib being an order of magnitude faster and more
  scalable than ever.
- #204: a new FilesystemError exception class is available in order send
  custom error strings to client from an AbstracteFS subclass.
- #207: added on_connect() and on_disconnect() callback methods to FTPHandler
  class.
- #212: provided two new classes:
  Logging_managementpyftpdlib.servers.ThreadedFTPServer and
  pyftpdlib.servers.MultiprocessFTPServer (POSIX only).
  They can be used to change the base async-based concurrecy model and
  use a multiple threads / processes based approach instead.
  Your FTPHandler subclasses will finally be free to block! ;)
- #219: it is not possible to instantiate different FPTS classes using
  different SSL certificates.
- #213: DummyAuthorizer.validate_authentication() has changed in that it
  no longer returns a bool but instead raises AuthenticationFailed()
  exception to signal a failed authentication.
  This has been done in order allow customized error messages on failed
  auth. Also it now expects a third 'handler' argument which is passed in
  order to allow IP-based authentication logic. Existing code overriding
  validate_authentication() must be changed in accordance.
- #223: ftpserver.py has been split in submodules.
- #225: logging module is now used for logging. ftpserver.py's log(), logline()
  and logerror() functions are deprecated.
- #231: FTPHandler.ftp_* methods implementing filesystem-related commands
  now return a meaningful value on success (tipically the path name).
- #234: FTPHandler and DTPHandler class provide a nice __repr__.
- #235: FTPServer.serve_forever() has a new handle_exit parameter which
  can be set to False in order to avoid handling SIGTERM/SIGINT signals
  and logging server start and stop.
- #236: big logging refactoring; by default only useful messages are logged
  (as opposed to *all* commands and responses exchanged by client and
  server).  Also, FTPHandler has a new 'log_prefix' attribute which can
  be used to format every line logged.

**Bug fixes**

- #131: IPv6 dual-stack support was broken.
- #206: can't change directory (CWD) when using UnixAuthorizer and process
  cwd is == "/root".
- #211: pyftpdlib doesn't work if deprecated py-sendfile 1.2.4 module is
  installed.
- #215: usage of FTPHandler.sleeping attribute could lead to 100% CPU usage.
  FTPHandler.sleeping is now removed. self.add_channel() /
  self.del_channel() should be used instead.
- #222: an unhandled exception in handle_error() or close() can cause server
  to crash.
- #229: backslashes on UNIX are not handled properly.
- #232: hybrid IPv4/IPv6 support is broken.  (patch by Claus Klein)

**New modules**

All the code contained in pyftpdlib/ftpserver.py and pyftpdlib/contrib
namespaces has been moved here:

- pyftpdlib.authorizers
- pyftpdlib.filesystems
- pyftpdlib.servers
- pyftpdlib.handlers
- pyftpdlib.log

**New APIs**

- pyftpdlib.authorizers.AuthenticationFailed
- pyftpdlib.filesystems.FilesystemError
- pyftpdlib.servers.ThreadedFTPServer
- pyftpdlib.servers.MultiprocessFTPServer
- pyftpdlib.handlers.FTPHandler's on_connect() and on_disconnect() callbacks.
- pyftpdlib.handlers.FTPHandler.ftp_* methods return a meaningful value on
  success.
- FTPServer, FTPHandler, DTPHandler new ioloop attribute.
- pyftpdlib.lib.ioloop.IOLoop class (not supposed to be used directly)
- pyftpdlib.handlers.FTPHandler.log_prefix

**Deprecated name spaces**

- pyftpdlib.ftpserver
- pyftpdlib.contrib.*

**Incompatible API changes**

- All the main classes have been extracted from ftpserver.py and split into sub
  modules.

  +-------------------------------------+---------------------------------------+
  | Before                              | After                                 |
  +=====================================+=======================================+
  | pyftpdlib.ftpserver.FTPServer       | pyftpdlib.servers.FTPServer           |
  +-------------------------------------+---------------------------------------+
  | pyftpdlib.ftpserver.FTPHandler      | pyftpdlib.handlers.FTPHandler         |
  +-------------------------------------+---------------------------------------+
  | pyftpdlib.ftpserver.DTPHandler      | pyftpdlib.handlers.DTPHandler         |
  +-------------------------------------+---------------------------------------+
  | pyftpdlib.ftpserver.DummyAuthorizer | pyftpdlib.authorizers.DummyAuthorizer |
  +-------------------------------------+---------------------------------------+
  | pyftpdlib.ftpserver.AbstractedFS    | pyftpdlib.filesystems.AbstractedFS    |
  +-------------------------------------+---------------------------------------+

  Same for pyftpflib.contribs namespace which is deprecated.

  +-------------------------------------------------+-----------------------------------------+
  | Before                                          | After                                   |
  +=================================================+=========================================+
  | pyftpdlib.contrib.handlers.TLS_FTPHandler       | pyftpdlib.handlers.TLS_FTPHandler       |
  +-------------------------------------------------+-----------------------------------------+
  | pyftpdlib.contrib.authorizers.UnixAuthorizer    | pyftpdlib.authorizers.UnixAuthorizer    |
  +-------------------------------------------------+-----------------------------------------+
  | pyftpdlib.contrib.authorizers.WindowsAuthorizer | pyftpdlib.authorizers.WindowsAuthorizer |
  +-------------------------------------------------+-----------------------------------------+
  | pyftpdlib.contrib.filesystems.UnixFilesystem    | pyftpdlib.filesystems.UnixFilesystem    |
  +-------------------------------------------------+-----------------------------------------+

  Both imports from pyftpdlib.ftpserver and pyftpdlib.contrib.* will still work
  though and will raise a DeprecationWarning exception.

**Other incompatible API changes**

- DummyAuthorizer.validate_authentication() signature has changed. A third
  'handler' argument is now expected.
- DummyAuthorizer.validate_authentication() is no longer expected to return a
  bool. Instead it is supposed to raise AuthenticationFailed(msg) in case of
  failed authentication and return None otherwise.
  (see issue 213)
- ftpserver.py's log(), logline() and logerror() functions are deprecated.
  logging module is now used instead. See:
  http://code.google.com/p/billiejoex/wiki/Tutorial#4.2_-_Logging_management
- Unicode is now used instead of bytes pretty much everywhere.
- FTPHandler.__init__() and TLS_FTPHandler.__init__() signatures have changed:
  from __init__(conn, server)
  to   __init__(conn, server, ioloop=None)
- FTPServer.server_forever() signature has changed:
  from serve_forever(timeout=1.0, use_poll=False, count=None)
  to   serve_forever(timeout=1.0, blocking=True, handle_exit=True)
- FTPServer.close_all() signature has changed:
  from close_all(ignore_all=False)
  to   close_all()
- FTPServer.serve_forever() and FTPServer.close_all() are no longer class
  methods.
- asyncore.dispatcher and asynchat.async_chat classes has been replaced by:
  pyftpdlib.ioloop.Acceptor
  pyftpdlib.ioloop.Connector
  pyftpdlib.ioloop.AsyncChat
  Any customization relying on asyncore (e.g. use of asyncore.socket_map to
  figure out the number of connected clients) will no longer work.
- pyftpdlib.ftpserver.CallLater and pyftpdlib.ftpserver.CallEvery are
  deprecated. Instead, use self.ioloop.call_later() and self.ioloop.call_every()
  from within the FTPHandler.  Also delay() method of the returned object has
  been removed.
- FTPHandler.sleeping attribute is removed. self.add_channel() and
  self.del_channel() should be used to pause and restart the handler.

**Minor incompatible API changes**

- FTPHandler.respond(resp) -> FTPHandler.respond(resp, logfun=logger.debug)
- FTPHandler.log(resp)     -> FTPHandler.log(resp, logfun=logger.info)
- FTPHandler.logline(resp) -> FTPHandler.logline(resp, logfun=logger.debug)

Version: 0.7.0 - Date: 2012-01-25
=================================

**Enhancements**

- #152: uploads (from server to client) on UNIX are now from 2x (Linux) to 3x
  (OSX) faster because of sendfile(2) system call usage.
- #155: AbstractedFS "root" and "cwd" are no longer read-only properties but
  can be set via setattr().
- #168: added FTPHandler.logerror() method. It can be overridden to provide
  more information (e.g. username) when logging exception tracebacks.
- #174: added support for SITE CHMOD command (change file mode).
- #177: setuptools is now used in setup.py
- #178: added anti flood script in demo directory.
- #181: added CallEvery class to call a function every x seconds.
- #185: pass Debian licenscheck tool.
- #189: the internal scheduler has been rewritten from scratch and it is an
  order of magnitude faster, especially for operations like cancel()
  which are involved when clients are disconnected (hence invoked very
  often). Some benchmarks:
  schedule:   +0.5x,
  reschedule: +1.7x,
  cancel:     +477x (with 1 million scheduled functions),
  run: +8x
  Also, a single scheduled function now consumes 1/3 of the memory thanks
  to ``__slots__`` usage.
- #195: enhanced unix_daemon.py script which (now uses python-daemon library).
- #196: added callback for failed login attempt.
- #200: FTPServer.server_forever() is now a class method.
- #202: added benchmark script.

**Bug fixes**

- #156: data connection must be closed before sending 226/426 reply. This was
  against RFC-959 and was causing problems with older FTP clients.
- #161: MLSD 'unique' fact can provide the same value for files having a
  similar device/inode but that in fact are different.
  (patch by Andrew Scheller)
- #162: (FTPS) SSL shutdown() is not invoked for the control connection.
- #163: FEAT erroneously reports MLSD. (patch by Andrew Scheller)
- #166: (FTPS) an exception on send() can cause server to crash (DoS).
- #167: fix some typos returned on HELP.
- #170: PBSZ and PROT commands are now allowed before authentication fixing
  problems with non-compliant FTPS clients.
- #171: (FTPS) an exception when shutting down the SSL layer can cause server
  to crash (DoS).
- #173: file last modification time shown in LIST response might be in a
  language different than English causing problems with some clients.
- #175: FEAT response now omits to show those commands which are removed from
  proto_cmds map.
- #176: SO_REUSEADDR option is now used for passive data sockets to prevent
  server running out of free ports when using passive_ports directive.
- #187: match proftpd LIST format for files having last modification time
  > 6 months.
- #188: fix maximum recursion depth exceeded exception occurring if client
  quickly connects and disconnects data channel.
- #191: (FTPS) during SSL shutdown() operation the server can end up in an
  infinite loop hogging CPU resources.
- #199: UnixAuthorizer with require_valid_shell option is broken.

**Major API changes since 0.6.0**

- New FTPHandler.use_sendfile attribute.
- sendfile() is now automatically used instead of plain send() if
  pysendfile module is installed.
- FTPServer.serve_forever() is a classmethod.
- AbstractedFS root and cwd properties can now be set via setattr().
- New CallLater class.
- New FTPHandler.on_login_failed(username, password) method.
- New FTPHandler.logerror(msg) method.
- New FTPHandler.log_exception(instance) method.


Version: 0.6.0 - Date: 2011-01-24
=================================

**Enhancements**

- #68: added full FTPS (FTP over SSL/TLS) support provided by new
  TLS_FTPHandler class defined in pyftpdlib.contrib.handlers module.
- #86:  pyftpdlib now reports all ls and MDTM timestamps as GMT times, as
  recommended in RFC-3659.  A FTPHandler.use_gmt_times attributed has
  been added and can be set to False in case local times are desired
  instead.
- #124: pyftpdlib now accepts command line options to configure a stand alone
  anonymous FTP server when running pyftpdlib with python's -m option.
- #125: logs are now provided in a standardized format parsable by log
  analyzers. FTPHandler class provides two new methods to standardize
  both commands and transfers logging: log_cmd() and log_transfer().
- #127: added FTPHandler.masquerade_address_map option which allows you to
  define multiple 1 to 1 mappings in case you run a FTP server with
  multiple private IP addresses behind a NAT firewall with multiple
  public IP addresses.
- #128: files and directories owner and group names and os.readlink are now
  resolved via AbstractedFS methods instead of in format_list().
- #129, #139: added 4 new callbacks to FTPHandler class:
  on_incomplete_file_sent(), on_incomplete_file_received(), on_login()
  and on_logout().
- #130: added UnixAuthorizer and WindowsAuthorizer classes defined in the new
  pyftpdlib.contrib.authorizers module.
- #131: pyftpdlib is now able to serve both IPv4 and IPv6 at the same time by
  using a single socket.
- #133: AbstractedFS constructor now accepts two argumets: root and cmd_channel
  breaking compatibility with previous version.  Also, root and and cwd
  attributes became properties.  The previous bug consisting in resetting
  the root from the ftp handler after user login has been fixed to ease
  the development of subclasses.
- #134: enabled TCP_NODELAY socket option for the FTP command channels
  resulting in pyftpdlib being twice faster.
- #135: Python 2.3 support has been dropped.
- #137: added new pyftpdlib.contrib.filesystems module within
  UnixFilesystem class which permits the client to escape its home
  directory and navigate the real filesystem.
- #138: added DTPHandler.get_elapsed_time() method which returns the transfer
  elapsed time in seconds.
- #144: a "username" parameter is now passed to authorizer's
  terminate_impersonation() method.
- #149: ftpserver.proto_cmds dictionary refactoring and get rid of
  _CommandProperty class.

**Bug fixes**

- #120: an ActiveDTP() instance is not garbage collected in case a client
  issuing PORT disconnects before establishing the data connection.
- #122: a wrong variable name was used in AbstractedFS.validpath method.
- #123: PORT command doesn't bind to correct address in case an alias is
  created for the local network interface.
- #140: pathnames returned in PWD response should have double-quotes '"'
  escaped.
- #143: EINVAL not properly handled causes server crash on OSX.
- #146: SIZE and MDTM commands are now rejected unless the "l" permission has
  been specified for the user.
- #150: path traversal bug: it is possible to move/rename a file outside of the
  user home directory.

**Major API changes since 0.5.2**

- dropped Python 2.3 support.
- all classes are now new-style classes.
- AbstractedFS class:
    - __init__ now accepts two arguments: root and cmd_channel.
    - root and cwd attributes are now read-only properties.
    - 3 new methods have been added:
       - get_user_by_uid()
       - get_group_by_gid()
       - readlink()
- FTPHandler class:
    - new class attributes:
       - use_gmt_times
       - tcp_no_delay
       - masquerade_address_map
    - new methods:
       - on_incomplete_file_sent()
       - on_incomplete_file_received()
       - on_login()
       - on_logout()
       - log_cmd()
       - log_transfer()
    - proto_cmds class attribute has been added.  The FTPHandler class no
       longer relies on "ftpserver.proto_cmds" global dictionary but on
       "ftpserver.FTPHandler.proto_cmds" instead.
- FTPServer class:
     - max_cons attribute defaults to 512 by default instead of 0 (unlimited).
     - server_forever()'s map argument is gone.
- DummyAuthorizer:
     - ValueError exceptions are now raised instead of AuthorizerError.
     - terminate_impersonation() method now expects a "username" parameter.
- DTPHandler.get_elapsed_time() method has been added.
- Added a new package in pyftpdlib namespace: "contrib". Modules (and classes)
   defined here:
     - pyftpdlib.contrib.handlers.py (TLS_FTPHandler)
     - pyftpdlib.contrib.authorizers.py (UnixAuthorizer, WindowsAuthorizer)
     - pyftpdlib.contrib.filesystems (UnixFilesystem)

**Minor API changes since 0.5.2**

- FTPHandler renamed objects:
    - data_server -> _dtp_acceptor
    - current_type -> _current_type
    - restart_position -> _restart_position
    - quit_pending -> _quit_pending
    - af -> _af
    - on_dtp_connection -> _on_dtp_connection
    - on_dtp_close -> _on_dtp_close
    - idler -> _idler
- AbstractedFS.rnfr attribute moved to FTPHandler._rnfr.


Version: 0.5.2 - Date: 2009-09-14
=================================

**Enhancements**

- #103: added unix_daemon.py script.
- #108: a new ThrottledDTPHandler class has been added for limiting the speed
  of downloads and uploads.

**Bug fixes**

- #100: fixed a race condition in FTPHandler constructor which could throw an
  exception in case of connection bashing (DoS).  (thanks Bram Neijt)
- #102: FTPServer.close_all() now removes any unfired delayed call left behind
  to prevent potential memory leaks.
- #104: fixed a bug in FTPServer.handle_accept() where socket.accept() could
  return None instead of a valid address causing the server to crash.
  (OS X only, reported by Wentao Han)
- #104: an unhandled EPIPE exception might be thrown by asyncore.recv() when
  dealing with ill-behaved clients on OS X . (reported by Wentao Han)
- #105: ECONNABORTED might be thrown by socket.accept() on FreeBSD causing the
  server to crash.
- #109: an unhandled EBADF exception might be thrown when using poll() on OSX
  and FreeBSD.
- #111: the license used was not MIT as stated in source files.
- #112: fixed a MDTM related test case failure occurring on 64 bit OSes.
- #113: fixed unix_ftp.py which was treating anonymous as a normal user.
- #114: MLST is now denied unless the "l" permission has been specified for the
  user.
- #115: asyncore.dispatcher.close() is now called before doing any other
  cleanup operation when client disconnects. This way we avoid an endless
  loop which hangs the server in case an exception is raised in close()
  method. (thanks Arkadiusz Wahlig)
- #116: extra carriage returns were added to files transferred in ASCII mode.
- #118: CDUP always changes to "/".
- #119: QUIT sent during a transfer caused a memory leak.

**API changes since 0.5.1**

- ThrottledDTPHandler class has been added.
- FTPHandler.process_command() method has been added.


Version: 0.5.1 - Date: 2009-01-21
=================================

**Enhancements**

- #79: added two new callback methods to FTPHandler class to handle
  "on_file_sent" and "on_file_received" events.
- #82: added table of contents in documentation.
- #92: ASCII transfers are now 200% faster on those systems using "\r\n" as
  line separator (typically Windows).
- #94: a bigger buffer size for send() and recv() has been set resulting in a
  considerable speedup (about 40% faster) for both incoming and outgoing
  data transfers.
- #98: added preliminary support for SITE command.
- #99: a new script implementing FTPS (FTP over TLS/SSL) has been added to the
  demo directory. See:
  http://code.google.com/p/pyftpdlib/source/browse/trunk/demo/tls_ftpd.py

**Bug fixes**

- #78: the idle timeout of passive data connections gets stopped in case of
  rejected "site-to-site" connections.
- #80: demo/md5_ftpd.py should use hashlib module instead of the deprecated md5
  module.
- #81: fixed some tests which were failing on SunOS.
- #84: fixed a very rare unhandled exception which could occur when retrieving
  the first bytes of a corrupted file.
- #85: a positive MKD response is supposed to include the name of the new
  directory.
- #87: SIZE should be rejected when the current TYPE is ASCII.
- #88: REST should be rejected when the current TYPE is ASCII.
- #89: "TYPE AN" was erroneously treated as synonym for "TYPE A" when "TYPE L7"
  should have been used instead.
- #90: an unhandled exception can occur when using MDTM against a file modified
  before year 1900.
- #91: an unhandled exception can occur in case accept() returns None instead
  of a socket (it happens sometimes).
- #95: anonymous is now treated as any other case-sensitive user.

**API changes since 0.5.0**

- FTPHandler gained a new "_extra_feats" private attribute.
- FTPHandler gained two new methods: "on_file_sent" and "on_file_received".


Version: 0.5.0 - Date: 2008-09-20
=================================

**Enhancements**

- #72: pyftpdlib now provides configurable idle timeouts to disconnect client
  after a long time of inactivity.
- #73: imposed a delay before replying for invalid credentials to minimize the
  risk of brute force password guessing (RFC-1123).
- #74: it is now possible to define permission exceptions for certain
  directories (e.g. creating a user which does not have write permission
  except for one sub-directory in FTP root).
- #: Improved bandwidth throttling capabilities of demo/throttled_ftpd.py
  script  by having used the new CallLater class which drastically reduces
  the number of time.time() calls.

**Bug fixes**

- #62: some unit tests were failing on certain dual core machines.
- #71: socket handles are leaked when a data transfer is in progress and user
  QUITs.
- #75: orphaned file was left behind in case STOU failed for insufficient user
  permissions.
- #77: incorrect OOB data management on FreeBSD.

**API changes since 0.4.0**

- FTPHandler, DTPHandler, PassiveDTP and ActiveDTP classes gained a new timeout
  class attribute.
- DummyAuthorizer class gained a new override_perm method.
- A new class called CallLater has been added.
- AbstractedFS.get_stat_dir method has been removed.


Version: 0.4.0 - Date: 2008-05-16
=================================

**Enhancements**

- #65: It is now possible to assume the id of real users when using system
  dependent authorizers.
- #67: added IPv6 support.

**Bug fixes**

- #64: Issue #when authenticating as anonymous user when using UNIX and Windows
  authorizers.
- #66: WinNTAuthorizer does not determine the real user home directory.
- #69: DummyAuthorizer incorrectly uses class attribute instead of instance
  attribute for user_table dictionary.
- #70: a wrong NOOP response code was given.

**API changes since 0.3.0**

- DummyAuthorizer class has now two new methods: impersonate_user() and
  terminate_impersonation().


Version: 0.3.0 - Date: 2008-01-17
=================================

**Enhancements**

- #42: implemented FEAT command (RFC-2389).
- #48: real permissions, owner, and group for files on UNIX platforms are now
  provided when processing LIST command.
- #51: added the new demo/throttled_ftpd.py script.
- #52: implemented MLST and MLSD commands (RFC-3659).
- #58: implemented OPTS command (RFC-2389).
- #59: iterators are now used for calculating requests requiring long time to
  complete (LIST and MLSD commands) drastically increasing the daemon
  scalability when dealing with many connected clients.
- #61: extended the set of assignable user permissions.

**Bug fixes**

- #41: an unhandled exception occurred on QUIT if user was not yet
  authenticated.
- #43: hidden the server identifier returned in STAT response.
- #44: a wrong response code was given on PORT in case of failed connection
  attempt.
- #45: a wrong response code was given on HELP if the provided argument wasn't
  recognized as valid command.
- #46: a wrong response code was given on PASV in case of unauthorized FXP
  connection attempt.
- #47: can't use FTPServer.max_cons option on Python 2.3.
- #49: a "550 No such file or directory" was returned when LISTing a directory
  containing a broken symbolic link.
- #50: DTPHandler class did not respect what specified in ac_out_buffer_size
  attribute.
- #53: received strings having trailing white spaces was erroneously stripped.
- #54: LIST/NLST/STAT outputs are now sorted by file name.
- #55: path traversal vulnerability in case of symbolic links escaping user's
  home directory.
- #56: can't rename broken symbolic links.
- #57: invoking LIST/NLST over a symbolic link which points to a direoctory
  shouldn't list its content.
- #60: an unhandled IndexError exception error was raised in case of certain
  bad formatted PORT requests.

**API changes since 0.2.0**

- New IteratorProducer and BufferedIteratorProducer classes have been added.
- DummyAuthorizer class changes:
    - The permissions management has been changed and the set of available
       permissions have been extended (see Issue #61). add_user() method
       now accepts "eladfm" permissions beyond the old "r" and "w".
    - r_perm() and w_perm() methods have been removed.
    - New has_perm() and get_perms() methods have been added.

- AbstractedFS class changes:
    - normalize() method has been renamed in ftpnorm().
    - translate() method has been renamed in ftp2fs().
    - New methods: fs2ftp(), stat(), lstat(), islink(), realpath(), lexists(),
       validpath().
    - get_list_dir(), get_stat_dir() and format_list() methods now return an
       iterator object instead of a string.
    - format_list() method has a new "ignore_err" keyword argument.
- global debug() function has been removed.


Version: 0.2.0 - Date: 2007-09-17
=================================

**Major enhancements**

- #5: it is now possible to set a maximum number of connections and a maximum
  number of connections from the same IP address.
- #36: added support for FXP site-to-site transfer.
- #39: added NAT/Firewall support with PASV (passive) mode connections.
- #40: it is now possible to set a range of ports to use for passive
  connections.

**RFC-related enhancements**

- #6: accept TYPE AN and TYPE L8 as synonyms for TYPE ASCII and TYPE Binary.
- #7: a new USER command can now be entered at any point to begin the login
  sequence again.
- #10: HELP command arguments are now accepted.
- #12: 554 error response is now returned on RETR/STOR if RESTart fails.
- #15: STAT used with an argument now returns directory LISTing over the
  command channel (RFC-959).

**Security Enhancements**

- #3: stop buffering when extremely long lines are received over the command
  channel.
- #11: data connection is now rejected in case a privileged port is specified
  in PORT command.
- #25: limited the number of attempts to find a unique filename when
  processing STOU command.

**Usability enhancements**

- #: Provided an overridable attribute to easily set number of maximum login
  attempts before disconnecting.
- #: Docstrings are now provided for almost every method and function.
- #30: HELP response now includes the command syntax.
- #31: a compact list of recognized commands is now provided on HELP.
- #32: a detailed error message response is not returned to client in
  case the transfer is interrupted for some unexpected reason.
- #38: write access can now be optionally granted for anonymous user.

**Test suite enhancements**

- # File creation/removal moved into setUp and tearDown methods to avoid
  leaving behind orphaned temporary files in the event of a test suite
  failure.
- #7: added test case for USER provided while already authenticated.
- #7: added test case for REIN while a transfer is in progress.
- #28: added ABOR tests.

**Bug fixes**

- #4: socket's "reuse_address" feature was used after the socket's binding.
- #8: STOU string response didn't follow RFC-1123 specifications.
- #9: corrected path traversal vulnerability affecting file-system path
  translations.
- #14: a wrong response code was returned on CDUP.
- #17: SIZE is now rejected for not regular files.
- #18: a wrong ABOR response code type was returned.
- #19: watch for STOU preceded by REST which makes no sense.
- #20: "attempted login" counter wasn't incremented on wrong username.
- #21: STAT wasn't permitted if user wasn't authenticated yet.
- #22: corrected memory leaks occurring on KeyboardInterrupt/SIGTERM.
- #23: PASS wasn't rejected when user was already authenticated.
- #24: Implemented a workaround over os.strerror() for those systems where it
  is not available (Python CE).
- #24: problem occurred on Windows when using '\\' as user's home directory.
- #26: select() in now used by default instead of poll() because of a bug
  inherited from asyncore.
- #33: some FTPHandler class attributes wasn't resetted on REIN.
- #35: watch for APPE preceded by REST which makes no sense.


Version: 0.1.1 - Date: 2007-03-27
=================================

- Port selection on PASV command has been randomized to prevent a remote user
  to guess how many data connections are in progress on the server.
- Fixed bug in demo/unix_ftpd.py script.
- ftp_server.serve_forever now automatically re-use address if current system
  is posix.
- License changed to MIT.


Version: 0.1.0 - Date: 2007-02-26
=================================

- First proof of concept beta release.
