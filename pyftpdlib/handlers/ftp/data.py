# Copyright (C) 2007 Giampaolo Rodola' <g.rodola@gmail.com>.
# Use of this source code is governed by MIT license that can be
# found in the LICENSE file.


import asynchat
import errno
import os
import socket
import traceback

from pyftpdlib.exceptions import _FileReadWriteError
from pyftpdlib.exceptions import _GiveUpOnSendfile
from pyftpdlib.exceptions import _RetryError
from pyftpdlib.ioloop import _ERRNOS_DISCONNECTED
from pyftpdlib.ioloop import _ERRNOS_RETRY
from pyftpdlib.ioloop import AsyncChat
from pyftpdlib.ioloop import timer
from pyftpdlib.log import debug
from pyftpdlib.log import logger
from pyftpdlib.utils import strerror

__all__ = ["DTPHandler", "ThrottledDTPHandler"]


class DTPHandler(AsyncChat):
    """Class handling server-data-transfer-process (server-DTP, see
    RFC-959) managing data-transfer operations involving sending
    and receiving data.

    Class attributes:

     - (int) timeout: the timeout which roughly is the maximum time we
       permit data transfers to stall for with no progress. If the
       timeout triggers, the remote client will be kicked off
       (defaults 300).

     - (int) ac_in_buffer_size: incoming data buffer size (defaults 65536)

     - (int) ac_out_buffer_size: outgoing data buffer size (defaults 65536)
    """

    timeout = 300
    ac_in_buffer_size = 65536
    ac_out_buffer_size = 65536

    def __init__(self, sock, cmd_channel):
        """Initialize the command channel.

        - (instance) sock: the socket object instance of the newly
           established connection.
        - (instance) cmd_channel: the command channel class instance.
        """
        self.cmd_channel = cmd_channel
        self.file_obj = None
        self.receive = False
        self.transfer_finished = False
        self.tot_bytes_sent = 0
        self.tot_bytes_received = 0
        self.cmd = None
        self.log = cmd_channel.log
        self.log_exception = cmd_channel.log_exception
        self._data_wrapper = None
        self._lastdata = 0
        self._had_cr = False
        self._start_time = timer()
        self._resp = ()
        self._offset = None
        self._filefd = None
        self._idler = None
        self._initialized = False
        try:
            AsyncChat.__init__(self, sock, ioloop=cmd_channel.ioloop)
        except OSError as err:
            # if we get an exception here we want the dispatcher
            # instance to set socket attribute before closing, see:
            # https://github.com/giampaolo/pyftpdlib/issues/188
            AsyncChat.__init__(
                self, socket.socket(), ioloop=cmd_channel.ioloop
            )
            # https://github.com/giampaolo/pyftpdlib/issues/143
            self.close()
            if err.errno == errno.EINVAL:
                return
            self.handle_error()
            return

        # remove this instance from IOLoop's socket map
        if not self.connected:
            self.close()
            return
        if self.timeout:
            self._idler = self.ioloop.call_every(
                self.timeout, self.handle_timeout, _errback=self.handle_error
            )

    def __repr__(self):
        return "<%s(%s)>" % (
            self.__class__.__name__,
            self.cmd_channel.get_repr_info(as_str=True),
        )

    __str__ = __repr__

    def use_sendfile(self):
        if not self.cmd_channel.use_sendfile:
            # as per server config
            return False
        if self.file_obj is None or not hasattr(self.file_obj, "fileno"):
            # directory listing or unusual file obj
            return False
        try:
            # io.IOBase default implementation raises io.UnsupportedOperation
            # UnsupportedOperation inherits ValueError
            # also may raise ValueError if stream is closed
            # https://docs.python.org/3/library/io.html#io.IOBase
            self.file_obj.fileno()
        except (OSError, ValueError):
            return False
        if self.cmd_channel._current_type != "i":  # noqa: SIM103
            # text file transfer (need to transform file content on the fly)
            return False
        return True

    def push(self, data):
        self._initialized = True
        self.modify_ioloop_events(self.ioloop.WRITE)
        self._wanted_io_events = self.ioloop.WRITE
        AsyncChat.push(self, data)

    def push_with_producer(self, producer):
        self._initialized = True
        self.modify_ioloop_events(self.ioloop.WRITE)
        self._wanted_io_events = self.ioloop.WRITE
        if self.use_sendfile():
            self._offset = producer.file.tell()
            self._filefd = self.file_obj.fileno()
            try:
                self.initiate_sendfile()
            except _GiveUpOnSendfile:
                pass
            else:
                self.initiate_send = self.initiate_sendfile
                return
        debug("starting transfer using send()", self)
        AsyncChat.push_with_producer(self, producer)

    def close_when_done(self):
        asynchat.async_chat.close_when_done(self)

    def initiate_send(self):
        asynchat.async_chat.initiate_send(self)

    def initiate_sendfile(self):
        """A wrapper around sendfile."""
        try:
            sent = os.sendfile(
                self._fileno,
                self._filefd,
                self._offset,
                self.ac_out_buffer_size,
            )
        except OSError as err:
            if err.errno in _ERRNOS_RETRY or err.errno == errno.EBUSY:
                return
            elif err.errno in _ERRNOS_DISCONNECTED:
                self.handle_close()
            elif self.tot_bytes_sent == 0:
                logger.warning(
                    "sendfile() failed; falling back on using plain send"
                )
                raise _GiveUpOnSendfile from err
            else:
                raise
        else:
            if sent == 0:
                # this signals the channel that the transfer is completed
                self.discard_buffers()
                self.handle_close()
            else:
                self._offset += sent
                self.tot_bytes_sent += sent

    # --- utility methods

    def _posix_ascii_data_wrapper(self, chunk):
        """The data wrapper used for receiving data in ASCII mode on
        systems using a single line terminator, handling those cases
        where CRLF ('\r\n') gets delivered in two chunks.
        """
        if self._had_cr:
            chunk = b"\r" + chunk

        if chunk.endswith(b"\r"):
            self._had_cr = True
            chunk = chunk[:-1]
        else:
            self._had_cr = False

        return chunk.replace(b"\r\n", bytes(os.linesep, "ascii"))

    def enable_receiving(self, type, cmd):
        """Enable receiving of data over the channel. Depending on the
        TYPE currently in use it creates an appropriate wrapper for the
        incoming data.

         - (str) type: current transfer type, 'a' (ASCII) or 'i' (binary).
        """
        self._initialized = True
        self.modify_ioloop_events(self.ioloop.READ)
        self._wanted_io_events = self.ioloop.READ
        self.cmd = cmd
        if type == "a":
            if os.linesep == "\r\n":
                self._data_wrapper = None
            else:
                self._data_wrapper = self._posix_ascii_data_wrapper
        elif type == "i":
            self._data_wrapper = None
        else:
            raise TypeError("unsupported type")
        self.receive = True

    def get_transmitted_bytes(self):
        """Return the number of transmitted bytes."""
        return self.tot_bytes_sent + self.tot_bytes_received

    def get_elapsed_time(self):
        """Return the transfer elapsed time in seconds."""
        return timer() - self._start_time

    def transfer_in_progress(self):
        """Return True if a transfer is in progress, else False."""
        return self.get_transmitted_bytes() != 0

    # --- connection

    def send(self, data):
        result = AsyncChat.send(self, data)
        self.tot_bytes_sent += result
        return result

    def refill_buffer(self):  # pragma: no cover
        """Overridden as a fix around https://bugs.python.org/issue1740572
        (when the producer is consumed, close() was called instead of
        handle_close()).
        """
        while True:
            if len(self.producer_fifo):
                p = self.producer_fifo.first()
                # a 'None' in the producer fifo is a sentinel,
                # telling us to close the channel.
                if p is None:
                    if not self.ac_out_buffer:
                        self.producer_fifo.pop()
                        # self.close()
                        self.handle_close()
                    return
                elif isinstance(p, str):
                    self.producer_fifo.pop()
                    self.ac_out_buffer += p
                    return
                data = p.more()
                if data:
                    self.ac_out_buffer += data
                    return
                else:
                    self.producer_fifo.pop()
            else:
                return

    def handle_read(self):
        """Called when there is data waiting to be read."""
        try:
            chunk = self.recv(self.ac_in_buffer_size)
        except _RetryError:
            pass
        except OSError:
            self.handle_error()
        else:
            self.tot_bytes_received += len(chunk)
            if not chunk:
                self.transfer_finished = True
                # self.close()  # <-- asyncore.recv() already do that...
                return
            if self._data_wrapper is not None:
                chunk = self._data_wrapper(chunk)
            try:
                self.file_obj.write(chunk)
            except OSError as err:
                raise _FileReadWriteError(err) from err

    handle_read_event = handle_read  # small speedup

    def readable(self):
        """Predicate for inclusion in the readable for select()."""
        # It the channel is not supposed to be receiving but yet it's
        # in the list of readable events, that means it has been
        # disconnected, in which case we explicitly close() it.
        # This is necessary as differently from FTPHandler this channel
        # is not supposed to be readable/writable at first, meaning the
        # upper IOLoop might end up calling readable() repeatedly,
        # hogging CPU resources.
        if not self.receive and not self._initialized:
            return self.close()
        return self.receive

    def writable(self):
        """Predicate for inclusion in the writable for select()."""
        return not self.receive and asynchat.async_chat.writable(self)

    def handle_timeout(self):
        """Called cyclically to check if data transfer is stalling with
        no progress in which case the client is kicked off.
        """
        if self.get_transmitted_bytes() > self._lastdata:
            self._lastdata = self.get_transmitted_bytes()
        else:
            msg = "Data connection timed out."
            self._resp = ("421 " + msg, logger.info)
            self.close()
            self.cmd_channel.close_when_done()

    def handle_error(self):
        """Called when an exception is raised and not otherwise handled."""
        try:
            raise  # noqa: PLE0704
        # an error could occur in case we fail reading / writing
        # from / to file (e.g. file system gets full)
        except _FileReadWriteError as err:
            error = strerror(err.errno)
        except Exception:
            # some other exception occurred;  we don't want to provide
            # confidential error messages
            self.log_exception(self)
            error = "Internal error"
        try:
            self._resp = (f"426 {error}; transfer aborted.", logger.warning)
            self.close()
        except Exception:
            logger.critical(traceback.format_exc())

    def handle_close(self):
        """Called when the socket is closed."""
        # If we used channel for receiving we assume that transfer is
        # finished when client closes the connection, if we used channel
        # for sending we have to check that all data has been sent
        # (responding with 226) or not (responding with 426).
        # In both cases handle_close() is automatically called by the
        # underlying asynchat module.
        if not self._closed:
            if self.receive:
                self.transfer_finished = True
            else:
                self.transfer_finished = len(self.producer_fifo) == 0
            try:
                if self.transfer_finished:
                    self._resp = ("226 Transfer complete.", logger.debug)
                else:
                    tot_bytes = self.get_transmitted_bytes()
                    self._resp = (
                        (
                            f"426 Transfer aborted; {int(tot_bytes)} bytes"
                            " transmitted."
                        ),
                        logger.debug,
                    )
            finally:
                self.close()

    def close(self):
        """Close the data channel, first attempting to close any remaining
        file handles."""
        debug("call: close()", inst=self)
        if not self._closed:
            # RFC-959 says we must close the connection before replying
            AsyncChat.close(self)

            # Close file object before responding successfully to client
            if self.file_obj is not None and not self.file_obj.closed:
                self.file_obj.close()

            if self._resp:
                self.cmd_channel.respond(self._resp[0], logfun=self._resp[1])

            if self._idler is not None and not self._idler.cancelled:
                self._idler.cancel()
            if self.file_obj is not None:
                filename = self.file_obj.name
                elapsed_time = round(self.get_elapsed_time(), 3)
                self.cmd_channel.log_transfer(
                    cmd=self.cmd,
                    filename=self.file_obj.name,
                    receive=self.receive,
                    completed=self.transfer_finished,
                    elapsed=elapsed_time,
                    bytes=self.get_transmitted_bytes(),
                )
                if self.transfer_finished:
                    if self.receive:
                        self.cmd_channel.on_file_received(filename)
                    else:
                        self.cmd_channel.on_file_sent(filename)
                elif self.receive:
                    self.cmd_channel.on_incomplete_file_received(filename)
                else:
                    self.cmd_channel.on_incomplete_file_sent(filename)
            self.cmd_channel._on_dtp_close()


