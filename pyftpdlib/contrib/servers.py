#!/usr/bin/env python

'''A collection of classes useful for building FTP servers. These classes
are generally used to orchestrate the FTPServer/FTPHandler classes.'''

import os, sys, signal
from pyftpdlib.ftpserver import FTPServer, FTPHandler

def daemonize(pidfile=None):
    '''This function will use two fork() system calls to go into the background.
    The calling process will be exit()ed. The child (daemon) will return from this
    function. An optional pidfile argument will cause the function to record the
    child (daemon's) pid into that file.'''
    # Now, let's go into the background using a pair of fork()s.
    pid = os.fork()
    if pid > 0:
        # We are the main process, we have done our job...
        sys.exit(0)
    # The child process continues, it will distance itself from the parent.
    os.chdir("/")
    os.setsid()
    os.umask(0)
    # Now fork again, this new child will be our daemon.
    pid = os.fork()
    if pid > 0:
        # The second master can exit.
        sys.exit(0)
    # Record our pid so we can be killed later...
    if pidfile:
        try:
            with file(pidfile, 'w') as pf:
                pf.write(str(os.getpid()))
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
    '''A unix FTP daemon. This daemon has the ability to:

     - Spawn multiple worker processes (ala pre-fork).
     - Drop privileges after privileged operations.
     - Close gracefully when signaled.

    For more information on the daemonizing technique used here, visit:

    http://www.jejik.com/articles/2007/02/a_simple_unix_linux_daemon_in_python/

    Author: Ben Timby, <btimby@gmail.com>'''
    def __init__(self, addr, port, ServerClass=FTPServer, HandlerClass=FTPHandler, worker_num=0, uid=None, gid=None, pidfile=None):
        self.ServerClass = ServerClass
        self.HandlerClass = HandlerClass
        self.addrport = (addr, port)
        self.worker_num = worker_num
        self.uid = uid
        self.gid = gid
        self.pidfile = pidfile
        self.worker_pids = []
        self.server = None

    def start(self):
        '''Start the daemon by fork()ing a background process.
        If more than one worker is desired, also start multiple other
        child processes. Each worker process will drop privileges if
        a uid/gid is provided.'''
        # We are still root, so let's go ahead and bind to our address/port
        # combo. Once we drop privileges, we may not be able to.
        self.server = self.ServerClass(self.addrport, self.HandlerClass)
        # We are done with our privileged operations, so let's drop
        # root privileges. We are not yet in the background, so we can
        # print error messages if need be.
        if self.gid:
            try:
                os.setgid(self.gid)
            except OSError, e:
                print >> sys.stderr, 'Could not set effective group id: %s' % e
        if self.uid:
            try:
                os.setuid(self.uid)
            except OSError, e:
                print >> sys.stderr, 'Could not set effective user id: %s' % e
        # Become a daemon
        daemonize(self.pidfile)
        # Set up our signal handler, workers inherit this.
        signal.signal(signal.SIGTERM, self.signal)
        # Let's spawn our worker processes (if any).
        for i in range(self.worker_num):
            pid = os.fork()
            if pid == 0:
                # The child process (pid==0) can exit the for loop.
                break
            # We are master, so save the child's pid.
            self.worker_pids.append(pid)
        # All processes can now enter into the asyncore event loop to
        # start handling connections.
        self.server.serve_forever()

    def signal(self, signum, frame):
        '''This method is registered as the SIGTERM handler in the
        start() method. This will ensure that the signal is propagated
        to the child processes and that we exit cleanly.'''
        # Propagate the same signal to our children.
        for pid in self.worker_pids:
            try:
                os.kill(pid, signum)
            except:
                # At least try to kill the rest...
                pass
        # And then let's exit gracefully.
        self.stop()
        # Always clean up after yourself. But only if master process.
        if self.worker_pids and self.pidfile and \
           os.path.exists(self.pidfile):
            try:
                os.remove(self.pidfile)
            except:
                # Don't die just because we can't remove the pid file.
                pass

    def stop(self):
        '''This method is provided to cleanly exit the daemon. It is
        intended to be called from a signal handler. This way the daemon
        process can handle the TERM signal to exit smoothly.'''
        if self.server is not None:
            self.server.close()
