# Copyright (C) 2007 Giampaolo Rodola' <g.rodola@gmail.com>.
# Use of this source code is governed by MIT license that can be
# found in the LICENSE file.

import os

from pyftpdlib.exceptions import _FileReadWriteError

CR_BYTE = ord("\r")

__all__ = ["BufferedIteratorProducer", "FileProducer"]


class FileProducer:
    """Producer wrapper for file[-like] objects."""

    buffer_size = 65536

    def __init__(self, file, type):
        """Initialize the producer with a data_wrapper appropriate to TYPE.

        - (file) file: the file[-like] object.
        - (str) type: the current TYPE, 'a' (ASCII) or 'i' (binary).
        """
        self.file = file
        self.type = type
        self._prev_chunk_endswith_cr = False
        if type == "a" and os.linesep != "\r\n":
            self._data_wrapper = self._posix_ascii_data_wrapper
        else:
            self._data_wrapper = None

    def _posix_ascii_data_wrapper(self, chunk):
        """The data wrapper used for sending data in ASCII mode on
        systems using a single line terminator, handling those cases
        where CRLF ('\r\n') gets delivered in two chunks.
        """
        chunk = bytearray(chunk)
        pos = 0
        if self._prev_chunk_endswith_cr and chunk.startswith(b"\n"):
            pos += 1
        while True:
            pos = chunk.find(b"\n", pos)
            if pos == -1:
                break
            if chunk[pos - 1] != CR_BYTE:
                chunk.insert(pos, CR_BYTE)
                pos += 1
            pos += 1
        self._prev_chunk_endswith_cr = chunk.endswith(b"\r")
        return chunk

    def more(self):
        """Attempt a chunk of data of size self.buffer_size."""
        try:
            data = self.file.read(self.buffer_size)
        except OSError as err:
            raise _FileReadWriteError(err) from err
        else:
            if self._data_wrapper is not None:
                data = self._data_wrapper(data)
            return data


class BufferedIteratorProducer:
    """Producer for iterator objects with buffer capabilities."""

    # how many times iterator.next() will be called before
    # returning some data
    loops = 20

    def __init__(self, iterator):
        self.iterator = iterator

    def more(self):
        """Attempt a chunk of data from iterator by calling
        its next() method different times.
        """
        buffer = []
        for _ in range(self.loops):
            try:
                buffer.append(next(self.iterator))
            except StopIteration:
                break
        return b"".join(buffer)
