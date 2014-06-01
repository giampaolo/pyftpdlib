# Shortcuts for various tasks (UNIX only).
# To use a specific Python version run:
# $ make install PYTHON=python3.3

PYTHON=python
TSCRIPT=test/test_ftpd.py
FLAGS=

all: test

clean:
	rm -f `find . -type f -name \*.py[co]`
	rm -f `find . -type f -name .\*~`
	rm -f `find . -type f -name \*.orig`
	rm -f `find . -type f -name \*.bak`
	rm -f `find . -type f -name \*.rej`
	rm -rf `find . -type d -name __pycache__`
	rm -rf *.egg-info
	rm -rf .tox
	rm -rf build
	rm -rf dist
	rm -rf docs/_build

build: clean
	$(PYTHON) setup.py build

install: build
	if test $(PYTHON) = python2.4; then \
		$(PYTHON) setup.py install; \
	elif test $(PYTHON) = python2.5; then \
		$(PYTHON) setup.py install; \
	else \
		$(PYTHON) setup.py install --user; \
	fi

uninstall:
	pip-`$(PYTHON) -c "import sys; sys.stdout.write('.'.join(map(str, sys.version_info)[:2]))"` uninstall -y -v pyftpdlib

test: install
	$(PYTHON) $(TSCRIPT)

test-contrib: install
	$(PYTHON) test/test_contrib.py

nosetest: install
	# $ make nosetest FLAGS=test_name
	nosetests $(TSCRIPT) -v -m $(FLAGS)

pep8:
	pep8 pyftpdlib/ demo/ test/ setup.py --ignore E302

pyflakes:
	# ignore doctests
	export PYFLAKES_NODOCTEST=1 && \
		pyflakes pyftpdlib/ demo/ test/ setup.py

flake8:
	@git ls-files | grep \\.py$ | xargs flake8

upload-src: clean
	$(PYTHON) setup.py sdist upload

# Build and upload doc on https://pythonhosted.org/pyftpdlib/.
# Requires "pip install sphinx-pypi-upload".
upload-docs:
	cd docs; make html
	$(PYTHON) setup.py upload_sphinx --upload-dir=docs/_build/html

# git-tag a new release
git-tag-release:
	git tag -a release-`python -c "import setup; print(setup.VERSION)"` -m `git rev-list HEAD --count`:`git rev-parse --short HEAD`
