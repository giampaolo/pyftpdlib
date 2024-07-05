# Copyright (C) 2007 Giampaolo Rodola' <g.rodola@gmail.com>.
# Use of this source code is governed by MIT license that can be
# found in the LICENSE file.

import os
import random
import string
import sys
import warnings

import pytest

from pyftpdlib.authorizers import AuthenticationFailed
from pyftpdlib.authorizers import AuthorizerError
from pyftpdlib.authorizers import DummyAuthorizer

from . import HOME
from . import PASSWD
from . import POSIX
from . import USER
from . import WINDOWS
from . import PyftpdlibTestCase
from . import touch


if POSIX:
    import pwd

    try:
        from pyftpdlib.authorizers import UnixAuthorizer
    except ImportError:
        UnixAuthorizer = None
else:
    UnixAuthorizer = None

if WINDOWS:
    from pywintypes import error as Win32ExtError

    from pyftpdlib.authorizers import WindowsAuthorizer
else:
    WindowsAuthorizer = None


class TestDummyAuthorizer(PyftpdlibTestCase):
    """Tests for DummyAuthorizer class."""

    # temporarily change warnings to exceptions for the purposes of testing
    def setUp(self):
        super().setUp()
        self.tempdir = os.path.abspath(self.get_testfn())
        self.subtempdir = os.path.join(self.tempdir, self.get_testfn())
        self.tempfile = os.path.join(self.tempdir, self.get_testfn())
        self.subtempfile = os.path.join(self.subtempdir, self.get_testfn())
        os.mkdir(self.tempdir)
        os.mkdir(self.subtempdir)
        touch(self.tempfile)
        touch(self.subtempfile)
        warnings.filterwarnings("error")

    def tearDown(self):
        os.remove(self.tempfile)
        os.remove(self.subtempfile)
        os.rmdir(self.subtempdir)
        os.rmdir(self.tempdir)
        warnings.resetwarnings()
        super().tearDown()

    def test_common_methods(self):
        auth = DummyAuthorizer()
        # create user
        auth.add_user(USER, PASSWD, HOME)
        auth.add_anonymous(HOME)
        # check credentials
        auth.validate_authentication(USER, PASSWD, None)
        with pytest.raises(AuthenticationFailed):
            auth.validate_authentication(USER, 'wrongpwd', None)
        auth.validate_authentication('anonymous', 'foo', None)
        auth.validate_authentication('anonymous', '', None)  # empty passwd
        # remove them
        auth.remove_user(USER)
        auth.remove_user('anonymous')
        # raise exc if user does not exists
        with pytest.raises(KeyError):
            auth.remove_user(USER)
        # raise exc if path does not exist
        with pytest.raises(ValueError, match='no such directory'):
            auth.add_user(USER, PASSWD, '?:\\')
        with pytest.raises(ValueError, match='no such directory'):
            auth.add_anonymous('?:\\')
        # raise exc if user already exists
        auth.add_user(USER, PASSWD, HOME)
        auth.add_anonymous(HOME)
        with pytest.raises(ValueError, match=f'user {USER!r} already exists'):
            auth.add_user(USER, PASSWD, HOME)
        with pytest.raises(
            ValueError, match="user 'anonymous' already exists"
        ):
            auth.add_anonymous(HOME)
        auth.remove_user(USER)
        auth.remove_user('anonymous')
        # raise on wrong permission
        with pytest.raises(ValueError, match="no such permission"):
            auth.add_user(USER, PASSWD, HOME, perm='?')
        with pytest.raises(ValueError, match="no such permission"):
            auth.add_anonymous(HOME, perm='?')
        # expect warning on write permissions assigned to anonymous user
        for x in "adfmw":
            with pytest.raises(
                RuntimeWarning,
                match="write permissions assigned to anonymous user.",
            ):
                auth.add_anonymous(HOME, perm=x)

    def test_override_perm_interface(self):
        auth = DummyAuthorizer()
        auth.add_user(USER, PASSWD, HOME, perm='elr')
        # raise exc if user does not exists
        with pytest.raises(KeyError):
            auth.override_perm(USER + 'w', HOME, 'elr')
        # raise exc if path does not exist or it's not a directory
        with pytest.raises(ValueError, match='no such directory'):
            auth.override_perm(USER, '?:\\', 'elr')
        with pytest.raises(ValueError, match='no such directory'):
            auth.override_perm(USER, self.tempfile, 'elr')
        # raise on wrong permission
        with pytest.raises(ValueError, match="no such permission"):
            auth.override_perm(USER, HOME, perm='?')
        # expect warning on write permissions assigned to anonymous user
        auth.add_anonymous(HOME)
        for p in "adfmw":
            with pytest.raises(
                RuntimeWarning,
                match="write permissions assigned to anonymous user.",
            ):
                auth.override_perm('anonymous', HOME, p)
        # raise on attempt to override home directory permissions
        with pytest.raises(
            ValueError, match="can't override home directory permissions"
        ):
            auth.override_perm(USER, HOME, perm='w')
        # raise on attempt to override a path escaping home directory
        if os.path.dirname(HOME) != HOME:
            with pytest.raises(
                ValueError, match="path escapes user home directory"
            ):
                auth.override_perm(USER, os.path.dirname(HOME), perm='w')
        # try to re-set an overridden permission
        auth.override_perm(USER, self.tempdir, perm='w')
        auth.override_perm(USER, self.tempdir, perm='wr')

    def test_override_perm_recursive_paths(self):
        auth = DummyAuthorizer()
        auth.add_user(USER, PASSWD, HOME, perm='elr')
        assert not auth.has_perm(USER, 'w', self.tempdir)
        auth.override_perm(USER, self.tempdir, perm='w', recursive=True)
        assert not auth.has_perm(USER, 'w', HOME)
        assert auth.has_perm(USER, 'w', self.tempdir)
        assert auth.has_perm(USER, 'w', self.tempfile)
        assert auth.has_perm(USER, 'w', self.subtempdir)
        assert auth.has_perm(USER, 'w', self.subtempfile)

        assert not auth.has_perm(USER, 'w', HOME + '@')
        assert not auth.has_perm(USER, 'w', self.tempdir + '@')
        path = os.path.join(
            self.tempdir + '@', os.path.basename(self.tempfile)
        )
        assert not auth.has_perm(USER, 'w', path)
        # test case-sensitiveness
        if (os.name in ('nt', 'ce')) or (sys.platform == 'cygwin'):
            assert auth.has_perm(USER, 'w', self.tempdir.upper())

    def test_override_perm_not_recursive_paths(self):
        auth = DummyAuthorizer()
        auth.add_user(USER, PASSWD, HOME, perm='elr')
        assert not auth.has_perm(USER, 'w', self.tempdir)
        auth.override_perm(USER, self.tempdir, perm='w')
        assert not auth.has_perm(USER, 'w', HOME)
        assert auth.has_perm(USER, 'w', self.tempdir)
        assert auth.has_perm(USER, 'w', self.tempfile)
        assert not auth.has_perm(USER, 'w', self.subtempdir)
        assert not auth.has_perm(USER, 'w', self.subtempfile)

        assert not auth.has_perm(USER, 'w', HOME + '@')
        assert not auth.has_perm(USER, 'w', self.tempdir + '@')
        path = os.path.join(
            self.tempdir + '@', os.path.basename(self.tempfile)
        )
        assert not auth.has_perm(USER, 'w', path)
        # test case-sensitiveness
        if (os.name in ('nt', 'ce')) or (sys.platform == 'cygwin'):
            assert auth.has_perm(USER, 'w', self.tempdir.upper())


