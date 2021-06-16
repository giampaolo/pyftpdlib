# http://www.haproxy.org/download/1.8/doc/proxy-protocol.txt

import ipaddress
import socket
import time

from .log import logger


class PPHeaderError(Exception):
    """Exception raised when the header is invalid in some way."""


class PPTimeoutError(Exception):
    """Exception raised when we don't receive a complete header
    within the timeout delay.
    """


class PPProxyError(Exception):
    """Exception raised when the connecting proxy is not trusted."""


class ProxyProtocol():
    """Base class used as an interface for version related classes.
    It can be used to guess the PROXY protocol version used by a proxy
    and return the appropriate ProxyProcotol instance. This class should
    not be instanciated and doing so will lead to a NotImplementedError
    exception. However, it may be useful to vaidate the trustworthiness
    of the connected proxy, without consuming the data in the sockets buffer.

    The user can configure the behaviour of the class by setting the
    public properties as in the examples below.

    ProxyProcotol.trusted_networks = ['0.0.0.0/0', '::/0']  # Trust everybody
    ProxyProcotol.trusted_networks = ['172.18.0.2/32']  # Trust only this IP

    Below is a list of the defined properties:

    - (instance) _socket: socket.socket instance to read the header from.
    - (str) _header: full header as read from the socket.
    - (int) _version: version of the protocol used by the classe.
    - (int) _inet_af: address family used by the socket (e.g. socket.AF_INET).
    - (int) _inet_proto: INET protocol used by the socket
        (e.g. socket.SOCK_STREAM).
    - (str) _remote_ip: IP of the source behind the proxy.
    - (int) _remote_port: port on the source behind the proxy.
    - (str) _local_ip: IP of the destination (should be this host IP).
    - (int) _local_port: port on destination.
    - (str) _proxy_ip: IP of the connected proxy.
    - (bool) trusted: is this proxy connection trusted?
    - (list) trusted_networks: list of str representing the networks you
        want to trust the IPs from. Use a /32 mask for a unique IP.
    - (bool) allow_untrusted: do we accept to handle connections from
        untrusted proxies?
    """

    # Private attributes
    _socket = None
    _header = None
    _version = None
    _inet_af = None
    _inet_proto = None
    _remote_ip = None
    _remote_port = None
    _local_ip = None
    _local_port = None
    _proxy_ip = None

    # Public attributes
    trusted = False
    trusted_networks = None
    allow_untrusted = False

    @property
    def header(self):
        return self._header

    @property
    def remote_ip(self):
        return self._remote_ip

    @property
    def local_ip(self):
        return self._local_ip

    @property
    def proxy_ip(self):
        return self._proxy_ip

    @property
    def remote_port(self):
        return self._remote_port

    @property
    def local_port(self):
        return self._local_port

    @property
    def version(self):
        return self._version

    @property
    def inet_af(self):
        return self._inet_af

    @property
    def inet_proto(self):
        return self._inet_proto

    def __init__(self, sock, header=b'', timeout=5.0):
        """Here we handle the complete initialization and population of the
        instance. Child classes should not define there own __init__ method
        or at least call this one first as we do the trust check and the
        retrieving and parsing of the header.

        List of the parameters:

        - (instance) sock: socket.socket instance to read the header from.
        - (str) header: part of the header that may have already been read.
            Used mainly in conjuction with the create() method.
        - (float) timeout: timeout used socket reading.
        """
        self._socket = sock
        self._header = header

        # Verify the connected proxy IP trust
        ip = self._socket.getpeername()[0]
        self.trusted = self.is_trusted(ip)
        if self.trusted:
            logger.debug("proxy: connection from trusted proxy '{}'"
                         .format(ip))
            self._proxy_ip = ip
        else:
            logger.debug("proxy: connection from untrusted proxy '{}'"
                         .format(ip))
            if not self.allow_untrusted:
                raise PPProxyError("untrusted proxies not allowed")
            else:
                logger.debug("proxy: untrusted proxies allowed")

        # Header population and parsing
        start = time.time()
        try:
            self._get_header(timeout)
        except PPTimeoutError:
            elapsed = time.time() - start
            raise PPTimeoutError("did not received a complete header in {} "
                                 "seconds".format(elapsed))
        logger.debug("proxy: header => {}".format(repr(self._header)))
        self._parse_header()

    @classmethod
    def _socket_read(cls, sock, size, timeout, stop_on_crlf=False,
                     partial=False):
        """Provide an unified way to read the socket buffer.

        List of the parameters:

        - (instance) sock: socket.socket instance to read the header from.
        - (int) size: number of bytes to read from the socket.
        - (float) timeout: timeout used socket reading.
        - (bool) stop_on_crlf: should we stop at the end of the line?
        - (bool) partial: if 'size' bytes haven't been read at the end of
            the timeout, should we return the partial result?

        Returns the bytes read or raises a socket.timeout exception.
        """
        if not sock:
            return None

        # Save socket's original blocking state
        orig_timeout = sock.gettimeout()
        sock.settimeout(timeout)

        res = b''
        try:
            buff = bytearray(size)
            buff_view = memoryview(buff)

            while len(res) < size:
                if stop_on_crlf:
                    # Read only what we need to align on a newline
                    read_len = 1 if res.endswith(b'\r') else 2
                else:
                    # Try to read all that is missing at once
                    read_len = size - len(res)

                pos = buff_view[len(res):]
                nb_bytes = sock.recv_into(pos, read_len)
                res = buff_view[0:len(res) + nb_bytes].tobytes()

                if stop_on_crlf and res.endswith(b'\r\n'):
                    break
        except socket.timeout as e:
            if not partial:
                raise e
        finally:
            # Reset the socket's blocking state
            sock.settimeout(orig_timeout)

        return res

    @classmethod
    def is_trusted(cls, ip):
        """
        - (str) ip: IP to check against the trusted networks.
        """
        if not ip or not cls.trusted_networks:
            return False
        ip = ipaddress.ip_address(ip)
        for network in cls.trusted_networks:
            if ip in ipaddress.ip_network(network):
                return True
        return False

    @classmethod
    def is_valid_ip(cls, ip: str, inet_af=socket.AF_INET):
        """
        - (str) ip: IP to validate.
        - (int) inet_af: address family to use.
        """
        try:
            socket.inet_pton(inet_af, ip)
        except OSError:
            return False
        return True

    @classmethod
    def is_valid_port(cls, port):
        """
        - (int) port: port to validate.
        """
        port = int(port)
        if 1 <= port <= 65535:
            return True
        return False

    @classmethod
    def create(cls, sock, timeout=5.0):
        """Guess which version of the PROXY protocol is used.

        List of the parameters:

        - (instance) sock: socket.socket instance to read the header from.
        - (float) timeout: timeout used socket reading.

        Return an instance of the matching version class or raise a
        PPTimeoutError exception if we reached the timeout.
        """
        start = time.time()
        try:
            # Version 1 needs 8 bytes for discovery
            header = cls._socket_read(sock, 8, timeout)
            if ProxyProtocolV1.check_protocol(header):
                logger.debug("using PROXY protocol v1")
                return ProxyProtocolV1(sock, header, timeout=timeout)

            # Version 2 needs 16 bytes for discovery
            header += cls._socket_read(sock, 8, timeout)
            if ProxyProtocolV2.check_protocol(header):
                return ProxyProtocolV2(sock, header, timeout=timeout)

            raise PPHeaderError('Invalid PROXY protocol signature')
        except socket.timeout:
            elapsed = time.time() - start
            raise PPTimeoutError("did not received a complete header in {} "
                                 "seconds".format(elapsed))

    @classmethod
    def check_protocol(cls, header):
        """Must return True or False depending on whether the header
        matches the protocol version or not. A PPHeaderError exception
        must be raised if the header is to short for the check to happen.

        - (str) header: header to check for version compatibility.
        """
        raise NotImplementedError("check_header() must be overridden")

    def _get_header(self, timeout):
        """Populate the self._header attribute with what is read from
        the socket.  A PPTimeoutError or PPHeaderError exception may
        be raised.

        - (float) timeout: timeout used socket reading.
        """
        raise NotImplementedError("_get_header() must be overridden")

    def _parse_header(self):
        """Populate the instance's attributes by parsing the header.
        A PPHeaderError exception may be raised if something in the
        header is invalid.
        """
        raise NotImplementedError("_parse_header() must be overridden")


