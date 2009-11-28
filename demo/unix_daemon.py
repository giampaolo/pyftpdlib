#!/usr/bin/env python
# $Id$

"""A basic unix daemon based on a Chad J. Schroeder recipe:
http://code.activestate.com/recipes/278731

Author: Michele Petrazzo, Italy. mail: michele.petrazzo <at> gmail.com
"""

import os
import sys
import time
import signal
import optparse
import resource
import threading


DAEMON_NAME = "pyftplib"
DAEMON_PID_FILE = "/var/run/%s.pid"% DAEMON_NAME
UMASK = 0
WORKDIR = os.getcwd()
MAXFD = 1024

if (hasattr(os, "devnull")):
   REDIRECT_TO = os.devnull
else:
   REDIRECT_TO = "/dev/null"


def _create_daemon():
    """Detach a process from the controlling terminal and run it in the
    background as a daemon.
    """
    try:
        pid = os.fork()
    except OSError as err:
        raise Exception("%s [%d]" % (err.strerror, err.errno))

    if (pid == 0):
        os.setsid()
        try:
            pid = os.fork()
        except OSError as err:
            raise Exception("%s [%d]" % (err.strerror, err.errno))

        if (pid == 0):
            os.chdir(WORKDIR)
            os.umask(UMASK)
        else:
            os._exit(0)
    else:
        os._exit(0)
    maxfd = resource.getrlimit(resource.RLIMIT_NOFILE)[1]
    if (maxfd == resource.RLIM_INFINITY):
        maxfd = MAXFD
    for fd in range(0, maxfd):
      try:
         os.close(fd)
      except OSError:
         pass
    os.open(REDIRECT_TO, os.O_RDWR)

    os.dup2(0, 1)
    os.dup2(0, 2)

    return(0)

def _ctrl_daemon_exists(pid):
    """Control if the the previous daemon exists,otherwise raise."""
    t = 0
    while os.path.exists("/proc/%s" % pid):
        if t > 50:
            raise RuntimeError("Waited for too long for process to kill")
        time.sleep(0.1)
        t += 1

def _kill_daemon():
    """Kill the daemon, if found."""
    if os.path.exists(DAEMON_PID_FILE):
        pid = int(open(DAEMON_PID_FILE).read().strip())
        if os.path.exists("/proc/%s" % pid):
            # kill the given pid
            os.kill(pid, signal.SIGTERM)

        _ctrl_daemon_exists(pid)

        # and clean the old pid file
        os.remove(DAEMON_PID_FILE)

def daemonize(options):
    """Control if I'm already in execution and kill the process.
    In any case, execute daemonize code.
    """
    if options.outputfile:
        global REDIRECT_TO
        REDIRECT_TO = options.outputfile

        open(REDIRECT_TO, "wb").write("")

    if options.foreground:
        # do nothing in foreground
        return

    _create_daemon()

    # create the pid path
    open(DAEMON_PID_FILE, "wb").write("%s" % os.getpid())

    def _exit(sig, frame):
        # and close all the timers/other threads that has a cancel method
        for t in threading.enumerate():
            if hasattr(t, "cancel") and hasattr(t.cancel, '__call__'):
                t.cancel()

        # wait for all threads to shutdown
        time.sleep(0.5)

        sys.exit(0)

    signal.signal(signal.SIGTERM, _exit)


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
    options, args = parser.parse_args()

    # option control
    num_opt = len([x for x in ("daemon", "foreground",
                                                         "kill") if getattr(options, x)])
    if num_opt == 0:
        parser.error("pass me at least one option")
    elif num_opt > 1:
        parser.error("options are mutually exclusive, use one at a time")

    if options.kill:
        _kill_daemon()
    else:
        daemonize(options)

    return options

def start_demo():
    # use the basic example to show how we work
    import basic_ftpd
    basic_ftpd.main()

if __name__ == '__main__':
    options = main()
    if not options.kill:
        start_demo()
