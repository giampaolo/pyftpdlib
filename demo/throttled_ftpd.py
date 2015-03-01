#!/usr/bin/env python

#  pyftpdlib is released under the MIT license, reproduced below:
#  ======================================================================
#  Copyright (C) 2007-2014 Giampaolo Rodola' <g.rodola@gmail.com>
#
#                         All Rights Reserved
#
# Permission is hereby granted, free of charge, to any person
# obtaining a copy of this software and associated documentation
# files (the "Software"), to deal in the Software without
# restriction, including without limitation the rights to use,
# copy, modify, merge, publish, distribute, sublicense, and/or sell
# copies of the Software, and to permit persons to whom the
# Software is furnished to do so, subject to the following
# conditions:
#
# The above copyright notice and this permission notice shall be
# included in all copies or substantial portions of the Software.
#
# THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND,
# EXPRESS OR IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES
# OF MERCHANTABILITY, FITNESS FOR A PARTICULAR PURPOSE AND
# NONINFRINGEMENT. IN NO EVENT SHALL THE AUTHORS OR COPYRIGHT
# HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER LIABILITY,
# WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING
# FROM, OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR
# OTHER DEALINGS IN THE SOFTWARE.
#
#  ======================================================================

"""An FTP server which uses the ThrottledDTPHandler class for limiting the
speed of downloads and uploads.
"""

import os

from pyftpdlib.authorizers import DummyAuthorizer
from pyftpdlib.handlers import FTPHandler, ThrottledDTPHandler
from pyftpdlib.servers import FTPServer

import pyftpdlib.log
import logging


def main():
    # be more verbose while logging
    pyftpdlib.log.LEVEL = logging.DEBUG

    authorizer = DummyAuthorizer()
    authorizer.add_user('user', '12345', os.getcwd(), perm='elradfmw')
    authorizer.add_anonymous(os.getcwd())

    dtp_handler = ThrottledDTPHandler
    dtp_handler.read_limit = 1024 * 1 * 1024  # inbound 1 Mb/sec (1 * 1024K)
    dtp_handler.write_limit = 1024 * 1 * 1024  # outbound 1 Mb/sec (1 * 1024K)
    dtp_handler.auto_sized_buffers = False

    # Changing log line prefix
    dtp_handler.log_prefix = '[%(username)s]@%(remote_ip)s'

    ftp_handler = FTPHandler
    ftp_handler.authorizer = authorizer
    # have the ftp handler use the alternative dtp handler class
    ftp_handler.dtp_handler = dtp_handler

    # set the same limit for passive ftp as for active
    ftp_handler.passive_dtp.ac_in_buffer_size = dtp_handler.read_limit
    ftp_handler.passive_dtp.ac_out_buffer_size = dtp_handler.write_limit

    server = FTPServer(('::', 2121), ftp_handler)

    # start ftp server and handle CTL C termination gracefully
    try:
        server.serve_forever()
    finally:
        server.close_all()

if __name__ == '__main__':
    main()
