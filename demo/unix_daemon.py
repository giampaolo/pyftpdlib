#!/usr/bin/env python
# unix_daemon.py

"""A basic unix daemon based on a Chad J. Schroeder recipes
   (http://code.activestate.com/recipes/278731/)
   Add also some command line switch for make the daemon simplier to use.
   Developer: Michele Petrazzo - Italy. mail: michele.petrazzo <at> gmail.com
   Usage:
       python unix_daemon.py -h
"""

import os
import sys
import time
import signal
import optparse
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
    except OSError, e:
        raise Exception, "%s [%d]" % (e.strerror, e.errno)
   
    if (pid == 0):
        os.setsid()
        try:
            pid = os.fork()
        except OSError, e:
            raise Exception, "%s [%d]" % (e.strerror, e.errno)

        if (pid == 0):
            os.chdir(WORKDIR)
            os.umask(UMASK)
        else:
            os._exit(0)
    else:
        os._exit(0)
    import resource
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

def _ctrl_damon_exists(pid):
    """Control if the the previous daemon exists, 
    otherwise raise
    """
    t = 0
    while os.path.exists("/proc/%s" % pid):
        if t > 20:
            #too much time
            raise RuntimeError("Wait too much time for process end, exit!")
        
        time.sleep(0.5)
        t += 1

def _kill_daemon():
    """Kill the daemon, if found
    """
    if os.path.exists(DAEMON_PID_FILE):
        pid = int(open(DAEMON_PID_FILE).read().strip())
        if os.path.exists("/proc/%s" % pid):
            #say to the pid to terminate
            os.kill(pid, signal.SIGTERM)
        
        _ctrl_damon_exists(pid)
        
        #and clean the old pid file
        os.remove(DAEMON_PID_FILE)
        
def daemonize(options):
    """Control if I'm already in execution and kill the process.
    In any case, execute daemonize code
    """
    
    if options.outputfile:
        global REDIRECT_TO
        REDIRECT_TO = options.outputfile
        
        open(REDIRECT_TO, "wb").write("")
    
    if options.foreground:
        #do nothing in foreground
        return
    
    _create_daemon()
    
    #create the pid path
    open(DAEMON_PID_FILE, "wb").write("%s" % os.getpid())
    
    def _exit(sig, frame):
        #and close all the timers/other threads that has a cancel method
        for t in threading.enumerate():
            if hasattr(t, "cancel") and callable(t.cancel):
                t.cancel()
        
        #wait for all the thread to shutdown
        time.sleep(0.5)
        
        sys.exit(0)
        
    signal.signal(signal.SIGTERM, _exit)
    
USAGE = '''%s -d|-f|-k [-o outputfile]
Command line for pyftplib. 
Can create a daemon, use it into foreground or kill an running one. 
You can also save the output to a file (usefull on daemon mode only)''' % sys.argv[0]

def main():
    parser = optparse.OptionParser(usage=USAGE)
    parser.add_option('-d', '--daemon', dest='daemon', 
                      default=False, action='store_true',
                      help='Create a pyftplib daemon that work in background')
    parser.add_option('-f', '--foreground', dest='foreground', 
                      default=False, action='store_true',
                      help='Interactive mode, do the work in foreground')
    parser.add_option('-k', '--kill', dest='kill',
                      default=False, action='store_true',
                      help='Control if there is a pyftplib daemon and kill it')
    parser.add_option('-o', '--outputfile', dest='outputfile', 
                      help='Save the stdout to the file')
    options, args = parser.parse_args()
    
    #Option control
    num_opt = len( filter(lambda x: getattr(options, x), ("daemon", "foreground", "kill")) )
    
    if num_opt == 0:
        parser.error("Pass me at least one option!")
    elif num_opt > 1:
        parser.error("The options are mutually exclusive. Use one at a time")
    
    if options.kill:
        _kill_daemon()
    else:
        daemonize(options)
    
    return options

def start_demo():
    #use the basic example for show how we work
    import basic_ftpd
    basic_ftpd.main()

if __name__ == '__main__':
    options = main()
    if not options.kill:
        start_demo()
