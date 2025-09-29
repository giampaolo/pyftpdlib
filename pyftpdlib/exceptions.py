# Copyright (C) 2007 Giampaolo Rodola' <g.rodola@gmail.com>.
# Use of this source code is governed by MIT license that can be
# found in the LICENSE file.

__all__ = ["AuthenticationFailed", "AuthorizerError", "FilesystemError"]


class AuthorizerError(Exception):
    """Base class for authorizer exceptions."""


class AuthenticationFailed(Exception):
    """Exception raised when authentication fails for any reason."""


class FilesystemError(Exception):
    """Custom class for filesystem-related exceptions.
    You can raise this from an AbstractedFS subclass in order to
    send a customized error string to the client.
    """


class _RetryError(Exception):
    """Raised when a socket operation would block, and hence it should
    be retried at a later time.
    """


class _FileReadWriteError(OSError):
    """Exception raised when reading or writing a file during a transfer."""


class _GiveUpOnSendfile(Exception):
    """Exception raised in case use of sendfile() fails on first try,
    in which case send() will be used.
    """
