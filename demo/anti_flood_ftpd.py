#!/usr/bin/env python
# $Id$

"""
A FTP server banning clients in case of command flood.

If client sends more than 300 requests per-second it will be
disconnected and won't be able to re-connect for 1 hour.
"""

from pyftpdlib.ftpserver import FTPHandler, FTPServer, DummyAuthorizer, CallLater


class AntiFloodHandler(FTPHandler):

    cmds_per_second = 300  # max number of cmds per second
    ban_for = 60 * 60      # 1 hour
    banned_ips = []

    def __init__(self, *args, **kwargs):
        super(AntiFloodHandler, self).__init__(*args, **kwargs)
        self.processed_cmds = 0
        self.pcmds_callback = CallLater(1, self.check_processed_cmds)

    def handle(self):
        # called when client connects.
        if self.remote_ip in self.banned_ips:
            self.respond('550 you are banned')
            self.close()
        else:
            super(AntiFloodHandler, self).handle()

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
        super(AntiFloodHandler, self).process_command(*args, **kwargs)

    def ban(self, ip):
        # ban ip and schedule next un-ban
        if ip not in self.banned_ips:
            self.log('banned IP %s for command flooding' % ip)
            CallLater(self.ban_for, self.unban, ip)
        self.respond('550 you are banned for %s seconds' % self.ban_for)
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
        super(AntiFloodHandler, self).close()
        if not self.pcmds_callback.cancelled:
            self.pcmds_callback.cancel()


def main():
    authorizer = DummyAuthorizer()
    authorizer.add_user('user', '12345', '.', perm='elradfmw')
    authorizer.add_anonymous('.')
    handler = AntiFloodHandler
    handler.authorizer = authorizer
    ftpd = FTPServer(('', 21), handler)
    ftpd.serve_forever(timeout=1)

if __name__ == '__main__':
    main()
