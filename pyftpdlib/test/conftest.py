# Copyright (C) 2007 Giampaolo Rodola' <g.rodola@gmail.com>.
# Use of this source code is governed by MIT license that can be
# found in the LICENSE file.

"""
pytest config file (file name has special meaning), executed before
running tests.

In here we tell pytest to execute setup/teardown functions before/after
each unit-test. We do so to make sure no orphaned resources are left
behind.

In unittest terms, this is equivalent to implicitly defining setUp(),
tearDown(), setUpClass(), tearDownClass() methods for each test class.
"""

import atexit
import os
import threading
import warnings

import psutil
import pytest

from pyftpdlib.ioloop import IOLoop

from . import POSIX
from . import ROOT_DIR
from . import TESTFN_PREFIX
from . import safe_rmpath

# set it to True to raise an exception instead of warning
FAIL = False
this_proc = psutil.Process()


def collect_resources():
    res = {}
    res["threads"] = set(threading.enumerate())
    if POSIX:
        res["num_fds"] = this_proc.num_fds()
    # res["cons"] = set(this_proc.net_connections(kind="all"))
    # res["files"] = set(this_proc.open_files())
    return res


def warn(msg):
    if FAIL:
        raise RuntimeError(msg)
    warnings.warn(msg, ResourceWarning, stacklevel=3)


def assert_closed_resources(setup_ctx, request):
    if request.session.testsfailed:
        return  # no need to warn if test already failed

    before = setup_ctx.copy()
    after = collect_resources()
    for key, value in before.items():
        if key.startswith("_"):
            continue
        msg = (
            f"{setup_ctx['_origin']!r} left some unclosed {key!r} resources"
            " behind: "
        )
        extra = after[key] - before[key]
        if extra:
            if isinstance(value, set):
                msg += repr(extra)
                warn(msg)
            elif extra > 0:  # unused, here just in case we extend it later
                msg += f"before={before[key]!r}, after={after[key]!r}"
                warn(msg)


def assert_closed_ioloop():
    inst = IOLoop.instance()
    if inst.socket_map:
        warn(f"unclosed ioloop socket map {inst.socket_map}")
    if inst.sched._tasks:
        warn(f"unclosed ioloop tasks {inst.sched._tasks}")


# ---


def setup_method(origin):
    ctx = collect_resources()
    ctx["_origin"] = origin
    return ctx


def teardown_method(setup_ctx, request):
    assert_closed_resources(setup_ctx, request)
    assert_closed_ioloop()


@pytest.fixture(autouse=True, scope="function")
def for_each_test_method(request):
    ctx = setup_method(request.node.nodeid)
    request.addfinalizer(lambda: teardown_method(ctx, request))


@atexit.register
def on_exit():
    for name in os.listdir(ROOT_DIR):
        if name.startswith(TESTFN_PREFIX):
            safe_rmpath(os.path.join(ROOT_DIR, name))
