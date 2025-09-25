#!/usr/bin/env python3

# Copyright (C) 2007 Giampaolo Rodola' <g.rodola@gmail.com>.
# Use of this source code is governed by MIT license that can be
# found in the LICENSE file.

"""
A basic ftpd storing passwords as hash digests (platform independent).
"""

import hashlib
import os

from pyftpdlib.authorizers import AuthenticationFailed
from pyftpdlib.authorizers import DummyAuthorizer
from pyftpdlib.handlers import FTPHandler
from pyftpdlib.servers import FTPServer


class DummyMD5Authorizer(DummyAuthorizer):

    def validate_authentication(self, username, password, handler):
        hash_ = hashlib.md5(password.encode("latin1")).hexdigest()
        try:
            if self.user_table[username]["pwd"] != hash_:
                raise KeyError
        except KeyError:
            raise AuthenticationFailed from None


def main():
    # get a hash digest from a clear-text password
    password = "12345"
    hash_ = hashlib.md5(password.encode("latin1")).hexdigest()
    authorizer = DummyMD5Authorizer()
    authorizer.add_user("user", hash_, os.getcwd(), perm="elradfmwMT")
    authorizer.add_anonymous(os.getcwd())
    handler = FTPHandler
    handler.authorizer = authorizer
    server = FTPServer(("", 2121), handler)
    server.serve_forever()


if __name__ == "__main__":
    main()
