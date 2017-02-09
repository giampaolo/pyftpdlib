#!/bin/bash

set -e
set -x

if [[ "$(uname -s)" == 'Darwin' ]]; then
    if which pyenv > /dev/null; then
        eval "$(pyenv init -)"
    fi
    pyenv activate pyftpdlib
fi

pip install -U flake8 pyopenssl mock setuptools six
python setup.py install
python pyftpdlib/test/runner.py
if [[ $TRAVIS_PYTHON_VERSION == '2.6' ]] || [[ $PYVER == 'py26' ]]; then
    exit 0;
fi
flake8