class ProxyProtocolV1(ProxyProtocol):
    """Class that handle version 1 of the PROXY protocol.

    Here are the attributes specific to this class:

    - (list) _inet_protos: list of the allowed INET protocols in the v1 header
    """

    # Private attributes
    _inet_protos = [b"TCP4", b"TCP6", b"UNKNOWN"]

    # Define the defaults
    _version = 1
    _inet_proto = socket.SOCK_STREAM

    @classmethod
    def check_protocol(cls, header):
        if len(header) < 6:
            raise PPHeaderError("v1 header should be at least 6 bytes long")
        return header.startswith(b'PROXY ')

    def socket_read(self, size, timeout):
        """Wrapper to define the defaults for this version of the protocol"""
        return ProxyProtocolV1._socket_read(self._socket, size, timeout,
                                            stop_on_crlf=True)

    def _get_header(self, timeout):
        try:
            # Max header size for v1 is 107
            read_len = 107 - len(self._header)
            self._header += self.socket_read(read_len, timeout)

            if not ProxyProtocolV1.check_protocol(self._header):
                raise PPHeaderError("not a valid PROXY protocol v1 header")
        except socket.timeout:
            raise PPTimeoutError()

    def _parse_header(self):
        if not self._header:
            raise PPHeaderError("Header cannot be empty")

        cls = ProxyProtocolV1
        parts = self._header.split()

        if len(parts) >= 2:
            inet_proto = parts[1]
            if inet_proto not in cls._inet_protos:
                raise PPHeaderError("invalid PROXY v1 inet_proto ({})"
                                    .format(inet_proto))
            if inet_proto == b"UNKNOWN":
                return  # In this case we skip the rest of the header

            if inet_proto.endswith(b"4"):
                self._inet_af = socket.AF_INET
            elif inet_proto.endswith(b"6"):
                self._inet_af = socket.AF_INET6
            else:
                raise PPHeaderError("unable to determine address family")
        else:
            raise PPHeaderError("no INET protocol")

        if len(parts) != 6:
            raise PPHeaderError("missing IP or port")

        self._remote_ip = parts[2].decode()
        if not cls.is_valid_ip(self._remote_ip, self._inet_af):
            raise PPHeaderError("not a valid IP ({})".format(parts[2]))

        self._local_ip = parts[3].decode()
        if not cls.is_valid_ip(self._local_ip, self._inet_af):
            raise PPHeaderError("not a valid IP ({})".format(parts[3]))

        self._remote_port = parts[4].decode()
        if not cls.is_valid_port(self._remote_port):
            raise PPHeaderError("bad port number ({})".format(parts[4]))

        self._local_port = parts[5].decode()
        if not cls.is_valid_port(self._local_port):
            raise PPHeaderError("bad port number ({})".format(parts[5]))


