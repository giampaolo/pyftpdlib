#!/usr/bin/env python
# $Id$
#
#  pyftpdlib is released under the MIT license, reproduced below:
#  ======================================================================
#  Copyright (C) 2007-2012 Giampaolo Rodola' <g.rodola@gmail.com>
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

"""
FTP server benchmark script.

In order to run this you must have a listening FTP server with a user
with writing permissions configured.

Example usages:
  python bench.py -u USER -p PASSWORD
  python bench.py -u USER -p PASSWORD -H ftp.domain.com -P 21   # host / port
  python bench.py -u USER -p PASSWORD -b transfer
  python bench.py -u USER -p PASSWORD -b concurrence
  python bench.py -u USER -p PASSWORD -b all
  python bench.py -u USER -p PASSWORD -b concurrence -n 500     # 500 clients
  python bench.py -u USER -p PASSWORD -b concurrence -s 20M     # file size
  python bench.py -u USER -p PASSWORD -b concurrence -p 3521    # memory usage
"""

# Some benchmarks (Linux 3.0.0, Intel core duo - 3.1 Ghz).
#
# pyftpdlib 0.6.0:
#
# (starting with 9M of RSS memory being used)
# STOR (client -> server)                      528.02 MB/sec  9M RSS
# RETR (server -> client)                      693.41 MB/sec  10M RSS
# 200 concurrent clients (connect, login)        0.25 secs    10M RSS
# 200 concurrent clients (RETR 10M file)         3.68 secs    11M RSS
# 200 concurrent clients (STOR 10M file)         6.11 secs    11M RSS
# 200 concurrent clients (quit)                  0.02 secs
#
# pyftpdlib 0.7.0:
#  (starting with 6M of RSS memory being used)
#   STOR (client -> server)                      512.80 MB/sec  9M RSS
#   RETR (server -> client)                     1694.14 MB/sec  9M RSS
#   200 concurrent clients (connect, login)        0.95 secs    11M RSS
#   200 concurrent clients (RETR 10M file)         2.80 secs    12M RSS
#   200 concurrent clients (STOR 10M file)         6.30 secs    13M RSS
#   200 concurrent clients (quit)                  0.02 secs
#
# proftpd 1.3.4rc2:
#
#   (starting with 2M of RSS memory being used)
#   STOR (client -> server)                      609.22 MB/sec  6M RSS
#   RETR (server -> client)                     1313.77 MB/sec  6M RSS
#   200 concurrent clients (connect, login)        7.53 secs    862M RSS
#   200 concurrent clients (RETR 10M file)         2.76 secs    862M RSS
#   200 concurrent clients (STOR 10M file)         6.39 secs    862M RSS
#   200 concurrent clients (quit)                  0.23 secs
#
# vsftpd 2.3.2
#
#   (starting with 1M of RSS memory being used)
#   STOR (client -> server)                      670.48 MB/sec  2M RSS
#   RETR (server -> client)                     1505.18 MB/sec  2M RSS
#   200 concurrent clients (connect, login)       12.61 secs    289M RSS
#   200 concurrent clients (RETR 10M file)         2.30 secs    289M RSS
#   200 concurrent clients (STOR 10M file)          N/A
#   200 concurrent clients (quit)                  0.01


from __future__ import with_statement, division
import ftplib
import sys
import os
import atexit
import time
import optparse
import contextlib
import asyncore
import asynchat
try:
    import resource
except ImportError:
    resource = None

try:
    import psutil
except ImportError:
    psutil = None

HOST = 'localhost'
PORT = 21
USER = None
PASSWORD = None
TESTFN = "$testfile"
BUFFER_LEN = 8192
SERVER_PROC = None


# http://goo.gl/6V8Rm
def hilite(string, ok=True, bold=False):
    """Return an highlighted version of 'string'."""
    attr = []
    if ok is None:  # no color
        pass
    elif ok:   # green
        attr.append('32')
    else:   # red
        attr.append('31')
    if bold:
        attr.append('1')
    return '\x1b[%sm%s\x1b[0m' % (';'.join(attr), string)

