# Copyright (C) 2007 Giampaolo Rodola' <g.rodola@gmail.com>.
# Use of this source code is governed by MIT license that can be
# found in the LICENSE file.

import os
import stat
import tempfile
import time

from .utils import memoize

try:
    import grp
    import pwd
except ImportError:
    pwd = grp = None


__all__ = ["AbstractedFS", "FilesystemError"]


_months_map = {
    1: "Jan",
    2: "Feb",
    3: "Mar",
    4: "Apr",
    5: "May",
    6: "Jun",
    7: "Jul",
    8: "Aug",
    9: "Sep",
    10: "Oct",
    11: "Nov",
    12: "Dec",
}


# ===================================================================
# --- custom exceptions
# ===================================================================


class FilesystemError(Exception):
    """Custom class for filesystem-related exceptions.
    You can raise this from an AbstractedFS subclass in order to
    send a customized error string to the client.
    """


# ===================================================================
# --- base class
# ===================================================================


class AbstractedFS:
    """A class used to interact with the file system, providing a
    cross-platform interface compatible with both Windows and
    UNIX style filesystems where all paths use "/" separator.

    AbstractedFS distinguishes between "real" filesystem paths and
    "virtual" ftp paths emulating a UNIX chroot jail where the user
    can not escape its home directory (example: real "/home/user"
    path will be seen as "/" by the client)

    It also provides some utility methods and wraps around all os.*
    calls involving operations against the filesystem like creating
    files or removing directories.

    FilesystemError exception can be raised from within any of
    the methods below in order to send a customized error string
    to the client.
    """

    def __init__(self, root, cmd_channel):
        """
        - (str) root: the user "real" home directory (e.g. '/home/user')
        - (instance) cmd_channel: the FTPHandler class instance.
        """
        # Set initial current working directory.
        # By default initial cwd is set to "/" to emulate a chroot jail.
        # If a different behavior is desired (e.g. initial cwd = root,
        # to reflect the real filesystem) users overriding this class
        # are responsible to set _cwd attribute as necessary.
        self._cwd = "/"
        self._root = root
        self.cmd_channel = cmd_channel

    @property
    def root(self):
        """The user home directory."""
        return self._root

    @property
    def cwd(self):
        """The user current working directory."""
        return self._cwd

    @root.setter
    def root(self, path):
        self._root = path

    @cwd.setter
    def cwd(self, path):
        self._cwd = path

    # --- Pathname / conversion utilities

    @staticmethod
    def _isabs(path, _windows=os.name == "nt"):
        # Windows + Python 3.13: isabs() changed so that a path
        # starting with "/" is no longer considered absolute.
        # https://github.com/python/cpython/issues/44626
        # https://github.com/python/cpython/pull/113829/
        if _windows and path.startswith("/"):
            return True
        return os.path.isabs(path)

    def ftpnorm(self, ftppath):
        """Normalize a "virtual" ftp pathname (typically the raw string
        coming from client) depending on the current working directory.

        Example (having "/foo" as current working directory):
        >>> ftpnorm('bar')
        '/foo/bar'

        Note: directory separators are system independent ("/").
        Pathname returned is always absolutized.
        """
        if self._isabs(ftppath):
            p = os.path.normpath(ftppath)
        else:
            p = os.path.normpath(os.path.join(self.cwd, ftppath))
        # normalize string in a standard web-path notation having '/'
        # as separator.
        if os.sep == "\\":
            p = p.replace("\\", "/")
        # os.path.normpath supports UNC paths (e.g. "//a/b/c") but we
        # don't need them.  In case we get an UNC path we collapse
        # redundant separators appearing at the beginning of the string
        while p[:2] == "//":
            p = p[1:]
        # Anti path traversal: don't trust user input, in the event
        # that self.cwd is not absolute, return "/" as a safety measure.
        # This is for extra protection, maybe not really necessary.
        if not self._isabs(p):
            p = "/"
        return p

    def ftp2fs(self, ftppath):
        """Translate a "virtual" ftp pathname (typically the raw string
        coming from client) into equivalent absolute "real" filesystem
        pathname.

        Example (having "/home/user" as root directory):
        >>> ftp2fs("foo")
        '/home/user/foo'

        Note: directory separators are system dependent.
        """
        # as far as I know, it should always be path traversal safe...
        if os.path.normpath(self.root) == os.sep:
            return os.path.normpath(self.ftpnorm(ftppath))
        else:
            p = self.ftpnorm(ftppath)[1:]
            return os.path.normpath(os.path.join(self.root, p))

    def fs2ftp(self, fspath):
        """Translate a "real" filesystem pathname into equivalent
        absolute "virtual" ftp pathname depending on the user's
        root directory.

        Example (having "/home/user" as root directory):
        >>> fs2ftp("/home/user/foo")
        '/foo'

        As for ftpnorm, directory separators are system independent
        ("/") and pathname returned is always absolutized.

        On invalid pathnames escaping from user's root directory
        (e.g. "/home" when root is "/home/user") always return "/".
        """
        if self._isabs(fspath):
            p = os.path.normpath(fspath)
        else:
            p = os.path.normpath(os.path.join(self.root, fspath))
        if not self.validpath(p):
            return "/"
        p = p.replace(os.sep, "/")
        p = p[len(self.root) :]
        if not p.startswith("/"):
            p = "/" + p
        return p

    def validpath(self, path):
        """Check whether the path belongs to user's home directory.
        Expected argument is a "real" filesystem pathname.

        If path is a symbolic link it is resolved to check its real
        destination.

        Pathnames escaping from user's root directory are considered
        not valid.
        """
        root = self.realpath(self.root)
        path = self.realpath(path)
        if not root.endswith(os.sep):
            root += os.sep
        if not path.endswith(os.sep):
            path += os.sep
        return path[0 : len(root)] == root

    # --- Wrapper methods around open() and tempfile.mkstemp

    def open(self, filename, mode):
        """Open a file returning its handler."""
        return open(filename, mode)

    def mkstemp(self, suffix="", prefix="", dir=None, mode="wb"):
        """A wrap around tempfile.mkstemp creating a file with a unique
        name.  Unlike mkstemp it returns an object with a file-like
        interface.
        """

        class FileWrapper:

            def __init__(self, fd, name):
                self.file = fd
                self.name = name

            def __getattr__(self, attr):
                return getattr(self.file, attr)

        text = "b" not in mode
        # max number of tries to find out a unique file name
        tempfile.TMP_MAX = 50
        fd, name = tempfile.mkstemp(suffix, prefix, dir, text=text)
        file = os.fdopen(fd, mode)
        return FileWrapper(file, name)

    # --- Wrapper methods around os.* calls

    def chdir(self, path):
        """Change the current directory. If this method is overridden
        it is vital that `cwd` attribute gets set.
        """
        # note: process cwd will be reset by the caller
        os.chdir(path)
        self.cwd = self.fs2ftp(path)

    def mkdir(self, path):
        """Create the specified directory."""
        os.mkdir(path)

    def listdir(self, path):
        """List the content of a directory."""
        return os.listdir(path)

    def listdirinfo(self, path):
        """List the content of a directory."""
        return os.listdir(path)

    def rmdir(self, path):
        """Remove the specified directory."""
        os.rmdir(path)

    def remove(self, path):
        """Remove the specified file."""
        os.remove(path)

    def rename(self, src, dst):
        """Rename the specified src file to the dst filename."""
        os.rename(src, dst)

    def chmod(self, path, mode):
        """Change file/directory mode."""
        if not hasattr(os, "chmod"):
            raise NotImplementedError
        os.chmod(path, mode)

    def stat(self, path):
        """Perform a stat() system call on the given path."""
        return os.stat(path)

    def utime(self, path, timeval):
        """Perform a utime() call on the given path."""
        # utime expects a int/float (atime, mtime) in seconds
        # thus, setting both access and modify time to timeval
        return os.utime(path, (timeval, timeval))

    if hasattr(os, "lstat"):

        def lstat(self, path):
            """Like stat but does not follow symbolic links."""
            return os.lstat(path)

    else:
        lstat = stat

    if hasattr(os, "readlink"):

        def readlink(self, path):
            """Return a string representing the path to which a
            symbolic link points.
            """
            return os.readlink(path)

    # --- Wrapper methods around os.path.* calls

    def isfile(self, path):
        """Return True if path is a file."""
        return os.path.isfile(path)

    def islink(self, path):
        """Return True if path is a symbolic link."""
        return os.path.islink(path)

    def isdir(self, path):
        """Return True if path is a directory."""
        return os.path.isdir(path)

    def getsize(self, path):
        """Return the size of the specified file in bytes."""
        return os.path.getsize(path)

    def getmtime(self, path):
        """Return the last modified time as a number of seconds since
        the epoch."""
        return os.path.getmtime(path)

    def realpath(self, path):
        """Return the canonical version of path eliminating any
        symbolic links encountered in the path (if they are
        supported by the operating system).
        """
        return os.path.realpath(path)

    def lexists(self, path):
        """Return True if path refers to an existing path, including
        a broken or circular symbolic link.
        """
        return os.path.lexists(path)

    if pwd is not None:

        def get_user_by_uid(self, uid):
            """Return the username associated with user id.
            If this can't be determined return raw uid instead.
            On Windows just return "owner".
            """
            try:
                return pwd.getpwuid(uid).pw_name
            except KeyError:
                return uid

    else:

        def get_user_by_uid(self, uid):
            return "owner"

    if grp is not None:

        def get_group_by_gid(self, gid):
            """Return the group name associated with group id.
            If this can't be determined return raw gid instead.
            On Windows just return "group".
            """
            try:
                return grp.getgrgid(gid).gr_name
            except KeyError:
                return gid

    else:

        def get_group_by_gid(self, gid):
            return "group"

    # --- Listing utilities

    def format_list(self, basedir, listing, ignore_err=True):
        """Return an iterator object that yields the entries of given
        directory emulating the "/bin/ls -lA" UNIX command output.

         - (str) basedir: the absolute dirname.
         - (list) listing: the names of the entries in basedir
         - (bool) ignore_err: when False raise exception if os.lstat()
         call fails.

        On platforms which do not support the pwd and grp modules (such
        as Windows), ownership is printed as "owner" and "group" as a
        default, and number of hard links is always "1". On UNIX
        systems, the actual owner, group, and number of links are
        printed.

        This is how output appears to client:

        -rw-rw-rw-   1 owner   group    7045120 Sep 02  3:47 music.mp3
        drwxrwxrwx   1 owner   group          0 Aug 31 18:50 e-books
        -rw-rw-rw-   1 owner   group        380 Sep 02  3:40 module.py
        """

        @memoize
        def get_user_by_uid(uid):
            return self.get_user_by_uid(uid)

        @memoize
        def get_group_by_gid(gid):
            return self.get_group_by_gid(gid)

        if self.cmd_channel.use_gmt_times:
            timefunc = time.gmtime
        else:
            timefunc = time.localtime
        SIX_MONTHS = 180 * 24 * 60 * 60
        readlink = getattr(self, "readlink", None)
        now = time.time()
        for basename in listing:
            file = os.path.join(basedir, basename)
            try:
                st = self.lstat(file)
            except (OSError, FilesystemError):
                if ignore_err:
                    continue
                raise

            perms = stat.filemode(st.st_mode)  # permissions
            nlinks = st.st_nlink  # number of links to inode
            if not nlinks:  # non-posix system, let's use a bogus value
                nlinks = 1
            size = st.st_size  # file size
            uname = get_user_by_uid(st.st_uid)
            gname = get_group_by_gid(st.st_gid)
            mtime = timefunc(st.st_mtime)
            # if modification time > 6 months shows "month year"
            # else "month hh:mm";  this matches proftpd format, see:
            # https://github.com/giampaolo/pyftpdlib/issues/187
            fmtstr = "%d  %Y" if now - st.st_mtime > SIX_MONTHS else "%d %H:%M"
            try:
                mtimestr = "%s %s" % (
                    _months_map[mtime.tm_mon],
                    time.strftime(fmtstr, mtime),
                )
            except ValueError:
                # It could be raised if last mtime happens to be too
                # old (prior to year 1900) in which case we return
                # the current time as last mtime.
                mtime = timefunc()
                mtimestr = "%s %s" % (
                    _months_map[mtime.tm_mon],
                    time.strftime("%d %H:%M", mtime),
                )

            # same as stat.S_ISLNK(st.st_mode) but slighlty faster
            islink = (st.st_mode & 61440) == stat.S_IFLNK
            if islink and readlink is not None:
                # if the file is a symlink, resolve it, e.g.
                # "symlink -> realfile"
                try:
                    basename = basename + " -> " + readlink(file)
                except (OSError, FilesystemError):
                    if not ignore_err:
                        raise

            # formatting is matched with proftpd ls output
            line = "%s %3s %-8s %-8s %8s %s %s\r\n" % (
                perms,
                nlinks,
                uname,
                gname,
                size,
                mtimestr,
                basename,
            )
            yield line.encode(
                self.cmd_channel.encoding, self.cmd_channel.unicode_errors
            )

    def format_mlsx(self, basedir, listing, perms, facts, ignore_err=True):
        """Return an iterator object that yields the entries of a given
        directory or of a single file in a form suitable with MLSD and
        MLST commands.

        Every entry includes a list of "facts" referring the listed
        element.  See RFC-3659, chapter 7, to see what every single
        fact stands for.

         - (str) basedir: the absolute dirname.
         - (list) listing: the names of the entries in basedir
         - (str) perms: the string referencing the user permissions.
         - (str) facts: the list of "facts" to be returned.
         - (bool) ignore_err: when False raise exception if os.stat()
         call fails.

        Note that "facts" returned may change depending on the platform
        and on what user specified by using the OPTS command.

        This is how output could appear to the client issuing
        a MLSD request:

        type=file;size=156;perm=r;modify=20071029155301;unique=8012; music.mp3
        type=dir;size=0;perm=el;modify=20071127230206;unique=801e33; ebooks
        type=file;size=211;perm=r;modify=20071103093626;unique=192; module.py
        """
        if self.cmd_channel.use_gmt_times:
            timefunc = time.gmtime
        else:
            timefunc = time.localtime
        permdir = "".join([x for x in perms if x not in "arw"])
        permfile = "".join([x for x in perms if x not in "celmp"])
        if ("w" in perms) or ("a" in perms) or ("f" in perms):
            permdir += "c"
        if "d" in perms:
            permdir += "p"
        show_type = "type" in facts
        show_perm = "perm" in facts
        show_size = "size" in facts
        show_modify = "modify" in facts
        show_create = "create" in facts
        show_mode = "unix.mode" in facts
        show_uid = "unix.uid" in facts
        show_gid = "unix.gid" in facts
        show_unique = "unique" in facts
        for basename in listing:
            retfacts = {}
            file = os.path.join(basedir, basename)
            # in order to properly implement 'unique' fact (RFC-3659,
            # chapter 7.5.2) we are supposed to follow symlinks, hence
            # use os.stat() instead of os.lstat()
            try:
                st = self.stat(file)
            except (OSError, FilesystemError):
                if ignore_err:
                    continue
                raise
            # type + perm
            # same as stat.S_ISDIR(st.st_mode) but slightly faster
            isdir = (st.st_mode & 61440) == stat.S_IFDIR
            if isdir:
                if show_type:
                    if basename == ".":
                        retfacts["type"] = "cdir"
                    elif basename == "..":
                        retfacts["type"] = "pdir"
                    else:
                        retfacts["type"] = "dir"
                if show_perm:
                    retfacts["perm"] = permdir
            else:
                if show_type:
                    retfacts["type"] = "file"
                if show_perm:
                    retfacts["perm"] = permfile
            if show_size:
                retfacts["size"] = st.st_size  # file size
            # last modification time
            if show_modify:
                try:
                    retfacts["modify"] = time.strftime(
                        "%Y%m%d%H%M%S", timefunc(st.st_mtime)
                    )
                # it could be raised if last mtime happens to be too old
                # (prior to year 1900)
                except ValueError:
                    pass
            if show_create:
                # on Windows we can provide also the creation time
                try:
                    retfacts["create"] = time.strftime(
                        "%Y%m%d%H%M%S", timefunc(st.st_ctime)
                    )
                except ValueError:
                    pass
            # UNIX only
            if show_mode:
                retfacts["unix.mode"] = oct(st.st_mode & 511)
            if show_uid:
                retfacts["unix.uid"] = st.st_uid
            if show_gid:
                retfacts["unix.gid"] = st.st_gid

            # We provide unique fact (see RFC-3659, chapter 7.5.2) on
            # posix platforms only; we get it by mixing st_dev and
            # st_ino values which should be enough for granting an
            # uniqueness for the file listed.
            # The same approach is used by pure-ftpd.
            # Implementors who want to provide unique fact on other
            # platforms should use some platform-specific method (e.g.
            # on Windows NTFS filesystems MTF records could be used).
            if show_unique:
                retfacts["unique"] = f"{st.st_dev:x}g{st.st_ino:x}"

            # facts can be in any order but we sort them by name
            factstring = "".join(
                [f"{x}={retfacts[x]};" for x in sorted(retfacts.keys())]
            )
            line = f"{factstring} {basename}\r\n"
            yield line.encode(
                self.cmd_channel.encoding, self.cmd_channel.unicode_errors
            )


# ===================================================================
# --- platform specific implementation
# ===================================================================

if os.name == "posix":
    __all__ += ["UnixFilesystem"]

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
