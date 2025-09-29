# Copyright (C) 2007 Giampaolo Rodola' <g.rodola@gmail.com>.
# Use of this source code is governed by MIT license that can be
# found in the LICENSE file.

import os

from OpenSSL import SSL

from pyftpdlib.handlers.ftp.control import FTPHandler

from .data import TLS_DTPHandler
from .ssl import SSLConnectionMixin

__all__ = ["TLS_FTPHandler"]


class TLS_FTPHandler(SSLConnectionMixin, FTPHandler):
    """A FTPHandler subclass supporting TLS/SSL.
    Implements AUTH, PBSZ and PROT commands (RFC-2228 and RFC-4217).

    Configurable attributes:

     - (bool) tls_control_required:
        When True requires SSL/TLS to be established on the control
        channel, before logging in.  This means the user will have
        to issue AUTH before USER/PASS (default False).

     - (bool) tls_data_required:
        When True requires SSL/TLS to be established on the data
        channel.  This means the user will have to issue PROT
        before PASV or PORT (default False).

    SSL-specific options:

     - (string) certfile:
        the path to the file which contains a certificate to be
        used to identify the local side of the connection.
        This  must always be specified, unless context is provided
        instead.

     - (string) keyfile:
        the path to the file containing the private RSA key;
        can be omitted if certfile already contains the private
        key (defaults: None).

     - (int) ssl_protocol:
        the desired SSL protocol version to use. This defaults to
        TLS_SERVER_METHOD, which includes TLSv1, TLSv1.1, TLSv1.2
        and TLSv1.3. The actual protocol version used will be
        negotiated to the highest version mutually supported by the
        client and the server.

     - (int) ssl_options:
        specific OpenSSL options. These default to:
        SSL.OP_NO_SSLv2 | SSL.OP_NO_SSLv3 | SSL.OP_NO_COMPRESSION
        ...which are all considered insecure features.
        Can be set to None in order to improve compatibility with
        older (insecure) FTP clients.

      - (instance) ssl_context:
        a SSL Context object previously configured; if specified
        all other parameters will be ignored.
        (default None).
    """

    # configurable attributes
    tls_control_required = False
    tls_data_required = False
    certfile = None
    keyfile = None
    # Includes: SSLv3, TLSv1, TLSv1.1, TLSv1.2, TLSv1.3
    ssl_protocol = SSL.TLS_SERVER_METHOD
    # - SSLv2 is easily broken and is considered harmful and dangerous
    # - SSLv3 has several problems and is now dangerous
    # - Disable compression to prevent CRIME attacks for OpenSSL 1.0+
    #   (see https://github.com/shazow/urllib3/pull/309)
    ssl_options = SSL.OP_NO_SSLv2 | SSL.OP_NO_SSLv3
    if hasattr(SSL, "OP_NO_COMPRESSION"):
        ssl_options |= SSL.OP_NO_COMPRESSION
    ssl_context = None

    # overridden attributes
    dtp_handler = TLS_DTPHandler
    proto_cmds = FTPHandler.proto_cmds.copy()
    proto_cmds.update({
        "AUTH": dict(
            perm=None,
            auth=False,
            arg=True,
            help="Syntax: AUTH <SP> TLS|SSL (set up secure control channel).",
        ),
        "PBSZ": dict(
            perm=None,
            auth=False,
            arg=True,
            help="Syntax: PBSZ <SP> 0 (negotiate TLS buffer).",
        ),
        "PROT": dict(
            perm=None,
            auth=False,
            arg=True,
            help="Syntax: PROT <SP> [C|P] (set up un/secure data channel).",
        ),
    })

    def __init__(self, conn, server, ioloop=None):
        super().__init__(conn, server, ioloop)
        if not self.connected:
            return
        self._extra_feats = ["AUTH TLS", "AUTH SSL", "PBSZ", "PROT"]
        self._pbsz = False
        self._prot = False
        self.ssl_context = self.get_ssl_context()

    def __repr__(self):
        return FTPHandler.__repr__(self)

    @classmethod
    def get_ssl_context(cls):
        if cls.ssl_context is None:
            if cls.certfile is None:
                raise ValueError("at least certfile must be specified")

            cls.ssl_context = SSL.Context(cls.ssl_protocol)

            if not cls.keyfile:
                cls.keyfile = cls.certfile
            for file in (cls.certfile, cls.keyfile):
                if not os.path.isfile(cls.certfile):
                    msg = f"{file!r} does not exist"
                    raise FileNotFoundError(msg)

            cls.ssl_context.use_certificate_chain_file(cls.certfile)
            cls.ssl_context.use_privatekey_file(cls.keyfile)

            if cls.ssl_options:
                cls.ssl_context.set_options(cls.ssl_options)

        return cls.ssl_context

    # --- overridden methods

    def flush_account(self):
        FTPHandler.flush_account(self)
        self._pbsz = False
        self._prot = False

    def process_command(self, cmd, *args, **kwargs):
        if cmd in ("USER", "PASS"):
            if self.tls_control_required and not self._ssl_established:
                msg = "SSL/TLS required on the control channel."
                self.respond("550 " + msg)
                self.log_cmd(cmd, args[0], 550, msg)
                return
        elif cmd in ("PASV", "EPSV", "PORT", "EPRT"):
            if self.tls_data_required and not self._prot:
                msg = "SSL/TLS required on the data channel."
                self.respond("550 " + msg)
                self.log_cmd(cmd, args[0], 550, msg)
                return
        FTPHandler.process_command(self, cmd, *args, **kwargs)

    def close(self):
        SSLConnectionMixin.close(self)
        FTPHandler.close(self)

    # --- new methods

    def handle_failed_ssl_handshake(self):
        # TLS/SSL handshake failure, probably client's fault which
        # used a SSL version different from server's.
        # We can't rely on the control connection anymore so we just
        # disconnect the client without sending any response.
        self.log("SSL handshake failed.")
        self.close()

    def ftp_AUTH(self, line):
        """Set up secure control channel."""
        arg = line.upper()
        if isinstance(self.socket, SSL.Connection):
            self.respond("503 Already using TLS.")
        elif arg in ("TLS", "TLS-C", "SSL", "TLS-P"):
            # From RFC-4217: "As the SSL/TLS protocols self-negotiate
            # their levels, there is no need to distinguish between SSL
            # and TLS in the application layer".
            self.respond(f"234 AUTH {arg} successful.")
            self.secure_connection(self.ssl_context)
        else:
            self.respond("502 Unrecognized encryption type (use TLS or SSL).")

    def ftp_PBSZ(self, line):
        """Negotiate size of buffer for secure data transfer.
        For TLS/SSL the only valid value for the parameter is '0'.
        Any other value is accepted but ignored.
        """
        if not isinstance(self.socket, SSL.Connection):
            self.respond(
                "503 PBSZ not allowed on insecure control connection."
            )
        else:
            self.respond("200 PBSZ=0 successful.")
            self._pbsz = True

    def ftp_PROT(self, line):
        """Setup un/secure data channel."""
        arg = line.upper()
        if not isinstance(self.socket, SSL.Connection):
            self.respond(
                "503 PROT not allowed on insecure control connection."
            )
        elif not self._pbsz:
            self.respond("503 You must issue the PBSZ command prior to PROT.")
        elif arg == "C":
            self.respond("200 Protection set to Clear")
            self._prot = False
        elif arg == "P":
            self.respond("200 Protection set to Private")
            self._prot = True
        elif arg in ("S", "E"):
            self.respond(f"521 PROT {arg} unsupported (use C or P).")
        else:
            self.respond("502 Unrecognized PROT type (use C or P).")
