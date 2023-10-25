# Shortcuts for various tasks (UNIX only).
# To use a specific Python version run:
# $ make install PYTHON=python3.7

PYTHON = python3
TSCRIPT = pyftpdlib/test/runner.py
ARGS =
PYDEPS = \
	check-manifest \
	coverage \
	psutil \
	pylint \
	pyopenssl \
	rstcheck \
	ruff \
	setuptools \
	teyit \
	toml-sort \
	twine
PYVER = $(shell $(PYTHON) -c "import sys; print(sys.version_info[0])")
ifeq ($(PYVER), 2)
	PYDEPS = \
		ipaddress \
		mock \
		psutil \
		pyopenssl \
		pysendfile \
		setuptools
endif

# In not in a virtualenv, add --user options for install commands.
INSTALL_OPTS = `$(PYTHON) -c "import sys; print('' if hasattr(sys, 'real_prefix') else '--user')"`
TEST_PREFIX = PYTHONWARNINGS=always
NUM_WORKERS = `$(PYTHON) -c "import os; print(os.cpu_count() or 1)"`


# ===================================================================
# Install
# ===================================================================

all: test

clean:  ## Remove all build files.
	@rm -rfv `find . \
		-type d -name __pycache__ \
		-o -type f -name \*.bak \
		-o -type f -name \*.orig \
		-o -type f -name \*.pyc \
		-o -type f -name \*.pyd \
		-o -type f -name \*.pyo \
		-o -type f -name \*.rej \
		-o -type f -name \*.so \
		-o -type f -name \*.~ \
		-o -type f -name \*\$testfn`
	@rm -rfv \
		*.core \
		*.egg-info \
		*\$testfile* \
		.coverage \
		.failed-tests.txt \
		.pytest_cache \
		.ruff_cache/ \
		build/ \
		dist/ \
		docs/_build/ \
		htmlcov/ \
		pyftpd-tmp-* \
		tmp/

install:  ## Install this package.
	# make sure setuptools is installed (needed for 'develop' / edit mode)
	$(PYTHON) -c "import setuptools"
	$(PYTHON) setup.py develop $(INSTALL_OPTS)

uninstall:  ## Uninstall this package.
	cd ..; $(PYTHON) -m pip uninstall -y -v pyftpdlib || true
	$(PYTHON) scripts/internal/purge_installation.py

install-pip:  ## (only if necessary)
	$(PYTHON) -c \
		"import sys, ssl, os, pkgutil, tempfile, atexit; \
		sys.exit(0) if pkgutil.find_loader('pip') else None; \
		pyexc = 'from urllib.request import urlopen' if sys.version_info[0] >= 3 else 'from urllib2 import urlopen'; \
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

setup-dev-env: ## Install GIT hooks, pip, test deps (also upgrades them).
	${MAKE} install-git-hooks
	${MAKE} install-pip
	$(PYTHON) -m pip install $(INSTALL_OPTS) --upgrade pip setuptools
	$(PYTHON) -m pip install $(INSTALL_OPTS) --upgrade $(PYDEPS)

# ===================================================================
# Tests
# ===================================================================

test:  ## Run all tests. To run a specific test: do "make test ARGS=pyftpdlib.test.test_functional.TestFtpStoreData"
	${MAKE} install
	$(TEST_PREFIX) $(PYTHON) $(TSCRIPT) $(ARGS)

test-functional:  ## Run functional FTP tests.
	${MAKE} install
	$(TEST_PREFIX) $(PYTHON) pyftpdlib/test/test_functional.py

test-functional-ssl:  ## Run functional FTPS tests.
	${MAKE} install
	$(TEST_PREFIX) $(PYTHON) pyftpdlib/test/test_functional_ssl.py

test-servers:  ## Run tests for FTPServer and its subclasses.
	${MAKE} install
	$(TEST_PREFIX) $(PYTHON) pyftpdlib/test/test_servers.py

test-authorizers:  ## Run tests for authorizers.
	${MAKE} install
	$(TEST_PREFIX) $(PYTHON) pyftpdlib/test/test_authorizers.py

test-filesystems:  ## Run filesystem tests.
	${MAKE} install
	$(TEST_PREFIX) $(PYTHON) pyftpdlib/test/test_filesystems.py

