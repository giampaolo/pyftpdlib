#!/usr/bin/env python
# $Id$

'''A unix FTP daemon. This demonstrates the UnixFTPDaemon class.

Author: Ben Timby, <btimby@gmail.com>'''

from pyftpdlib.contrib import UnixFTPDaemon

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
    #
    # Below we are using 3 workers, this will result in 4 total processes (1 master,
    # and 3 workers). It is recommended to use one process per core, to take advantage
    # of multiple CPUs. Any more than one process per core will simply consume more
    # memory without spreading the load any more evenly.
    daemon = UnixFTPDaemon('0.0.0.0', 21, worker_num=3)
    daemon.start()

if __name__ == '__main__':
    main()
