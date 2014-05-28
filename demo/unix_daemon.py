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

"""A basic unix daemon using the python-daemon library:
http://pypi.python.org/pypi/python-daemon

Example usages:

 $ python unix_daemon.py start
 $ python unix_daemon.py stop
 $ python unix_daemon.py status
 $ python unix_daemon.py  # foreground (no daemon)
 $ python unix_daemon.py --logfile /var/log/ftpd.log start
 $ python unix_daemon.py --pidfile /var/run/ftpd.pid start

This is just a proof of concept which demonstrates how to daemonize
the FTP server.
You might want to use this as an example and provide the necessary
customizations.

Parts you might want to customize are:
 - UMASK, WORKDIR, HOST, PORT constants
 - get_server() function (to define users and customize FTP handler)

Authors:
 - Ben Timby - btimby <at> gmail.com
 - Giampaolo Rodola' - g.rodola <at> gmail.com
"""

from __future__ import with_statement

import os
import errno
import sys
import time
import optparse
import signal
import atexit

from pyftpdlib.handlers import FTPHandler
from pyftpdlib.servers import FTPServer
from pyftpdlib.authorizers import UnixAuthorizer
from pyftpdlib.filesystems import UnixFilesystem


# overridable options
HOST = ""
PORT = 21
PID_FILE = "/var/run/pyftpdlib.pid"
LOG_FILE = "/var/log/pyftpdlib.log"
WORKDIR = os.getcwd()
UMASK = 0


def print_(s):
    sys.stdout.write(s + '\n')
    sys.stdout.flush()


def pid_exists(pid):
    """Return True if a process with the given PID is currently running."""
    try:
        os.kill(pid, 0)
    except OSError:
        err = sys.exc_info()[1]
        return err.errno == errno.EPERM
    else:
        return True


def get_pid():
    """Return the PID saved in the pid file if possible, else None."""
    try:
        with open(PID_FILE) as f:
            return int(f.read().strip())
    except IOError:
        err = sys.exc_info()[1]
        if err.errno != errno.ENOENT:
            raise


def stop():
    """Keep attempting to stop the daemon for 5 seconds, first using
    SIGTERM, then using SIGKILL.
    """
    pid = get_pid()
    if not pid or not pid_exists(pid):
        sys.exit("daemon not running")
    sig = signal.SIGTERM
    i = 0
    while True:
        sys.stdout.write('.')
        sys.stdout.flush()
        try:
            os.kill(pid, sig)
        except OSError:
            e = sys.exc_info()[1]
            if e.errno == errno.ESRCH:
                print_("\nstopped (pid %s)" % pid)
                return
            else:
                raise
        i += 1
        if i == 25:
            sig = signal.SIGKILL
        elif i == 50:
            sys.exit("\ncould not kill daemon (pid %s)" % pid)
        time.sleep(0.1)


def status():
    """Print daemon status and exit."""
    pid = get_pid()
    if not pid or not pid_exists(pid):
        print_("daemon not running")
    else:
        print_("daemon running with pid %s" % pid)
    sys.exit(0)


def get_server():
    """Return a pre-configured FTP server instance."""
    handler = FTPHandler
    handler.authorizer = UnixAuthorizer()
    handler.abstracted_fs = UnixFilesystem
    server = FTPServer((HOST, PORT), handler)
    return server


def daemonize():
    """A wrapper around python-daemonize context manager."""
    def _daemonize():
        pid = os.fork()
        if pid > 0:
            # exit first parent
            sys.exit(0)

        # decouple from parent environment
        os.chdir(WORKDIR)
        os.setsid()
        os.umask(0)

        # do second fork
        pid = os.fork()
        if pid > 0:
            # exit from second parent
            sys.exit(0)

        # redirect standard file descriptors
        sys.stdout.flush()
        sys.stderr.flush()
        si = open(LOG_FILE, 'r')
        so = open(LOG_FILE, 'a+')
        se = open(LOG_FILE, 'a+', 0)
        os.dup2(si.fileno(), sys.stdin.fileno())
        os.dup2(so.fileno(), sys.stdout.fileno())
        os.dup2(se.fileno(), sys.stderr.fileno())

        # write pidfile
        pid = str(os.getpid())
        f = open(PID_FILE, 'w')
        f.write("%s\n" % pid)
        f.close()
        atexit.register(lambda: os.remove(PID_FILE))

    pid = get_pid()
    if pid and pid_exists(pid):
        sys.exit('daemon already running (pid %s)' % pid)
    # instance FTPd before daemonizing, so that in case of problems we
    # get an exception here and exit immediately
    server = get_server()
    _daemonize()
    server.serve_forever()


def main():
    global PID_FILE, LOG_FILE
    USAGE = "python [-p PIDFILE] [-l LOGFILE]\n\n" \
            "Commands:\n  - start\n  - stop\n  - status"
    parser = optparse.OptionParser(usage=USAGE)
    parser.add_option('-l', '--logfile', dest='logfile',
                      help='the log file location')
    parser.add_option('-p', '--pidfile', dest='pidfile', default=PID_FILE,
                      help='file to store/retreive daemon pid')
    options, args = parser.parse_args()

    if options.pidfile:
        PID_FILE = options.pidfile
    if options.logfile:
        LOG_FILE = options.logfile

    if not args:
        server = get_server()
        server.serve_forever()
    else:
        if len(args) != 1:
            sys.exit('too many commands')
        elif args[0] == 'start':
            daemonize()
        elif args[0] == 'stop':
            stop()
        elif args[0] == 'restart':
            try:
                stop()
            finally:
                daemonize()
        elif args[0] == 'status':
            status()
        else:
            sys.exit('invalid command')

if __name__ == '__main__':
    sys.exit(main())