if not sys.stdout.isatty() or os.name != 'posix':
    def hilite(s, *args, **kwargs):
        return s

server_memory = []

def print_bench(what, value, unit=""):
    s = "%s %s %-8s" % (hilite("%-50s" % what, ok=None, bold=0),
                      hilite("%8.2f" % value),
                      unit)
    if server_memory:
        s += "%s RSS" % hilite(server_memory.pop())
    print s.strip()

# http://goo.gl/zeJZl
def bytes2human(n, format="%(value)i%(symbol)s"):
    """
    >>> bytes2human(10000)
    '9K'
    >>> bytes2human(100001221)
    '95M'
    """
    symbols = ('B', 'K', 'M', 'G', 'T', 'P', 'E', 'Z', 'Y')
    prefix = {}
    for i, s in enumerate(symbols[1:]):
        prefix[s] = 1 << (i+1)*10
    for symbol in reversed(symbols[1:]):
        if n >= prefix[symbol]:
            value = float(n) / prefix[symbol]
            return format % locals()
    return format % dict(symbol=symbols[0], value=n)

# http://goo.gl/zeJZl
def human2bytes(s):
    """
    >>> human2bytes('1M')
    1048576
    >>> human2bytes('1G')
    1073741824
    """
    symbols = ('B', 'K', 'M', 'G', 'T', 'P', 'E', 'Z', 'Y')
    letter = s[-1:].strip().upper()
    num = s[:-1]
    assert num.isdigit() and letter in symbols, s
    num = float(num)
    prefix = {symbols[0]:1}
    for i, s in enumerate(symbols[1:]):
        prefix[s] = 1 << (i+1)*10
    return int(num * prefix[letter])

def register_memory():
    """Register RSS memory used by server process and its children."""
    if SERVER_PROC is not None:
        mem = SERVER_PROC.get_memory_info().rss
        for child in SERVER_PROC.get_children():
            mem += child.get_memory_info().rss
        server_memory.append(bytes2human(mem))

def timethis(what):
    """"Utility function for making simple benchmarks (calculates time calls).
    It can be used either as a context manager or as a decorator.
    """
    @contextlib.contextmanager
    def benchmark():
        timer = time.clock if sys.platform == "win32" else time.time
        start = timer()
        yield
        stop = timer()
        res = (stop - start)
        print_bench(what, res, "secs")

    if hasattr(what,"__call__"):
        def timed(*args,**kwargs):
            with benchmark():
                return what(*args,**kwargs)
        return timed
    else:
        return benchmark()

def connect():
    """Connect to FTP server, login and return an ftplib.FTP instance."""
    ftp = ftplib.FTP()
    ftp.connect(HOST, PORT)
    ftp.login(USER, PASSWORD)
    return ftp

def retr(ftp):
    """Same as ftplib's retrbinary() but discard the received data."""
    ftp.voidcmd('TYPE I')
    conn = ftp.transfercmd("RETR " + TESTFN)
    recv_bytes = 0
    while 1:
        data = conn.recv(BUFFER_LEN)
        if not data:
            break
        recv_bytes += len(data)
    conn.close()
    ftp.voidresp()

def stor(ftp, size):
    """Same as ftplib's storbinary() but just sends dummy data
    instead of reading it from a real file.
    """
    ftp.voidcmd('TYPE I')
    conn = ftp.transfercmd("STOR " + TESTFN)
    chunk = 'x' * BUFFER_LEN
    total_sent = 0
    while 1:
        sent = conn.send(chunk)
        total_sent += sent
        if total_sent >= size:
            break
    conn.close()
    ftp.voidresp()

