# Copyright (C) 2007 Giampaolo Rodola' <g.rodola@gmail.com>.
# Use of this source code is governed by MIT license that can be
# found in the LICENSE file.

import errno
import random
import socket
import sys
import traceback

from pyftpdlib.ioloop import Acceptor
from pyftpdlib.ioloop import Connector
from pyftpdlib.log import debug
from pyftpdlib.log import logger

__all__ = ["ActiveDTP", "PassiveDTP"]


class PassiveDTP(Acceptor):
    """Creates a socket listening on a local port, dispatching the
    resultant connection to DTPHandler. Used for handling PASV command.

     - (int) timeout: the timeout for a remote client to establish
       connection with the listening socket. Defaults to 30 seconds.

     - (int) backlog: the maximum number of queued connections passed
       to listen(). If a connection request arrives when the queue is
       full the client may raise ECONNRESET. Defaults to 5.
    """

    timeout = 30
    backlog = None

    def __init__(self, cmd_channel, extmode=False):
        """Initialize the passive data server.

        - (instance) cmd_channel: the command channel class instance.
        - (bool) extmode: whether use extended passive mode response type.
        """
        self.cmd_channel = cmd_channel
        self.log = cmd_channel.log
        self.log_exception = cmd_channel.log_exception
        Acceptor.__init__(self, ioloop=cmd_channel.ioloop)

        local_ip = self.cmd_channel.socket.getsockname()[0]
        if local_ip in self.cmd_channel.masquerade_address_map:
            masqueraded_ip = self.cmd_channel.masquerade_address_map[local_ip]
        elif self.cmd_channel.masquerade_address:
            masqueraded_ip = self.cmd_channel.masquerade_address
        else:
            masqueraded_ip = None

        if self.cmd_channel.server.socket.family != socket.AF_INET:
            # dual stack IPv4/IPv6 support
            af = self.bind_af_unspecified((local_ip, 0))
            self.socket.close()
            self.del_channel()
        else:
            af = self.cmd_channel.socket.family

        self.create_socket(af, socket.SOCK_STREAM)

        if self.cmd_channel.passive_ports is None:
            # By using 0 as port number value we let kernel choose a
            # free unprivileged random port.
            self.bind((local_ip, 0))
        else:
            ports = list(self.cmd_channel.passive_ports)
            while ports:
                port = ports.pop(random.randint(0, len(ports) - 1))
                self.set_reuse_addr()
                try:
                    self.bind((local_ip, port))
                except PermissionError:
                    self.cmd_channel.log(
                        f"ignoring EPERM when bind()ing port {port}",
                        logfun=logger.debug,
                    )
                except OSError as err:
                    if err.errno == errno.EADDRINUSE:  # port already in use
                        if ports:
                            continue
                        # If cannot use one of the ports in the configured
                        # range we'll use a kernel-assigned port, and log
                        # a message reporting the issue.
                        # By using 0 as port number value we let kernel
                        # choose a free unprivileged random port.
                        else:
                            self.bind((local_ip, 0))
                            self.cmd_channel.log(
                                "Can't find a valid passive port in the "
                                "configured range. A random kernel-assigned "
                                "port will be used.",
                                logfun=logger.warning,
                            )
                    else:
                        raise
                else:
                    break
        self.listen(self.backlog or self.cmd_channel.server.backlog)

        port = self.socket.getsockname()[1]
        if not extmode:
            ip = masqueraded_ip or local_ip
            if ip.startswith("::ffff:"):
                # In this scenario, the server has an IPv6 socket, but
                # the remote client is using IPv4 and its address is
                # represented as an IPv4-mapped IPv6 address which
                # looks like this ::ffff:151.12.5.65, see:
                # https://en.wikipedia.org/wiki/IPv6#IPv4-mapped_addresses
                # https://datatracker.ietf.org/doc/html/rfc3493.html#section-3.7
                # We truncate the first bytes to make it look like a
                # common IPv4 address.
                ip = ip[7:]
            # The format of 227 response in not standardized.
            # This is the most expected:
            resp = "227 Entering passive mode (%s,%d,%d)." % (
                ip.replace(".", ","),
                port // 256,
                port % 256,
            )
            self.cmd_channel.respond(resp)
        else:
            self.cmd_channel.respond(
                f"229 Entering extended passive mode (|||{int(port)}|)."
            )
        if self.timeout:
            self.call_later(self.timeout, self.handle_timeout)

    # --- connection / overridden

    def handle_accepted(self, sock, addr):
        """Called when remote client initiates a connection."""
        if not self.cmd_channel.connected:
            return self.close()

        # Check the origin of data connection.  If not expressively
        # configured we drop the incoming data connection if remote
        # IP address does not match the client's IP address.
        if self.cmd_channel.remote_ip != addr[0]:
            if not self.cmd_channel.permit_foreign_addresses:
                try:
                    sock.close()
                except OSError:
                    pass
                msg = (
                    "425 Rejected data connection from foreign address "
                    f"{addr[0]}:{addr[1]}."
                )
                self.cmd_channel.respond_w_warning(msg)

                if sys.stdout.isatty():
                    self.cmd_channel.log(
                        "you can use --permit-foreign-addresses CLI opt to"
                        " allow this connection"
                    )

                # do not close listening socket: it couldn't be client's blame
                return
            else:
                # site-to-site FTP allowed
                msg = (
                    "Established data connection with foreign address "
                    f"{addr[0]}:{addr[1]}."
                )
                self.cmd_channel.log(msg, logfun=logger.warning)
        # Immediately close the current channel (we accept only one
        # connection at time) and avoid running out of max connections
        # limit.
        self.close()
        # delegate such connection to DTP handler
        if self.cmd_channel.connected:
            handler = self.cmd_channel.dtp_handler(sock, self.cmd_channel)
            if handler.connected:
                self.cmd_channel.data_channel = handler
                self.cmd_channel._on_dtp_connection()

    def handle_timeout(self):
        if self.cmd_channel.connected:
            self.cmd_channel.respond(
                "421 Passive data channel timed out.", logfun=logger.info
            )
        self.close()

    def handle_error(self):
        """Called to handle any uncaught exceptions."""
        try:
            raise  # noqa: PLE0704
        except Exception:
            logger.error(traceback.format_exc())
        try:
            self.close()
        except Exception:
            logger.critical(traceback.format_exc())

    def close(self):
        debug("call: close()", inst=self)
        Acceptor.close(self)


