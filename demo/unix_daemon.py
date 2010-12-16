#!/usr/bin/env python
# $Id$

'''A unix FTP daemon. This daemon has the ability to:

 - Spawn multiple worker processes (ala pre-fork).
 - Drop privileges after privileged operations.
 - Close gracefully when signaled.

For more information on the daemonizing technique used here, visit:

http://www.jejik.com/articles/2007/02/a_simple_unix_linux_daemon_in_python/

Author: Ben Timby, <btimby@gmail.com>'''

import os, sys, signal
from pyftpdlib.ftpserver import FTPServer, FTPHandler

class UnixFTPDaemon(object):
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
        # Now, let's go into the background using a pair of fork()s.
        pid = os.fork()
        if pid > 0:
            # We are the main process, we have done our job...
            return
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
        if self.pidfile:
            with file(self.pidfile, 'w') as pf:
                pf.write(str(os.getpid()))
        # we don't need these anymore...
        sys.stdout.flush()
        sys.stderr.flush()
        si = file('/dev/null', 'r')
        so = file('/dev/null', 'a+')
        se = file('/dev/null', 'a+', 0)
        os.dup2(si.fileno(), sys.stdin.fileno())
        os.dup2(so.fileno(), sys.stdout.fileno())
        os.dup2(se.fileno(), sys.stderr.fileno())
        # Set up our signal handler:
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
        # Always clean up after yourself.
        if self.worker_pids and self.pidfile and \
           os.path.exists(self.pidfile):
            try:
                os.remove(self.pidfile)
            except:
                pass

    def stop(self):
        '''This method is provided to cleanly exit the daemon. It is
        intended to be called from a signal handler. This way the daemon
        process can handle the TERM signal to exit smoothly.'''
        if self.server is not None:
            self.server.close()

def main():
    '''Demonstrates a basic FTP daemon using the stock FTPServer and FTPHandler.'''
    # ServerClass - Here you can customize the FTPServer class to use any
    #               authorizers/abstractfs you desire. This example uses
    #               the stock FTPServer.
    # HandlerClass - You can customize the FTPHandler that will be used for
    #                each client connection. This example uses the stock
    #                FTPHandler.
    # addr - The IP address to bind to.
    # port - The TCP port to bind to.
    # worker_num - The number of workers is useful if you are running on an
    #              SMP system. This will allow a worker process on each CPU
    #              rather than only CPU0.
    # uid - The unix user to become after privileged operations.
    # gid - The unix group to become after privileged operations.
    # **************************************************************************
    # * if providing a uid/gid, the AbstractedFS will not work, as it attempts *
    # * to set the uid/gid to the connecting user. Only root can do this, so   *
    # * If you wish to drop privileges, you will need to find another way to   *
    # * enforce permissions.                                                   *
    # **************************************************************************
    # pidfile - A file in which to record the pid of the master process. This pid
    #           can be used to later shut down the daemon.
    # Daemon Shutdown:
    #
    # kill `cat /path/to/pidfile`
    daemon = UnixFTPDaemon('0.0.0.0', 21, worker_num=4)
    daemon.start()

if __name__ == '__main__':
    main()