def bytes_per_second(ftp, retr=True):
    """Return the number of bytes transmitted in 1 second."""
    bytes = 0
    if retr:
        def request_file():
            ftp.voidcmd('TYPE I')
            conn = ftp.transfercmd("retr " + TESTFN)
            return conn

        conn = request_file()
        register_memory()
        stop_at = time.time() + 1.0
        while stop_at > time.time():
            chunk = conn.recv(BUFFER_LEN)
            if not chunk:
                a = time.time()
                while conn.recv(BUFFER_LEN):
                    break
                conn.close()
                ftp.voidresp()
                conn = request_file()
                stop_at += time.time() - a
            bytes += len(chunk)
        conn.close()
        try:
            ftp.voidresp()
        except (ftplib.error_temp, ftplib.error_perm):
            pass
    else:
        ftp.voidcmd('TYPE I')
        conn = ftp.transfercmd("STOR " + TESTFN)
        register_memory()
        chunk = 'x' * BUFFER_LEN
        stop_at = time.time() + 1
        while stop_at > time.time():
            bytes += conn.send(chunk)
        conn.close()
        ftp.voidresp()

    ftp.quit()
    return bytes

def cleanup():
    ftp = connect()
    try:
        ftp.delete(TESTFN)
    except (ftplib.error_perm, ftplib.error_temp):
        pass
    ftp.quit()


class AsyncReader(asyncore.dispatcher):
    """Just read data from a connected socket, asynchronously."""

    def __init__(self, sock):
        asyncore.dispatcher.__init__(self, sock)

    def writable(self):
        return False

    def handle_read(self):
        chunk = self.socket.recv(BUFFER_LEN)
        if not chunk:
            self.close()

    def handle_close(self):
        self.close()

    def handle_error(self):
        raise

class AsyncWriter(asynchat.async_chat):
    """Just write dummy data to a connected socket, asynchronously."""
    class ChunkProducer:
        def __init__(self, size):
            self.size = size
            self.sent = 0
            self.chunk = 'x' * BUFFER_LEN

        def more(self):
            if self.sent >= self.size:
                return ''
            self.sent += len(self.chunk)
            return self.chunk

    def __init__(self, sock, size):
        asynchat.async_chat.__init__(self, sock)
        self.push_with_producer(self.ChunkProducer(size))
        self.close_when_done()

    def handle_error(self):
        raise

class AsyncQuit(asynchat.async_chat):

    def __init__(self, sock):
        asynchat.async_chat.__init__(self, sock)
        self.in_buffer = []
        self.set_terminator('\r\n')
        self.push('QUIT\r\n')

    def collect_incoming_data(self, data):
        self.in_buffer.append(data)

    def found_terminator(self):
        self.handle_close()

    def handle_error(self):
        raise

class OptFormatter(optparse.IndentedHelpFormatter):

    def format_epilog(self, s):
        return s.lstrip()

    def format_option(self, option):
        result = []
        opts = self.option_strings[option]
        result.append('  %s\n' % opts)
        if option.help:
            help_text = '     %s\n\n' % self.expand_default(option)
            result.append(help_text)
        return ''.join(result)

