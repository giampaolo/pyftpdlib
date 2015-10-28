# Shortcuts for various tasks (UNIX only).
# To use a specific Python version run:
# $ make install PYTHON=python3.3

PYTHON=python
TSCRIPT=pyftpdlib/test/runner.py
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
	$(PYTHON) setup.py install --user;

uninstall:
	pip-`$(PYTHON) -c "import sys; sys.stdout.write('.'.join(list(map(str, sys.version_info))[:2]))"` uninstall -y -v pyftpdlib

# useful deps which are nice to have while developing / testing
setup-dev-env: install-git-hooks
	python -c  "import urllib2, ssl; \
				context = ssl._create_unverified_context() if hasattr(ssl, '_create_unverified_context') else None; \
				kw = dict(context=context) if context else {}; \
				r = urllib2.urlopen('https://bootstrap.pypa.io/get-pip.py', **kw); \
				open('/tmp/get-pip.py', 'w').write(r.read());"
	$(PYTHON) /tmp/get-pip.py --user
	rm /tmp/get-pip.py
	$(PYTHON) -m pip install --user --upgrade pip
	$(PYTHON) -m pip install --user --upgrade \
		coverage  \
		flake8 \
		ipdb \
		mock==1.0.1 \
		nose \
		pep8 \
		pyflakes \
		pyopenssl \
		pysendfile \
		sphinx \
		sphinx-pypi-upload \
		unittest2 \

test: install
	$(PYTHON) $(TSCRIPT)

test-functional: install
	$(PYTHON) pyftpdlib/test/test_functional.py

test-functional-ssl: install
	$(PYTHON) pyftpdlib/test/test_functional_ssl.py

# Run a specific test by name; e.g. "make test-by-name retr" will run
# all test methods containing "retr" in their name.
# Requires "pip install nose".
test-by-name:
	@$(PYTHON) -m nose pyftpdlib/test/test_*.py --nocapture -v -m $(filter-out $@,$(MAKECMDGOALS))

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
	@echo "now run 'git push --tags'"

# install GIT pre-commit hook
install-git-hooks:
	ln -sf ../../.git-pre-commit .git/hooks/pre-commit
	chmod +x .git/hooks/pre-commit
