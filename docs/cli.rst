==================
Command line usage
==================

Pyftpdlib can also be run as a simple stand-alone server from the command line.
This is useful when you want to quickly share a directory. Here's some
examples.

Anonymous server, listening on port 2121, sharing the current directory:

.. code-block::

    $ python3 -m pyftpdlib
    [I 13-04-09 17:55:18] >>> starting FTP server on 0.0.0.0:2121, pid=6412 <<<
    [I 13-04-09 17:55:18] poller: <class 'pyftpdlib.ioloop.Epoll'>
    [I 13-04-09 17:55:18] masquerade (NAT) address: None
    [I 13-04-09 17:55:18] passive ports: None
    [I 13-04-09 17:55:18] use sendfile(2): True

Anonymous server with write permission:

.. code-block::

    $ python3 -m pyftpdlib --write

Specify a user with write permissions:

.. code-block::

    $ python3 -m pyftpdlib --username=bob --password=mypassword

Set a different address/port and home directory:

.. code-block::

    $ python3 -m pyftpdlib --interface=localhost --port=2121 --directory=/home/bob

Start a FTPS (FTP over SSL) server:

.. code-block::

    $ openssl req -x509 -newkey rsa:2048 -keyout ftpd.key -out ftpd.crt -nodes
    $ python3 -m pyftpdlib --tls --keyfile=ftpd.key --certfile=ftpd.crt

See ``python3 -m pyftpdlib -h`` for a complete list of options:

.. code-block::

    $ python3 -m pyftpdlib  -h
    usage: python3 -m pyftpdlib [options]

    Start a standalone anonymous FTP server.

    Options:
      -h, --help
                            show this help message and exit

    Main options:
      -i, --interface ADDRESS
                            specify the interface to run on (default: all interfaces)
      -p, --port PORT
                            specify port number to run on (default: 2121)
      -w, --write
                            grants write access for logged in user (default: read-only)
      -d, --directory PATH
                            specify the directory to share (default: current directory)
      -n, --nat-address ADDRESS
                            the NAT address to use for passive connections
      -r, --range FROM-TO
                            the range of TCP ports to use for passive connections (e.g. -r 8000-9000)
      -D, --debug
                            enable DEBUG logging level
      -u, --username USERNAME
                            specify username to login with (anonymous login will be disabled and password required if supplied)
      -P, --password PASSWORD
                            specify a password to login with (username required to be useful)
      --concurrency CONCURRENCY
                            the FTP server concurrency model to use, either 'async' (default), 'pre-fork', 'multi-thread' or 'multi-proc'

    Tls options:
      --tls   whether to enable FTPS (FTP over TLS); requires --keyfile and --certfile args
      --keyfile PATH
                            the TLS key file
      --certfile PATH
                            the TLS certificate file
      --tls-control-required
                            impose TLS for the control connection (before login)
      --tls-data-required
                            impose TLS for data connection

    Other options:
      --timeout TIMEOUT
                            connection timeout (default: 300 seconds)
      --banner BANNER
                            the message sent when client connects (default: 'pyftpdlib 2.1.0 ready.')
      --permit-foreign-addresses
                            allow data connections from an IP address different than the control connection
      --permit-privileged-ports
                            allow data connections (PORT) over privileged TCP ports
      --encoding ENCODING
                            the encoding used for client / server communication (default: utf8)
      --use-localtime
                            display directory listings with the time in your local time zone (default: use GMT)
      --disable-sendfile
                            disable sendfile() syscall, used for faster file transfers
      --max-cons MAX_CONS
                            max number of simultaneous connections (default: 512)
      --max-cons-per-ip MAX_CONS_PER_IP
                            maximum number connections from the same IP address (default: unlimited)
      --max-login-attempts MAX_LOGIN_ATTEMPTS
                            max number of failed authentications before disconnect (default: 3)
