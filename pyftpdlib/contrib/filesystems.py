#!/usr/bin/env python
# $Id$

from pyftpdlib.ftpserver import AbstractedFS

__all__ = ['UnixFilesystem']


class UnixFilesystem(AbstractedFS):
    """Represents the real UNIX filesystem.

    Differently from AbstractedFS the client will login into
    /home/<username> and will be able to escape its home directory
    and navigate the real filesystem.
    """

    def __init__(self, root, cmd_channel):
        AbstractedFS.__init__(self, root, cmd_channel)
        # initial cwd was set to "/" to emulate a chroot jail
        self.cwd = root

    def ftp2fs(self, ftppath):
        return self.ftpnorm(ftppath)

    def fs2ftp(self, fspath):
        return fspath

    def validpath(self, path):
        # validpath was used to check symlinks escaping user home
        # directory; this is no longer necessary.
        return True

