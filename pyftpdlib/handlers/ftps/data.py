# Copyright (C) 2007 Giampaolo Rodola' <g.rodola@gmail.com>.
# Use of this source code is governed by MIT license that can be
# found in the LICENSE file.


from pyftpdlib.handlers.ftp.data import DTPHandler
from pyftpdlib.utils import is_ssl_sock

from .ssl import SSLConnectionMixin

__all__ = ["TLS_DTPHandler"]


class TLS_DTPHandler(SSLConnectionMixin, DTPHandler):
    """A DTPHandler subclass supporting TLS/SSL."""

    def __init__(self, sock, cmd_channel):
        super().__init__(sock, cmd_channel)
        if self.cmd_channel._prot:
            self.secure_connection(self.cmd_channel.ssl_context)

    def __repr__(self):
        return DTPHandler.__repr__(self)

    def use_sendfile(self):
        if is_ssl_sock(self.socket):
            return False
        else:
            return super().use_sendfile()

    def handle_failed_ssl_handshake(self):
        # TLS/SSL handshake failure, probably client's fault which
        # used a SSL version different from server's.
        # RFC-4217, chapter 10.2 expects us to return 522 over the
        # command channel.
        self.cmd_channel.respond("522 SSL handshake failed.")
        self.cmd_channel.log_cmd("PROT", "P", 522, "SSL handshake failed.")
        self.close()
