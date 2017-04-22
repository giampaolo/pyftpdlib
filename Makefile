# Shortcuts for various tasks (UNIX only).
# To use a specific Python version run:
# $ make install PYTHON=python3.3

PYTHON=python
TSCRIPT=pyftpdlib/test/runner.py
ARGS=

DEPS=coverage \
	check-manifest \
	flake8 \
	mock==1.0.1 \
	nose \
	pep8 \
	pyflakes \
	pyopenssl \
	pysendfile \
	setuptools \
	sphinx \
	unittest2

# In not in a virtualenv, add --user options for install commands.
INSTALL_OPTS = `$(PYTHON) -c "import sys; print('' if hasattr(sys, 'real_prefix') else '--user')"`

all: test

clean:
	rm -rf `find . -type d -name __pycache__ \
		-o -type f -name \*.bak \
		-o -type f -name \*.orig \
		-o -type f -name \*.pyc \
		-o -type f -name \*.pyd \
		-o -type f -name \*.pyo \
		-o -type f -name \*.rej \
		-o -type f -name \*.so \
		-o -type f -name \*.~ \
		-o -type f -name \*\$testfn`
	rm -rf \
		*.core \
		*.egg-info \
		*\$testfile* \
		.coverage \
		.tox \
		build/ \
		dist/ \
		docs/_build/ \
		htmlcov/ \
		tmp/

build: clean
	$(PYTHON) setup.py build

install: build
	# make sure setuptools is installed (needed for 'develop' / edit mode)
	$(PYTHON) -c "import setuptools"
	$(PYTHON) setup.py develop $(INSTALL_OPTS)

uninstall:
	cd ..; $(PYTHON) -m pip uninstall -y -v pyftpdlib

# Install PIP (only if necessary).
install-pip:
	$(PYTHON) -c \
		"import sys, ssl, os, pkgutil, tempfile, atexit; \
		sys.exit(0) if pkgutil.find_loader('pip') else None; \
		pyexc = 'from urllib.request import urlopen' if sys.version_info[0] == 3 else 'from urllib2 import urlopen'; \
		exec(pyexc); \
		ctx = ssl._create_unverified_context() if hasattr(ssl, '_create_unverified_context') else None; \
		kw = dict(context=ctx) if ctx else {}; \
		req = urlopen('https://bootstrap.pypa.io/get-pip.py', **kw); \
		data = req.read(); \
		f = tempfile.NamedTemporaryFile(suffix='.py'); \
		atexit.register(f.close); \
		f.write(data); \
		f.flush(); \
		print('downloaded %s' % f.name); \
		code = os.system('%s %s --user' % (sys.executable, f.name)); \
		f.close(); \
		sys.exit(code);"

# useful deps which are nice to have while developing / testing
setup-dev-env: install-git-hooks install-pip
	$(PYTHON) -m pip install $(INSTALL_OPTS) --upgrade pip
	$(PYTHON) -m pip install $(INSTALL_OPTS) --upgrade $(DEPS)

test: install
	$(PYTHON) $(TSCRIPT)

test-functional: install
	$(PYTHON) pyftpdlib/test/test_functional.py

test-functional-ssl: install
	$(PYTHON) pyftpdlib/test/test_functional_ssl.py

test-authorizers: install
	$(PYTHON) pyftpdlib/test/test_authorizers.py

test-filesystems: install
	$(PYTHON) pyftpdlib/test/test_filesystems.py

test-ioloop: install
	$(PYTHON) pyftpdlib/test/test_ioloop.py

test-servers: install
	$(PYTHON) pyftpdlib/test/test_servers.py

# Run a specific test by name; e.g. "make test-by-name retr" will run
# all test methods containing "retr" in their name.
# Requires "pip install nose".
test-by-name: install
	@$(PYTHON) -m nose pyftpdlib/test/test_*.py --nocapture -v -m $(filter-out $@,$(MAKECMDGOALS))

coverage: install
	# Note: coverage options are controlled by .coveragerc file
	rm -rf .coverage htmlcov
	$(PYTHON) -m coverage run $(TSCRIPT)
	$(PYTHON) -m coverage report
	@echo "writing results to htmlcov/index.html"
	$(PYTHON) -m coverage html
	$(PYTHON) -m webbrowser -t htmlcov/index.html

pep8:
	@git ls-files | grep \\.py$ | xargs $(PYTHON) -m pep8

pyflakes:
	# ignore doctests
	export PYFLAKES_NODOCTEST=1 && \
		git ls-files | grep \\.py$ | xargs $(PYTHON) -m pyflakes

flake8:
	@git ls-files | grep \\.py$ | xargs $(PYTHON) -m flake8

check-manifest:
	$(PYTHON) -m check_manifest -v $(ARGS)

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

grep-todos:
	git grep -EIn "TODO|FIXME|XXX"

# All the necessary steps before making a release.
pre-release:
	${MAKE} clean
	$(PYTHON) -c \
		"from pyftpdlib import __ver__ as ver; \
		doc = open('docs/index.rst').read(); \
		history = open('HISTORY.rst').read(); \
		assert ver in history, '%r not in HISTORY.rst' % ver; \
		assert 'XXXX' not in history; \
		"
	$(PYTHON) setup.py sdist

# Create a release: creates tar.gz, uploads it, git tag release.
release:
	${MAKE} pre-release
	$(PYTHON) -m twine upload dist/*  # upload tar on PYPI
	${MAKE} git-tag-release

# Print announce of new release.
print-announce:
	@$(PYTHON) scripts/print_announce.py

# generate a doc.zip file and manually upload it to PYPI.
doc:
	cd docs && make html && cd _build/html/ && zip doc.zip -r .
	mv docs/_build/html/doc.zip .
	@echo "done; now manually upload doc.zip from here: https://pypi.python.org/pypi?:action=pkg_edit&name=pyftpdlib"