class ActiveDTP(Connector):
    """Connects to remote client and dispatches the resulting connection
    to DTPHandler. Used for handling PORT command.

     - (int) timeout: the timeout for us to establish connection with
       the client's listening data socket.
    """

    timeout = 30

    def __init__(self, ip, port, cmd_channel):
        """Initialize the active data channel attempting to connect
        to remote data socket.

         - (str) ip: the remote IP address.
         - (int) port: the remote port.
         - (instance) cmd_channel: the command channel class instance.
        """
        Connector.__init__(self, ioloop=cmd_channel.ioloop)
        self.cmd_channel = cmd_channel
        self.log = cmd_channel.log
        self.log_exception = cmd_channel.log_exception
        self._idler = None
        if self.timeout:
            self._idler = self.ioloop.call_later(
                self.timeout, self.handle_timeout, _errback=self.handle_error
            )

        if ip.count(".") == 3:
            self._cmd = "PORT"
            self._normalized_addr = f"{ip}:{port}"
        else:
            self._cmd = "EPRT"
            self._normalized_addr = f"[{ip}]:{port}"

        source_ip = self.cmd_channel.socket.getsockname()[0]
        # dual stack IPv4/IPv6 support
        try:
            self.connect_af_unspecified((ip, port), (source_ip, 0))
        except (socket.gaierror, OSError):
            self.handle_close()

    def readable(self):
        return False

    def handle_connect(self):
        """Called when connection is established."""
        self.del_channel()
        if self._idler is not None and not self._idler.cancelled:
            self._idler.cancel()
        if not self.cmd_channel.connected:
            return self.close()
        # test_active_conn_error tests this condition
        err = self.socket.getsockopt(socket.SOL_SOCKET, socket.SO_ERROR)
        if err != 0:
            raise OSError(err)
        msg = "Active data connection established."
        self.cmd_channel.respond("200 " + msg)
        self.cmd_channel.log_cmd(self._cmd, self._normalized_addr, 200, msg)
        if not self.cmd_channel.connected:
            return self.close()
        # delegate such connection to DTP handler
        handler = self.cmd_channel.dtp_handler(self.socket, self.cmd_channel)
        self.cmd_channel.data_channel = handler
        self.cmd_channel._on_dtp_connection()

    def handle_timeout(self):
        if self.cmd_channel.connected:
            msg = "Active data channel timed out."
            self.cmd_channel.respond("421 " + msg, logfun=logger.info)
            self.cmd_channel.log_cmd(
                self._cmd, self._normalized_addr, 421, msg
            )
        self.close()

    def handle_close(self):
        # With the new IO loop, handle_close() gets called in case
        # the fd appears in the list of exceptional fds.
        # This means connect() failed.
        if not self._closed:
            self.close()
            if self.cmd_channel.connected:
                msg = "Can't connect to specified address."
                self.cmd_channel.respond("425 " + msg)
                self.cmd_channel.log_cmd(
                    self._cmd, self._normalized_addr, 425, msg
                )

    def handle_error(self):
        """Called to handle any uncaught exceptions."""
        try:
            raise  # noqa: PLE0704
        except (socket.gaierror, OSError):
            pass
        except Exception:
            self.log_exception(self)
        try:
            self.handle_close()
        except Exception:
            logger.critical(traceback.format_exc())

    def close(self):
        debug("call: close()", inst=self)
        if not self._closed:
            Connector.close(self)
            if self._idler is not None and not self._idler.cancelled:
                self._idler.cancel()