def main():
    global HOST, PORT, USER, PASSWORD, SERVER_PROC
    USAGE = "%s -u USERNAME -p PASSWORD [-H] [-P] [-b] [-n] [-s] [-k]" % __file__
    parser = optparse.OptionParser(usage=USAGE,
                                   epilog=__doc__[__doc__.find('Example'):],
                                   formatter=OptFormatter())
    parser.add_option('-u', '--user', dest='user', help='username')
    parser.add_option('-p', '--pass', dest='password', help='password')
    parser.add_option('-H', '--host', dest='host', default=HOST, help='hostname')
    parser.add_option('-P', '--port', dest='port', default=PORT, help='port')
    parser.add_option('-b', '--benchmark', dest='benchmark', default='transfer',
                      help="benchmark type ('transfer', 'concurrence', 'all')")
    parser.add_option('-n', '--clients', dest='clients', default=200, type="int",
                      help="number of concurrent clients used by 'concurrence' "
                           "benchmark")
    parser.add_option('-s', '--filesize', dest='filesize', default="10M",
                      help="file size used by 'concurrence' benchmark "
                           "(e.g. '10M')")
    parser.add_option('-k', '--pid', dest='pid', default=None, type="int",
                      help="the PID of the server process to bench memory usage")


    options, args = parser.parse_args()
    if not options.user or not options.password:
        sys.exit(USAGE)
    else:
        USER = options.user
        PASSWORD = options.password
        HOST = options.host
        PORT = options.port
        try:
            FILE_SIZE = human2bytes(options.filesize)
        except (ValueError, AssertionError):
            parser.error("invalid file size %r" % options.filesize)
        if options.pid is not None:
            if psutil is None:
                raise ImportError("-p option requires psutil module")
            SERVER_PROC = psutil.Process(options.pid)

    def bench_stor(title="STOR (client -> server)"):
        bytes = bytes_per_second(connect(), retr=False)
        print_bench(title, round(bytes / 1024.0 / 1024.0, 2), "MB/sec")

    def bench_retr(title="RETR (server -> client)"):
        bytes = bytes_per_second(connect(), retr=True)
        print_bench(title, round(bytes / 1024.0 / 1024.0, 2), "MB/sec")

    def bench_multi():
        howmany = options.clients

        # The OS usually sets a limit of 1024 as the maximum number of
        # open file descriptors for the current process.
        # Let's set the highest number possible, just to be sure.
        if howmany > 500 and resource is not None:
            soft, hard = resource.getrlimit(resource.RLIMIT_NOFILE)
            resource.setrlimit(resource.RLIMIT_NOFILE, (hard, hard))

        def bench_multi_connect():
            with timethis("%i concurrent clients (connect, login)" % howmany):
                clients = []
                for x in range(howmany):
                    clients.append(connect())
                register_memory()
            return clients

        def bench_multi_retr(clients):
            stor(clients[0], FILE_SIZE)
            with timethis("%s concurrent clients (RETR %s file)" \
                          % (howmany, bytes2human(FILE_SIZE))):
                for ftp in clients:
                    ftp.voidcmd('TYPE I')
                    conn = ftp.transfercmd("RETR " + TESTFN)
                    AsyncReader(conn)
                register_memory()
                asyncore.loop(use_poll=True)
            for ftp in clients:
                ftp.voidresp()

        def bench_multi_stor(clients):
            with timethis("%s concurrent clients (STOR %s file)" \
                          % (howmany, bytes2human(FILE_SIZE))):
                for ftp in clients:
                    ftp.voidcmd('TYPE I')
                    conn = ftp.transfercmd("STOR " + TESTFN)
                    AsyncWriter(conn, 1024 * 1024 * 5)
                register_memory()
                asyncore.loop(use_poll=True)
            for ftp in clients:
                ftp.voidresp()

        def bench_multi_quit(clients):
            for ftp in clients:
                AsyncQuit(ftp.sock)
            with timethis("%i concurrent clients (QUIT)" % howmany):
                asyncore.loop(use_poll=True)

        clients = bench_multi_connect()
        bench_stor("STOR (1 file with %s idle clients)" % len(clients))
        bench_retr("RETR (1 file with %s idle clients)" % len(clients))
        bench_multi_retr(clients)
        bench_multi_stor(clients)
        bench_multi_quit(clients)

    # before starting make sure we have write permissions
    ftp = connect()
    conn = ftp.transfercmd("STOR " + TESTFN)
    conn.close()
    ftp.voidresp()
    ftp.delete(TESTFN)
    ftp.quit()
    atexit.register(cleanup)

    # start benchmark
    if SERVER_PROC is not None:
        register_memory()
        print "(starting with %s of RSS memory being used)" \
               % hilite(server_memory.pop())
    if options.benchmark == 'transfer':
        bench_stor()
        bench_retr()
    elif options.benchmark == 'concurrence':
        bench_multi()
    elif options.benchmark == 'all':
        bench_stor()
        bench_retr()
        bench_multi()
    else:
        sys.exit("invalid 'benchmark' parameter %r" % options.benchmark)

if __name__ == '__main__':
    main()
