#!/bin/bash

set -e
set -x

if [[ "$(uname -s)" == 'Darwin' ]]; then
    brew update || brew update
    brew outdated pyenv || brew upgrade pyenv
    brew install pyenv-virtualenv

    if which pyenv > /dev/null; then
        eval "$(pyenv init -)"
    fi

    case "${PYVER}" in
        py26)
            pyenv install 2.6
            pyenv virtualenv 2.6 psutil
            ;;
        py27)
            pyenv install 2.7
            pyenv virtualenv 2.7 psutil
            ;;
        py33)
            pyenv install 3.3
            pyenv virtualenv 3.3 psutil
            ;;
        py34)
            pyenv install 3.4
            pyenv virtualenv 3.4 psutil
            ;;
        py35)
            pyenv install 3.5
            pyenv virtualenv 3.5 psutil
            ;;
    esac
    pyenv rehash
    pyenv activate pyftpdlib
fi

if [[ $TRAVIS_PYTHON_VERSION == '2.6' ]] || [[ $PYVER == 'py26' ]]; then
    pip install -U unittest2
fi

pip install -U pyopenssl pysendfile flake8 mock coveralls
