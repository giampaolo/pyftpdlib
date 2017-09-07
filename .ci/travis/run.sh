#!/bin/bash

set -e
set -x

if [[ "$(uname -s)" == 'Darwin' ]]; then
    if which pyenv > /dev/null; then
        eval "$(pyenv init -)"
    fi
    pyenv activate pyftpdlib
fi

python setup.py install
python pyftpdlib/test/runner.py

# run linter only on Linux and on latest python versions
if [ "$PYVER" == "2.7" ] || [ "$PYVER" == "3.6" ]; then
    if [[ "$(uname -s)" != 'Darwin' ]]; then
        rm -rf build
        python -m flake8
    fi
fi
