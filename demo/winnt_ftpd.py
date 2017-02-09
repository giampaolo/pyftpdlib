#!/usr/bin/env python

# Copyright (C) 2007 Giampaolo Rodola' <g.rodola@gmail.com>.
# Use of this source code is governed by MIT license that can be
# found in the LICENSE file.

"""A ftpd using local Windows NT account database to authenticate users
(users must already exist).

It also provides a mechanism to (temporarily) impersonate the system
users every time they are going to perform filesystem operations.
"""

from pyftpdlib.authorizers import WindowsAuthorizer
from pyftpdlib.handlers import FTPHandler
from pyftpdlib.servers import FTPServer


def main():
    authorizer = WindowsAuthorizer()
    # Use Guest user with empty password to handle anonymous sessions.
    # Guest user must be enabled first, empty password set and profile
    # directory specified.
    # authorizer = WindowsAuthorizer(anonymous_user="Guest",
    #                                anonymous_password="")
    handler = FTPHandler
    handler.authorizer = authorizer
    ftpd = FTPServer(('', 21), handler)
    ftpd.serve_forever()


if __name__ == "__main__":
    main()
