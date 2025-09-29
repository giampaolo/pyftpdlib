# Copyright (C) 2007 Giampaolo Rodola' <g.rodola@gmail.com>.
# Use of this source code is governed by MIT license that can be
# found in the LICENSE file.


class AuthorizerError(Exception):
    """Base class for authorizer exceptions."""


class AuthenticationFailed(Exception):
    """Exception raised when authentication fails for any reason."""


class _FileReadWriteError(OSError):
    """Exception raised when reading or writing a file during a transfer."""


class _GiveUpOnSendfile(Exception):
    """Exception raised in case use of sendfile() fails on first try,
    in which case send() will be used.
    """