class ProxyProtocolV2(ProxyProtocol):
    """Class that handle version 2 of the PROXY protocol.

    Here are the attributes specific to this class:

    - (str) _command: command used by the header
    - (dict) _commands: valid commands used by the v2 protocol
    - (dict) _address_families: valid address families used by the v2 protocol
    - (dict) _inet_protos: valid INET protocols used by the v2 protocol
    """

    # Private attributes
    _command = None
    _commands = {
        0x00: "LOCAL",
        0x01: "PROXY",
    }
    _address_families = {
        0x01: socket.AF_INET,
        0x02: socket.AF_INET6,
        0x03: socket.AF_UNIX,
    }
    _inet_protos = {
        0x01: socket.SOCK_STREAM,
        0x02: socket.SOCK_DGRAM,
    }

    # Define the defaults
    _version = 2

    @classmethod
    def check_protocol(cls, header):
        if len(header) < 16:
            raise PPHeaderError("header should be at least 16 bytes long")
        if header[0:12] != b'\x0D\x0A\x0D\x0A\x00\x0D\x0A\x51\x55\x49\x54\x0A':
            return False
        if ord(header[12]) & 0xF0 != 0x20:
            return False
        return True

    def socket_read(self, size, timeout):
        """Wrapper to define the defaults for this version of the protocol"""
        return ProxyProtocolV2._socket_read(self._socket, size, timeout,
                                            stop_on_crlf=False)

    def _get_header(self, timeout):
        try:
            # Version 2 header is always 16 bytes long
            if len(self._header) < 16:
                read_len = 16 - len(self._header)
                self._header += self.socket_read(read_len, timeout)

            if not ProxyProtocolV2.check_protocol(self._header):
                raise PPHeaderError("not a valid PROXY protocol v2 header")

            # Bytes 15 and 16 specify the size, in bytes, of the payload
            read_len = (ord(self._header[14]) << 8) | ord(self._header[15])
            if read_len:
                self._header += self.socket_read(read_len, timeout)
        except socket.timeout:
            raise PPTimeoutError()

    def _parse_header(self):
        if not self._header:
            raise PPHeaderError("Header cannot be empty")

        cls = ProxyProtocolV2

        command = ord(self._header[12]) & 0x0F
        if command in self._commands:
            self._command = self._commands[command]
        else:
            raise PPHeaderError("invalid PROXY v2 command ({})"
                                .format(command))

        inet_af = ord(self._header[13]) >> 4
        if inet_af in cls._address_families:
            self._inet_af = cls._address_families[inet_af]
        else:
            raise PPHeaderError("invalid PROXY v2 address family ({})"
                                .format(inet_af))

        inet_proto = ord(self._header[13]) & 0x0F
        if inet_proto in cls._inet_protos:
            self._inet_proto = cls._inet_protos[inet_proto]
        else:
            raise PPHeaderError("invalid PROXY v2 inet_proto ({})"
                                .format(inet_proto))

        if self._command == "LOCAL":
            logger.debug("discard protocol data for local connection")
            return

        # Here starts the parsing of the payload according to
        # the address family.
        h = self._header
        if self._inet_af == socket.AF_INET:
            self._remote_ip = socket.inet_ntop(socket.AF_INET, h[16:20])
            self._local_ip = socket.inet_ntop(socket.AF_INET, h[20:24])
            self._remote_port = (ord(h[24]) << 8) | ord(h[25])
            self._local_port = (ord(h[26]) << 8) | ord(h[27])
        elif self._inet_af == socket.AF_INET6:
            self._remote_ip = socket.inet_ntop(socket.AF_INET6, h[16:32])
            self._local_ip = socket.inet_ntop(socket.AF_INET6, h[32:48])
            self._remote_port = (ord(h[48]) << 8) | ord(h[49])
            self._local_port = (ord(h[50]) << 8) | ord(h[51])
        elif self._inet_af == socket.AF_UNIX:
            self._remote_ip = h[16:124]
            self._local_ip = h[124:232]
        else:
            raise PPHeaderError("address family not implemented ({})"
                                .format(self._inet_af))

        if self._remote_port and not cls.is_valid_port(self._remote_port):
            raise PPHeaderError("bad port number ({})"
                                .format(self._remote_port))
        if self._local_port and not cls.is_valid_port(self._local_port):
            raise PPHeaderError("bad port number ({})"
                                .format(self._local_port))
