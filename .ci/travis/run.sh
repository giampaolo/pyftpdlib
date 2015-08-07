#!/bin/bash

set -e
set -x

if [[ "$(uname -s)" == 'Darwin' ]]; then
    if which pyenv > /dev/null; then
        eval "$(pyenv init -)"
    fi
    pyenv activate pyftpdlib
fi

pip install flake8
python setup.py install
python test/test_ftpd.py
python test/test_contrib.py
flake8