class _SharedAuthorizerTests:
    """Tests valid for both UnixAuthorizer and WindowsAuthorizer for
    those parts which share the same API.
    """

    authorizer_class = None
    # --- utils

    def get_users(self):
        return self.authorizer_class._get_system_users()

    @staticmethod
    def get_current_user():
        if POSIX:
            return pwd.getpwuid(os.getuid()).pw_name
        else:
            return os.environ['USERNAME']

    @staticmethod
    def get_current_user_homedir():
        if POSIX:
            return pwd.getpwuid(os.getuid()).pw_dir
        else:
            return os.environ['USERPROFILE']

    def get_nonexistent_user(self):
        # return a user which does not exist on the system
        users = self.get_users()
        letters = string.ascii_lowercase
        while True:
            user = ''.join([random.choice(letters) for i in range(10)])
            if user not in users:
                return user

    def assertRaisesWithMsg(self, excClass, msg, callableObj, *args, **kwargs):
        try:
            callableObj(*args, **kwargs)
        except excClass as err:
            if str(err) == msg:
                return
            raise self.failureException(f"{err!s} != {msg}")
        else:
            if hasattr(excClass, '__name__'):
                excName = excClass.__name__
            else:
                excName = str(excClass)
            raise self.failureException(f"{excName} not raised")

    # --- /utils

    def test_get_home_dir(self):
        auth = self.authorizer_class()
        home = auth.get_home_dir(self.get_current_user())
        nonexistent_user = self.get_nonexistent_user()
        assert os.path.isdir(home)
        if auth.has_user('nobody'):
            home = auth.get_home_dir('nobody')
        with pytest.raises(AuthorizerError):
            auth.get_home_dir(nonexistent_user)

    def test_has_user(self):
        auth = self.authorizer_class()
        current_user = self.get_current_user()
        nonexistent_user = self.get_nonexistent_user()
        assert auth.has_user(current_user)
        assert not auth.has_user(nonexistent_user)
        auth = self.authorizer_class(rejected_users=[current_user])
        assert not auth.has_user(current_user)

    def test_validate_authentication(self):
        # can't test for actual success in case of valid authentication
        # here as we don't have the user password
        if self.authorizer_class.__name__ == 'UnixAuthorizer':
            auth = self.authorizer_class(require_valid_shell=False)
        else:
            auth = self.authorizer_class()
        current_user = self.get_current_user()
        nonexistent_user = self.get_nonexistent_user()
        with pytest.raises(AuthenticationFailed):
            auth.validate_authentication(
                current_user,
                'wrongpasswd',
                None,
            )
        with pytest.raises(AuthenticationFailed):
            auth.validate_authentication(
                nonexistent_user,
                'bar',
                None,
            )

    def test_impersonate_user(self):
        auth = self.authorizer_class()
        nonexistent_user = self.get_nonexistent_user()
        try:
            if self.authorizer_class.__name__ == 'UnixAuthorizer':
                auth.impersonate_user(self.get_current_user(), '')
                with pytest.raises(AuthorizerError):
                    auth.impersonate_user(
                        nonexistent_user,
                        'pwd',
                    )
            else:
                with pytest.raises(Win32ExtError):
                    auth.impersonate_user(
                        nonexistent_user,
                        'pwd',
                    )
                with pytest.raises(Win32ExtError):
                    auth.impersonate_user(
                        self.get_current_user(),
                        '',
                    )
        finally:
            auth.terminate_impersonation('')

    def test_terminate_impersonation(self):
        auth = self.authorizer_class()
        auth.terminate_impersonation('')
        auth.terminate_impersonation('')

    def test_get_perms(self):
        auth = self.authorizer_class(global_perm='elr')
        assert 'r' in auth.get_perms(self.get_current_user())
        assert 'w' not in auth.get_perms(self.get_current_user())

    def test_has_perm(self):
        auth = self.authorizer_class(global_perm='elr')
        assert auth.has_perm(self.get_current_user(), 'r')
        assert not auth.has_perm(self.get_current_user(), 'w')

    def test_messages(self):
        auth = self.authorizer_class(msg_login="login", msg_quit="quit")
        assert auth.get_msg_login, "login"
        assert auth.get_msg_quit, "quit"

    def test_error_options(self):
        wrong_user = self.get_nonexistent_user()
        self.assertRaisesWithMsg(
            AuthorizerError,
            "rejected_users and allowed_users options are mutually exclusive",
            self.authorizer_class,
            allowed_users=['foo'],
            rejected_users=['bar'],
        )
        self.assertRaisesWithMsg(
            AuthorizerError,
            'invalid username "anonymous"',
            self.authorizer_class,
            allowed_users=['anonymous'],
        )
        self.assertRaisesWithMsg(
            AuthorizerError,
            'invalid username "anonymous"',
            self.authorizer_class,
            rejected_users=['anonymous'],
        )
        self.assertRaisesWithMsg(
            AuthorizerError,
            f'unknown user {wrong_user}',
            self.authorizer_class,
            allowed_users=[wrong_user],
        )
        self.assertRaisesWithMsg(
            AuthorizerError,
            f'unknown user {wrong_user}',
            self.authorizer_class,
            rejected_users=[wrong_user],
        )

    def test_override_user_password(self):
        auth = self.authorizer_class()
        user = self.get_current_user()
        auth.override_user(user, password='foo')
        auth.validate_authentication(user, 'foo', None)
        with pytest.raises(AuthenticationFailed):
            auth.validate_authentication(
                user,
                'bar',
                None,
            )
        # make sure other settings keep using default values
        assert auth.get_home_dir(user) == self.get_current_user_homedir()
        assert auth.get_perms(user) == "elradfmwMT"
        assert auth.get_msg_login(user) == "Login successful."
        assert auth.get_msg_quit(user) == "Goodbye."

    def test_override_user_homedir(self):
        auth = self.authorizer_class()
        user = self.get_current_user()
        dir = os.path.dirname(os.getcwd())
        auth.override_user(user, homedir=dir)
        assert auth.get_home_dir(user) == dir
        # make sure other settings keep using default values
        # self.assertEqual(auth.get_home_dir(user),
        #                  self.get_current_user_homedir())
        assert auth.get_perms(user) == "elradfmwMT"
        assert auth.get_msg_login(user) == "Login successful."
        assert auth.get_msg_quit(user) == "Goodbye."

    def test_override_user_perm(self):
        auth = self.authorizer_class()
        user = self.get_current_user()
        auth.override_user(user, perm="elr")
        assert auth.get_perms(user) == "elr"
        # make sure other settings keep using default values
        assert auth.get_home_dir(user) == self.get_current_user_homedir()
        # self.assertEqual(auth.get_perms(user), "elradfmwMT")
        assert auth.get_msg_login(user) == "Login successful."
        assert auth.get_msg_quit(user) == "Goodbye."

    def test_override_user_msg_login_quit(self):
        auth = self.authorizer_class()
        user = self.get_current_user()
        auth.override_user(user, msg_login="foo", msg_quit="bar")
        assert auth.get_msg_login(user) == "foo"
        assert auth.get_msg_quit(user) == "bar"
        # make sure other settings keep using default values
        assert auth.get_home_dir(user) == self.get_current_user_homedir()
        assert auth.get_perms(user) == "elradfmwMT"
        # self.assertEqual(auth.get_msg_login(user), "Login successful.")
        # self.assertEqual(auth.get_msg_quit(user), "Goodbye.")

    def test_override_user_errors(self):
        if self.authorizer_class.__name__ == 'UnixAuthorizer':
            auth = self.authorizer_class(require_valid_shell=False)
        else:
            auth = self.authorizer_class()
        this_user = self.get_current_user()
        for x in self.get_users():
            if x != this_user:
                another_user = x
                break
        nonexistent_user = self.get_nonexistent_user()
        self.assertRaisesWithMsg(
            AuthorizerError,
            "at least one keyword argument must be specified",
            auth.override_user,
            this_user,
        )
        self.assertRaisesWithMsg(
            AuthorizerError,
            f'no such user {nonexistent_user}',
            auth.override_user,
            nonexistent_user,
            perm='r',
        )
        if self.authorizer_class.__name__ == 'UnixAuthorizer':
            auth = self.authorizer_class(
                allowed_users=[this_user], require_valid_shell=False
            )
        else:
            auth = self.authorizer_class(allowed_users=[this_user])
        auth.override_user(this_user, perm='r')
        self.assertRaisesWithMsg(
            AuthorizerError,
            f'{another_user} is not an allowed user',
            auth.override_user,
            another_user,
            perm='r',
        )
        if self.authorizer_class.__name__ == 'UnixAuthorizer':
            auth = self.authorizer_class(
                rejected_users=[this_user], require_valid_shell=False
            )
        else:
            auth = self.authorizer_class(rejected_users=[this_user])
        auth.override_user(another_user, perm='r')
        self.assertRaisesWithMsg(
            AuthorizerError,
            f'{this_user} is not an allowed user',
            auth.override_user,
            this_user,
            perm='r',
        )
        self.assertRaisesWithMsg(
            AuthorizerError,
            "can't assign password to anonymous user",
            auth.override_user,
            "anonymous",
            password='foo',
        )


