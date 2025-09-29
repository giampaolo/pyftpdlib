# Copyright (C) 2007 Giampaolo Rodola' <g.rodola@gmail.com>.
# Use of this source code is governed by MIT license that can be
# found in the LICENSE file.


class AuthorizerError(Exception):
    """Base class for authorizer exceptions."""


class AuthenticationFailed(Exception):
    """Exception raised when authentication fails for any reason."""
