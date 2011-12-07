#!/usr/bin/env python
# $Id$

"""A basic unix daemon using the python-daemon library.

Author: Michele Petrazzo, Italy. mail: michele.petrazzo <at> gmail.com
Author: Ben Timby, US. mail: btimby <at> gmail.com
"""

from __future__ import with_statement

import os
import errno
import sys
import time
import optparse
import signal
import basic_ftpd

# http://pypi.python.org/pypi/python-daemon
import daemon
import daemon.pidfile


DAEMON_NAME = "pyftplib"
DAEMON_PID_FILE = "/var/run/%s.pid"% DAEMON_NAME


def kill(pidfile):
    if os.path.exists(pidfile):
        pid = int(open(pidfile).read().strip())
        sig = signal.SIGTERM
        i = 0
        while True:
            try:
                os.kill(pid, sig)
            except OSError, e:
                if e.errno == errno.ESRCH:
                    return
                raise
            i += 1
            if i >= 2:
                sig = signal.SIGKILL
            if i >= 50:
                raise SystemExit("could not kill the daemon")
            time.sleep(0.1)


def daemonize(pidfile=None, redirect=None, workdir=os.getcwd(), umask=0):
    """A wrapper around pytho-daemonize context manager."""
    ctx = daemon.DaemonContext(working_directory=workdir, umask=umask)
    if pidfile:
        ctx.pidfile = daemon.pidfile.TimeoutPIDLockFile(pidfile)
    if redirect:
        ctx.stdout = ctx.stderr = file(redirect, 'wb')
    with ctx:
        basic_ftpd.main()


def main():
    usage = "python %s -d|-f|-k [-o outputfile]" %sys.argv[0]
    parser = optparse.OptionParser(usage=usage)
    parser.add_option('-d', '--daemon', dest='daemon',
                      default=False, action='store_true',
                      help='create a pyftplib daemon that runs in background')
    parser.add_option('-f', '--foreground', dest='foreground',
                      default=False, action='store_true',
                      help='interactive mode, do the work in foreground')
    parser.add_option('-k', '--kill', dest='kill',
                      default=False, action='store_true',
                      help='check for existance of a pyftplib daemon and kill it')
    parser.add_option('-o', '--outputfile', dest='outputfile',
                      help='save stdout to a file')
    parser.add_option('-p', '--pidfile', dest='pidfile', default=DAEMON_PID_FILE,
                      help='File to store/retreive daemon pid.')
    options, args = parser.parse_args()

    # option control
    num_opt = len(filter(lambda x: getattr(options, x), ("daemon", "foreground",
                                                         "kill")))
    if num_opt == 0:
        parser.error("pass me at least one option")
    elif num_opt > 1:
        parser.error("options are mutually exclusive, use one at a time")

    if options.kill:
        kill(options.pidfile)
    elif options.daemon:
        daemonize(options.pidfile, options.outputfile)
    else:
        basic_ftpd.main()


if __name__ == '__main__':
    main()
