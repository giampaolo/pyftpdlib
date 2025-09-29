# Copyright (C) 2007 Giampaolo Rodola' <g.rodola@gmail.com>.
# Use of this source code is governed by MIT license that can be
# found in the LICENSE file.

import os

proto_cmds = {
    "ABOR": dict(
        perm=None, auth=True, arg=False, help="Syntax: ABOR (abort transfer)."
    ),
    "ALLO": dict(
        perm=None,
        auth=True,
        arg=True,
        help="Syntax: ALLO <SP> bytes (noop; allocate storage).",
    ),
    "APPE": dict(
        perm="a",
        auth=True,
        arg=True,
        help="Syntax: APPE <SP> file-name (append data to file).",
    ),
    "CDUP": dict(
        perm="e",
        auth=True,
        arg=False,
        help="Syntax: CDUP (go to parent directory).",
    ),
    "CWD": dict(
        perm="e",
        auth=True,
        arg=None,
        help="Syntax: CWD [<SP> dir-name] (change working directory).",
    ),
    "DELE": dict(
        perm="d",
        auth=True,
        arg=True,
        help="Syntax: DELE <SP> file-name (delete file).",
    ),
    "EPRT": dict(
        perm=None,
        auth=True,
        arg=True,
        help="Syntax: EPRT <SP> |proto|ip|port| (extended active mode).",
    ),
    "EPSV": dict(
        perm=None,
        auth=True,
        arg=None,
        help='Syntax: EPSV [<SP> proto/"ALL"] (extended passive mode).',
    ),
    "FEAT": dict(
        perm=None,
        auth=False,
        arg=False,
        help="Syntax: FEAT (list all new features supported).",
    ),
    "HELP": dict(
        perm=None,
        auth=False,
        arg=None,
        help="Syntax: HELP [<SP> cmd] (show help).",
    ),
    "LIST": dict(
        perm="l",
        auth=True,
        arg=None,
        help="Syntax: LIST [<SP> path] (list files).",
    ),
    "MDTM": dict(
        perm="l",
        auth=True,
        arg=True,
        help="Syntax: MDTM [<SP> path] (file last modification time).",
    ),
    "MFMT": dict(
        perm="T",
        auth=True,
        arg=True,
        help=(
            "Syntax: MFMT <SP> timeval <SP> path (file update last "
            "modification time)."
        ),
    ),
    "MLSD": dict(
        perm="l",
        auth=True,
        arg=None,
        help="Syntax: MLSD [<SP> path] (list directory).",
    ),
    "MLST": dict(
        perm="l",
        auth=True,
        arg=None,
        help="Syntax: MLST [<SP> path] (show information about path).",
    ),
    "MODE": dict(
        perm=None,
        auth=True,
        arg=True,
        help="Syntax: MODE <SP> mode (noop; set data transfer mode).",
    ),
    "MKD": dict(
        perm="m",
        auth=True,
        arg=True,
        help="Syntax: MKD <SP> path (create directory).",
    ),
    "NLST": dict(
        perm="l",
        auth=True,
        arg=None,
        help="Syntax: NLST [<SP> path] (list path in a compact form).",
    ),
    "NOOP": dict(
        perm=None,
        auth=False,
        arg=False,
        help="Syntax: NOOP (just do nothing).",
    ),
    "OPTS": dict(
        perm=None,
        auth=True,
        arg=True,
        help="Syntax: OPTS <SP> cmd [<SP> option] (set option for command).",
    ),
    "PASS": dict(
        perm=None,
        auth=False,
        arg=None,
        help="Syntax: PASS [<SP> password] (set user password).",
    ),
    "PASV": dict(
        perm=None,
        auth=True,
        arg=False,
        help="Syntax: PASV (open passive data connection).",
    ),
    "PORT": dict(
        perm=None,
        auth=True,
        arg=True,
        help="Syntax: PORT <sp> h,h,h,h,p,p (open active data connection).",
    ),
    "PWD": dict(
        perm=None,
        auth=True,
        arg=False,
        help="Syntax: PWD (get current working directory).",
    ),
    "QUIT": dict(
        perm=None,
        auth=False,
        arg=False,
        help="Syntax: QUIT (quit current session).",
    ),
    "REIN": dict(
        perm=None, auth=True, arg=False, help="Syntax: REIN (flush account)."
    ),
    "REST": dict(
        perm=None,
        auth=True,
        arg=True,
        help="Syntax: REST <SP> offset (set file offset).",
    ),
    "RETR": dict(
        perm="r",
        auth=True,
        arg=True,
        help="Syntax: RETR <SP> file-name (retrieve a file).",
    ),
    "RMD": dict(
        perm="d",
        auth=True,
        arg=True,
        help="Syntax: RMD <SP> dir-name (remove directory).",
    ),
    "RNFR": dict(
        perm="f",
        auth=True,
        arg=True,
        help="Syntax: RNFR <SP> file-name (rename (source name)).",
    ),
    "RNTO": dict(
        perm="f",
        auth=True,
        arg=True,
        help="Syntax: RNTO <SP> file-name (rename (destination name)).",
    ),
    "SITE": dict(
        perm=None,
        auth=False,
        arg=True,
        help="Syntax: SITE <SP> site-command (execute SITE command).",
    ),
    "SITE HELP": dict(
        perm=None,
        auth=False,
        arg=None,
        help="Syntax: SITE HELP [<SP> cmd] (show SITE command help).",
    ),
    "SITE CHMOD": dict(
        perm="M",
        auth=True,
        arg=True,
        help="Syntax: SITE CHMOD <SP> mode path (change file mode).",
    ),
    "SIZE": dict(
        perm="l",
        auth=True,
        arg=True,
        help="Syntax: SIZE <SP> file-name (get file size).",
    ),
    "STAT": dict(
        perm="l",
        auth=False,
        arg=None,
        help="Syntax: STAT [<SP> path name] (server stats [list files]).",
    ),
    "STOR": dict(
        perm="w",
        auth=True,
        arg=True,
        help="Syntax: STOR <SP> file-name (store a file).",
    ),
    "STOU": dict(
        perm="w",
        auth=True,
        arg=None,
        help="Syntax: STOU [<SP> name] (store a file with a unique name).",
    ),
    "STRU": dict(
        perm=None,
        auth=True,
        arg=True,
        help="Syntax: STRU <SP> type (noop; set file structure).",
    ),
    "SYST": dict(
        perm=None,
        auth=False,
        arg=False,
        help="Syntax: SYST (get operating system type).",
    ),
    "TYPE": dict(
        perm=None,
        auth=True,
        arg=True,
        help="Syntax: TYPE <SP> [A | I] (set transfer type).",
    ),
    "USER": dict(
        perm=None,
        auth=False,
        arg=True,
        help="Syntax: USER <SP> user-name (set username).",
    ),
    "XCUP": dict(
        perm="e",
        auth=True,
        arg=False,
        help="Syntax: XCUP (obsolete; go to parent directory).",
    ),
    "XCWD": dict(
        perm="e",
        auth=True,
        arg=None,
        help="Syntax: XCWD [<SP> dir-name] (obsolete; change directory).",
    ),
    "XMKD": dict(
        perm="m",
        auth=True,
        arg=True,
        help="Syntax: XMKD <SP> dir-name (obsolete; create directory).",
    ),
    "XPWD": dict(
        perm=None,
        auth=True,
        arg=False,
        help="Syntax: XPWD (obsolete; get current dir).",
    ),
    "XRMD": dict(
        perm="d",
        auth=True,
        arg=True,
        help="Syntax: XRMD <SP> dir-name (obsolete; remove directory).",
    ),
}

if not hasattr(os, "chmod"):
    del proto_cmds["SITE CHMOD"]
