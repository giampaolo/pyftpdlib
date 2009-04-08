#!/usr/bin/env python
# $Id$

"""ftpd supporting bandwidth throttling capabilities for data transfer.
"""

import os
import time

from pyftpdlib import ftpserver


class ThrottledDTPHandler(ftpserver.DTPHandler):
    """A DTPHandler which wraps sending and receiving in a data counter
    and temporarily sleeps the channel so that you burst to no more than
    x Kb/sec average.
    """

    # maximum number of bytes to transmit in a second (0 == no limit)
    read_limit = 0
    write_limit = 0

    # smaller the buffers, the less bursty and smoother the throughput
    ac_in_buffer_size = 4096
    ac_out_buffer_size = 4096

    def __init__(self, sock_obj, cmd_channel):
        ftpserver.DTPHandler.__init__(self, sock_obj, cmd_channel)
        self._timenext = 0
        self._datacount = 0
        self._sleeping = False
        self._throttler = None

    def readable(self):
        return not self._sleeping and ftpserver.DTPHandler.readable(self)

    def writable(self):
        return not self._sleeping and ftpserver.DTPHandler.writable(self)

    def recv(self, buffer_size):
        chunk = ftpserver.DTPHandler.recv(self, buffer_size)
        if self.read_limit:
            self.throttle_bandwidth(len(chunk), self.read_limit)
        return chunk

    def send(self, data):
        num_sent = ftpserver.DTPHandler.send(self, data)
        if self.write_limit:
            self.throttle_bandwidth(num_sent, self.write_limit)
        return num_sent

    def throttle_bandwidth(self, len_chunk, max_speed):
        """A method which counts data transmitted so that you burst to
        no more than x Kb/sec average.
        """
        self._datacount += len_chunk
        if self._datacount >= max_speed:
            self._datacount = 0
            now = time.time()
            sleepfor = self._timenext - now
            if sleepfor > 0:
                # we've passed bandwidth limits
                def unsleep():
                    self._sleeping = False
                self._sleeping = True
                self._throttler = ftpserver.CallLater(sleepfor * 2, unsleep)
            self._timenext = now + 1

    def close(self):
        if self._throttler is not None and not self._throttler.cancelled:
            self._throttler.cancel()
        ftpserver.DTPHandler.close(self)


if __name__ == '__main__':
    authorizer = ftpserver.DummyAuthorizer()
    authorizer.add_user('user', '12345', os.getcwd(), perm='elradfmw')
    authorizer.add_anonymous(os.getcwd())

    # use the modified DTPHandler class and set a speed limit for both
    # sending and receiving
    dtp_handler = ThrottledDTPHandler
    dtp_handler.read_limit = 30720  # 30 Kb/sec (30 * 1024)
    dtp_handler.write_limit = 30720  # 30 Kb/sec (30 * 1024)

    ftp_handler = ftpserver.FTPHandler
    ftp_handler.authorizer = authorizer
    # have the ftp handler use the different dtp handler
    ftp_handler.dtp_handler = dtp_handler

    ftpd = ftpserver.FTPServer(('', 21), ftp_handler)
    ftpd.serve_forever()