class ThrottledDTPHandler(DTPHandler):
    """A DTPHandler subclass which wraps sending and receiving in a data
    counter and temporarily "sleeps" the channel so that you burst to no
    more than x Kb/sec average.

     - (int) read_limit: the maximum number of bytes to read (receive)
       in one second (defaults to 0 == no limit).

     - (int) write_limit: the maximum number of bytes to write (send)
       in one second (defaults to 0 == no limit).

     - (bool) auto_sized_buffers: this option only applies when read
       and/or write limits are specified. When enabled it bumps down
       the data buffer sizes so that they are never greater than read
       and write limits which results in a less bursty and smoother
       throughput (default: True).
    """

    read_limit = 0
    write_limit = 0
    auto_sized_buffers = True

    def __init__(self, sock, cmd_channel):
        super().__init__(sock, cmd_channel)
        self._timenext = 0
        self._datacount = 0
        self.sleeping = False
        self._throttler = None
        if self.auto_sized_buffers:
            if self.read_limit:
                while self.ac_in_buffer_size > self.read_limit:
                    self.ac_in_buffer_size /= 2
            if self.write_limit:
                while self.ac_out_buffer_size > self.write_limit:
                    self.ac_out_buffer_size /= 2
        self.ac_in_buffer_size = int(self.ac_in_buffer_size)
        self.ac_out_buffer_size = int(self.ac_out_buffer_size)

    def __repr__(self):
        return DTPHandler.__repr__(self)

    def use_sendfile(self):
        return False

    def recv(self, buffer_size):
        chunk = super().recv(buffer_size)
        if self.read_limit:
            self._throttle_bandwidth(len(chunk), self.read_limit)
        return chunk

    def send(self, data):
        num_sent = super().send(data)
        if self.write_limit:
            self._throttle_bandwidth(num_sent, self.write_limit)
        return num_sent

    def _cancel_throttler(self):
        if self._throttler is not None and not self._throttler.cancelled:
            self._throttler.cancel()

    def _throttle_bandwidth(self, len_chunk, max_speed):
        """A method which counts data transmitted so that you burst to
        no more than x Kb/sec average.
        """
        self._datacount += len_chunk
        if self._datacount >= max_speed:
            self._datacount = 0
            now = timer()
            sleepfor = (self._timenext - now) * 2
            if sleepfor > 0:
                # we've passed bandwidth limits
                def unsleep():
                    if self.receive:
                        event = self.ioloop.READ
                    else:
                        event = self.ioloop.WRITE
                    self.add_channel(events=event)

                self.del_channel()
                self._cancel_throttler()
                self._throttler = self.ioloop.call_later(
                    sleepfor, unsleep, _errback=self.handle_error
                )
            self._timenext = now + 1

    def close(self):
        self._cancel_throttler()
        super().close()