# =====================================================================
# --- UNIX authorizer
# =====================================================================


@pytest.mark.skipif(not POSIX, reason="UNIX only")
@pytest.mark.skipif(
    UnixAuthorizer is None, reason="UnixAuthorizer class not available"
)
class TestUnixAuthorizer(_SharedAuthorizerTests, PyftpdlibTestCase):
    """Unix authorizer specific tests."""

    authorizer_class = UnixAuthorizer

    def setUp(self):
        super().setUp()
        try:
            UnixAuthorizer()
        except AuthorizerError:  # not root
            self.skipTest("need root access")

    def test_get_perms_anonymous(self):
        auth = UnixAuthorizer(
            global_perm='elr', anonymous_user=self.get_current_user()
        )
        assert 'e' in auth.get_perms('anonymous')
        assert 'w' not in auth.get_perms('anonymous')
        warnings.filterwarnings("ignore")
        auth.override_user('anonymous', perm='w')
        warnings.resetwarnings()
        assert 'w' in auth.get_perms('anonymous')

    def test_has_perm_anonymous(self):
        auth = UnixAuthorizer(
            global_perm='elr', anonymous_user=self.get_current_user()
        )
        assert auth.has_perm(self.get_current_user(), 'r')
        assert not auth.has_perm(self.get_current_user(), 'w')
        assert auth.has_perm('anonymous', 'e')
        assert not auth.has_perm('anonymous', 'w')
        warnings.filterwarnings("ignore")
        auth.override_user('anonymous', perm='w')
        warnings.resetwarnings()
        assert auth.has_perm('anonymous', 'w')

    def test_validate_authentication(self):
        # we can only test for invalid credentials
        auth = UnixAuthorizer(require_valid_shell=False)
        with pytest.raises(AuthenticationFailed):
            auth.validate_authentication(
                '?!foo',
                '?!foo',
                None,
            )
        auth = UnixAuthorizer(require_valid_shell=True)
        with pytest.raises(AuthenticationFailed):
            auth.validate_authentication(
                '?!foo',
                '?!foo',
                None,
            )

    def test_validate_authentication_anonymous(self):
        current_user = self.get_current_user()
        auth = UnixAuthorizer(
            anonymous_user=current_user, require_valid_shell=False
        )
        with pytest.raises(AuthenticationFailed):
            auth.validate_authentication(
                'foo',
                'passwd',
                None,
            )
        with pytest.raises(AuthenticationFailed):
            auth.validate_authentication(
                current_user,
                'passwd',
                None,
            )
        auth.validate_authentication('anonymous', 'passwd', None)

    def test_require_valid_shell(self):

        def get_fake_shell_user():
            for user in self.get_users():
                shell = pwd.getpwnam(user).pw_shell
                # On linux fake shell is usually /bin/false, on
                # freebsd /usr/sbin/nologin;  in case of other
                # UNIX variants test needs to be adjusted.
                if '/false' in shell or '/nologin' in shell:
                    return user
            self.fail("no user found")

        user = get_fake_shell_user()
        self.assertRaisesWithMsg(
            AuthorizerError,
            f"user {user} has not a valid shell",
            UnixAuthorizer,
            allowed_users=[user],
        )
        # commented as it first fails for invalid home
        # self.assertRaisesWithMsg(
        #     ValueError,
        #     "user %s has not a valid shell" % user,
        #     UnixAuthorizer, anonymous_user=user)
        auth = UnixAuthorizer()
        assert auth._has_valid_shell(self.get_current_user())
        assert not auth._has_valid_shell(user)
        self.assertRaisesWithMsg(
            AuthorizerError,
            f"User {user} doesn't have a valid shell.",
            auth.override_user,
            user,
            perm='r',
        )

    def test_not_root(self):
        # UnixAuthorizer is supposed to work only as super user
        auth = self.authorizer_class()
        try:
            auth.impersonate_user('nobody', '')
            self.assertRaisesWithMsg(
                AuthorizerError,
                "super user privileges are required",
                UnixAuthorizer,
            )
        finally:
            auth.terminate_impersonation('nobody')


# =====================================================================
# --- Windows authorizer
# =====================================================================


@pytest.mark.skipif(not WINDOWS, reason="Windows only")
class TestWindowsAuthorizer(_SharedAuthorizerTests, PyftpdlibTestCase):
    """Windows authorizer specific tests."""

    authorizer_class = WindowsAuthorizer

    def test_wrong_anonymous_credentials(self):
        user = self.get_current_user()
        with pytest.raises(Win32ExtError):
            self.authorizer_class(
                anonymous_user=user, anonymous_password='$|1wrongpasswd'
            )