test-ioloop:  ## Run IOLoop tests.
	${MAKE} install
	$(TEST_PREFIX) $(PYTHON) pyftpdlib/test/test_ioloop.py

test-misc:  ## Run miscellaneous tests.
	${MAKE} install
	$(TEST_PREFIX) $(PYTHON) pyftpdlib/test/test_misc.py

test-coverage:  ## Run test coverage.
	${MAKE} install
	rm -rf .coverage htmlcov
	PYTHONWARNINGS=all $(PYTHON) -m coverage run $(TSCRIPT)
	$(PYTHON) -m coverage report
	@echo "writing results to htmlcov/index.html"
	$(PYTHON) -m coverage html
	$(PYTHON) -m webbrowser -t htmlcov/index.html

# ===================================================================
# Linters
# ===================================================================

ruff:  ## Run ruff linter.
	@git ls-files '*.py' | xargs $(PYTHON) -m ruff check --config=pyproject.toml --no-cache

_pylint:  ## Python pylint (not mandatory, just run it from time to time)
	@git ls-files '*.py' | xargs $(PYTHON) -m pylint --rcfile=pyproject.toml --jobs=${NUM_WORKERS}

lint-rst:  ## Run RsT linter.
	@git ls-files '*.rst' | xargs rstcheck --config=pyproject.toml

lint-toml:  ## Linter for pyproject.toml
	@git ls-files '*.toml' | xargs toml-sort --check

lint-all:  ## Run all linters
	${MAKE} ruff
	${MAKE} lint-rst
	${MAKE} lint-toml

# ===================================================================
# Fixers
# ===================================================================

fix-ruff:
	@git ls-files '*.py' | xargs $(PYTHON) -m ruff --config=pyproject.toml --no-cache --fix

fix-toml:  ## Fix pyproject.toml
	@git ls-files '*.toml' | xargs toml-sort

fix-unittests:  ## Fix unittest idioms.
	@git ls-files '*test_*.py' | xargs $(PYTHON) -m teyit --show-stats

fix-all:  ## Run all code fixers.
	${MAKE} fix-ruff
	${MAKE} fix-toml
	${MAKE} fix-unittests

# ===================================================================
# Distribution
# ===================================================================

check-manifest:  ## Inspect MANIFEST.in file.
	$(PYTHON) -m check_manifest -v $(ARGS)

upload-src:  ## Upload source on PYPI.
	${MAKE} clean
	$(PYTHON) setup.py sdist upload

git-tag-release:  ## Git-tag a new release.
	git tag -a release-`python3 -c "import setup; print(setup.VERSION)"` -m `git rev-list HEAD --count`:`git rev-parse --short HEAD`
	git push --follow-tags

install-git-hooks:  ## Install GIT pre-commit hook.
	ln -sf ../../scripts/internal/git_pre_commit.py .git/hooks/pre-commit
	chmod +x .git/hooks/pre-commit

grep-todos:  ## Look for TODOs in source files.
	git grep -EIn "TODO|FIXME|XXX"

pre-release:  ## All the necessary steps before making a release.
	${MAKE} clean
	$(PYTHON) -c \
		"from pyftpdlib import __ver__ as ver; \
		doc = open('docs/index.rst').read(); \
		history = open('HISTORY.rst').read(); \
		assert ver in history, '%r not in HISTORY.rst' % ver; \
		assert 'XXXX' not in history; \
		"
	$(PYTHON) setup.py sdist

release:  ## Creates a release (tar.gz + upload + git tag release).
	${MAKE} pre-release
	$(PYTHON) -m twine upload --verbose dist/*  # upload tar on PYPI
	${MAKE} git-tag-release

generate-manifest:  ## Generates MANIFEST.in file.
	$(PYTHON) scripts/internal/generate_manifest.py > MANIFEST.in

print-announce:  ## Print announce of new release.
	@$(PYTHON) scripts/internal/print_announce.py

help: ## Display callable targets.
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | sort | awk 'BEGIN {FS = ":.*?## "}; {printf "\033[36m%-20s\033[0m %s\n", $$1, $$2}'
