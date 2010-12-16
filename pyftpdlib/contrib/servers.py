#!/usr/bin/env python

"""A collection of classes useful for building FTP servers. These classes
are generally used to orchestrate the FTPServer/FTPHandler classes.
"""

import os
import sys
import signal
import multiprocessing

from pyftpdlib.ftpserver import FTPServer, FTPHandler

def daemonize(umask, pidfile=None):
    """This function will use two fork() system calls to go into the background.
    The calling process will be exit()ed. The child (daemon) will return from this
    function. An optional pidfile argument will cause the function to record the
    child (daemon's) pid into that file.
    """
    # Now, let's go into the background using a pair of fork()s.
    pid = os.fork()
    if pid > 0:
        # We are the main process, we have done our job...
        sys.exit(0)
    # The child process continues, it will distance itself from the parent.
    os.chdir("/")
    os.setsid()
    os.umask(umask)
    # Now fork again, this new child will be our daemon.
    pid = os.fork()
    if pid > 0:
        # The second master can exit.
        sys.exit(0)
    # Record our pid so we can be killed later...
    if pidfile:
        try:
            file(pidfile, 'w').write(str(os.getpid()))
        except:
            # Don't die just because we can't write to the pid file.
            pass
    # We don't need these anymore... Set stdin/stdout/stderr to /dev/null
    sys.stdout.flush()
    sys.stderr.flush()
    si = file('/dev/null', 'r')
    so = file('/dev/null', 'a+')
    se = file('/dev/null', 'a+', 0)
    os.dup2(si.fileno(), sys.stdin.fileno())
    os.dup2(so.fileno(), sys.stdout.fileno())
    os.dup2(se.fileno(), sys.stderr.fileno())

class UnixFTPDaemon(object):
    """A unix FTP daemon. This daemon has the ability to:

     - Spawn multiple worker processes (ala pre-fork).
     - Drop privileges after privileged operations.
     - Close gracefully when signaled.

    For more information on the daemonizing technique used here, visit:

    http://www.jejik.com/articles/2007/02/a_simple_unix_linux_daemon_in_python/

    Author: Ben Timby, <btimby@gmail.com>
    """
    def __init__(self, (addr, port), server_class=FTPServer, hander_class=FTPHandler, worker_num=None, uid=None, gid=None, pidfile=None, umask=117):
        """Class constructor. Prepares the daemon for use.

        - (tuple) addr, port: the address and port to bind to.
        - (type) server_class: the FTPServer class or derivitive to use.
        - (type) handler_class: the FTPHandler class or dirivitive to use.
        - (int) worker_num: the number of worker process to spawn. By default
                            the number of CPU cores will be determined and
                            enough workers will be spawned to cover all CPUs.
        - (int) uid: the uid to drop privileges to.
        - (int) gid: the gid to drop privileges to.
        - (string) pidfile: the file in which to store the master process pid.
        - (int) umask: the umask to apply to the process. A safe default is provided.
        """
        self.server_class = server_class
        self.handler_class = handler_class
        self.addrport = (addr, port)
        self.worker_num = worker_num
        if self.worker_num is None:
            self.worker_num = multiprocessing.cpu_count() - 1
        self.uid = uid
        self.gid = gid
        self.pidfile = pidfile
        self.umask = umask
        self._worker_pids = []
        self._server = None

    def start(self, use_poll=False, timeout=1.0):
        """Start the daemon by fork()ing a background process.
        If more than one worker is desired, also start multiple other
        child processes. Each worker process will drop privileges if
        a uid/gid is provided.
        """
        # We are still root, so let's go ahead and bind to our address/port
        # combo. Once we drop privileges, we may not be able to.
        self._server = self.server_class(self.addrport, self.handler_class)
        # We are done with our privileged operations, so let's drop
        # root privileges. We are not yet in the background, so we can
        # print error messages if need be.
        if self.gid:
            try:
                os.setgid(self.gid)
            except OSError, e:
                sys.stderr.write('Could not set group id: %s' % e)
                sys.stderr.flush()
        if self.uid:
            try:
                os.setuid(self.uid)
            except OSError, e:
                sys.stderr.write('Could not set user id: %s' % e)
                sys.stderr.flush()
        # Become a daemon, the default umask of 117 prevents files from being executable.
        # it also prevents them from being world-anything.
        daemonize(self.umask, self.pidfile)
        # Set up our signal handler, workers inherit this.
        signal.signal(signal.SIGTERM, self.signal)
        # Let's spawn our worker processes (if any).
        for i in range(self.worker_num):
            pid = os.fork()
            if pid == 0:
                # The child process (pid==0) can exit the for loop.
                break
            # We are master, so save the child's pid.
            self._worker_pids.append(pid)
        # All processes can now enter into the asyncore event loop to
        # start handling connections.
        self._server.serve_forever(use_poll, timeout)

    def signal(self, signum, frame):
        """This method is registered as the SIGTERM handler in the
        start() method. This will ensure that the signal is propagated
        to the child processes and that we exit cleanly.
        """
        # Propagate the same signal to our children.
        for pid in self._worker_pids:
            try:
                os.kill(pid, signum)
            except:
                # At least try to kill the rest...
                pass
        # And then let's exit gracefully.
        self.stop()
        # Always clean up after yourself. But only if master process.
        if self._worker_pids and self.pidfile and \
           os.path.exists(self.pidfile):
            try:
                os.remove(self.pidfile)
            except:
                # Don't die just because we can't remove the pid file.
                pass

    def stop(self):
        """This method is provided to cleanly exit the daemon. It is
        intended to be called from a signal handler. This way the daemon
        process can handle the TERM signal to exit smoothly.
        """
        if self._server is not None:
            self._server.close_all(ignore_all=True)
