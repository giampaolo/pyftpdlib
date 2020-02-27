#!/bin/bash

set -e
set -x

uname -a
python -c "import sys; print(sys.version)"

if [[ "$(uname -s)" == 'Darwin' ]]; then
    brew update || brew update
    brew outdated pyenv || brew upgrade pyenv
    brew install pyenv-virtualenv

    if which pyenv > /dev/null; then
        eval "$(pyenv init -)"
    fi

    case "${PYVER}" in
        py27)
            pyenv install 2.7.17
            pyenv virtualenv 2.7.17 pyftpdlib
            ;;
        py34)
            pyenv install --list
            pyenv install 3.8.1
            pyenv virtualenv 3.8.1 pyftpdlib
            ;;
    esac
    pyenv rehash
    pyenv activate pyftpdlib
fi

# It appears it's necessary to first upgrade setuptools separately:
# https://github.com/pyexcel/pyexcel/issues/49
pip install -U setuptools
pip install -U pip six pyopenssl pysendfile flake8 mock coveralls psutil
