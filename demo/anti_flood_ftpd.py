#!/usr/bin/env python

# Copyright (C) 2007 Giampaolo Rodola' <g.rodola@gmail.com>.
# Use of this source code is governed by MIT license that can be
# found in the LICENSE file.

"""
A FTP server banning clients in case of commands flood.

If client sends more than 300 requests per-second it will be
disconnected and won't be able to re-connect for 1 hour.
"""

from pyftpdlib.authorizers import DummyAuthorizer
from pyftpdlib.handlers import FTPHandler
from pyftpdlib.servers import FTPServer


class AntiFloodHandler(FTPHandler):

    cmds_per_second = 300  # max number of cmds per second
    ban_for = 60 * 60      # 1 hour
    banned_ips = []

    def __init__(self, *args, **kwargs):
        FTPHandler.__init__(self, *args, **kwargs)
        self.processed_cmds = 0
        self.pcmds_callback = \
            self.ioloop.call_every(1, self.check_processed_cmds)

    def on_connect(self):
        # called when client connects.
        if self.remote_ip in self.banned_ips:
            self.respond('550 You are banned.')
            self.close_when_done()

    def check_processed_cmds(self):
        # called every second; checks for the number of commands
        # sent in the last second.
        if self.processed_cmds > self.cmds_per_second:
            self.ban(self.remote_ip)
        else:
            self.processed_cmds = 0

    def process_command(self, *args, **kwargs):
        # increase counter for every received command
        self.processed_cmds += 1
        FTPHandler.process_command(self, *args, **kwargs)

    def ban(self, ip):
        # ban ip and schedule next un-ban
        if ip not in self.banned_ips:
            self.log('banned IP %s for command flooding' % ip)
        self.respond('550 You are banned for %s seconds.' % self.ban_for)
        self.close()
        self.banned_ips.append(ip)

    def unban(self, ip):
        # unban ip
        try:
            self.banned_ips.remove(ip)
        except ValueError:
            pass
        else:
            self.log('unbanning IP %s' % ip)

    def close(self):
        FTPHandler.close(self)
        if not self.pcmds_callback.cancelled:
            self.pcmds_callback.cancel()


def main():
    authorizer = DummyAuthorizer()
    authorizer.add_user('user', '12345', '.', perm='elradfmwMT')
    authorizer.add_anonymous('.')
    handler = AntiFloodHandler
    handler.authorizer = authorizer
    server = FTPServer(('', 2121), handler)
    server.serve_forever(timeout=1)


if __name__ == '__main__':
    main()
