#!/usr/bin/env python
# throttled_ftpd.py

"""ftpd supporting bandwidth throttling capabilities for data transfer.
"""

import os
import time
import asyncore

from pyftpdlib import ftpserver


class ThrottledDTPHandler(ftpserver.DTPHandler):
    """A DTPHandler which wraps sending and receiving in a data counter
    and sleep loop so that you burst to no more than x Kb/sec average.
    """

    # maximum number of bytes to transmit in a second (0 == no limit)
    read_limit = 0
    write_limit = 0

    # smaller the buffers, the less bursty and smoother the throughput
    ac_in_buffer_size = 2048
    ac_out_buffer_size  = 2048

    def __init__(self, sock_obj, cmd_channel):
        ftpserver.DTPHandler.__init__(self, sock_obj, cmd_channel)
        self.timenext = 0
        self.datacount = 0
        self.sleep = None

    # --- overridden asyncore methods

    def readable(self):
        return self.receive and not self.sleeping()

    def writable(self):
        return (self.producer_fifo or (not self.connected)) and not \
                self.sleeping()

    def recv(self, buffer_size):
        chunk = asyncore.dispatcher.recv(self, buffer_size)
        if self.read_limit:
            self.throttle_bandwidth(len(chunk), self.read_limit)
        return chunk

    def send(self, data):
        num_sent = asyncore.dispatcher.send(self, data)
        if self.write_limit:
            self.throttle_bandwidth(num_sent, self.write_limit)
        return num_sent

    # --- new methods

    def sleeping(self):
        """Return True if the channel is temporary blocked."""
        if self.sleep:
            if time.time() >= self.sleep:
                self.sleep = None
            else:
                return True
        return False

    def throttle_bandwidth(self, len_chunk, max_speed):
        """A method which counts data transmitted so that you burst to
        no more than x Kb/sec average.
        """
        self.datacount += len_chunk
        if self.datacount >= max_speed:
            self.datacount = 0
            now = time.time()
            sleepfor = self.timenext - now
            if sleepfor > 0:
                # we've passed bandwidth limits
                self.sleep = now + (sleepfor * 2)
            self.timenext = now + 1


if __name__ == '__main__':
    authorizer = ftpserver.DummyAuthorizer()
    authorizer.add_user('user', '12345', os.getcwd(), perm='elradfmw')

    # use the modified DTPHandler class; set a speed
    # limit for both sending and receiving
    dtp_handler = ThrottledDTPHandler
    dtp_handler.read_limit = 30072  # 30 Kb/sec (30 * 1024)
    dtp_handler.write_limit = 30072  # 30 Kb/sec (30 * 1024)

    ftp_handler = ftpserver.FTPHandler
    ftp_handler.authorizer = authorizer
    # have the ftp handler use the different dtp handler
    ftp_handler.dtp_handler = dtp_handler

    ftpd = ftpserver.FTPServer(('127.0.0.1', 21), ftp_handler)
    ftpd.serve_forever()
