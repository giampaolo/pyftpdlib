# Shortcuts for various tasks (UNIX only).
# To use a specific Python version run:
# 	$ make install PYTHON=python3.7
# To run a specific test:
# 	$ make test ARGS="-v -s pyftpdlib/test/test_functional.py::TestIPv6MixedEnvironment::test_port_v4"

# Configurable
PYTHON = python3
ARGS =

# In not in a virtualenv, add --user options for install commands.
SETUP_INSTALL_ARGS = `$(PYTHON) -c \
	"import sys; print('' if hasattr(sys, 'real_prefix') or hasattr(sys, 'base_prefix') and sys.base_prefix != sys.prefix else '--user')"`
TEST_PREFIX = PYTHONWARNINGS=always
PYTEST_ARGS = -v -s --tb=short
NUM_WORKERS = `$(PYTHON) -c "import os; print(os.cpu_count() or 1)"`
PIP_INSTALL_ARGS = --trusted-host files.pythonhosted.org --trusted-host pypi.org --upgrade

# if make is invoked with no arg, default to `make help`
.DEFAULT_GOAL := help

# install git hook
_ := $(shell mkdir -p .git/hooks/ && ln -sf ../../scripts/internal/git_pre_commit.py .git/hooks/pre-commit && chmod +x .git/hooks/pre-commit)

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
	$(PYTHON) setup.py develop $(SETUP_INSTALL_ARGS)

uninstall:  ## Uninstall this package.
	cd ..; $(PYTHON) -m pip uninstall -y -v pyftpdlib || true
	$(PYTHON) scripts/internal/purge_installation.py

install-pip:  ## Install pip (no-op if already installed).
	$(PYTHON) scripts/internal/install_pip.py

install-pydeps-test:  ## Install python deps necessary to run unit tests.
	${MAKE} install-pip
	$(PYTHON) -m pip install $(PIP_INSTALL_ARGS) pip  # upgrade pip to latest version
	$(PYTHON) -m pip install $(PIP_INSTALL_ARGS) `$(PYTHON) -c "import setup; print(' '.join(setup.TEST_DEPS))"`

install-pydeps-dev:  ## Install python deps meant for local development.
	${MAKE} install-git-hooks
	${MAKE} install-pip
	$(PYTHON) -m pip install $(PIP_INSTALL_ARGS) pip  # upgrade pip to latest version
	$(PYTHON) -m pip install $(PIP_INSTALL_ARGS) `$(PYTHON) -c "import setup; print(' '.join(setup.TEST_DEPS + setup.DEV_DEPS))"`

# ===================================================================
# Tests
# ===================================================================

test:  ## Run all tests. To run a specific test: do "make test ARGS=pyftpdlib.test.test_functional.TestFtpStoreData"
	$(TEST_PREFIX) $(PYTHON) -m pytest $(PYTEST_ARGS) $(ARGS)

test-parallel:  ## Run all tests in parallel.
	$(TEST_PREFIX) $(PYTHON) -m pytest $(PYTEST_ARGS) -n auto --dist loadgroup $(ARGS)

test-functional:  ## Run functional FTP tests.
	$(TEST_PREFIX) $(PYTHON) -m pytest $(PYTEST_ARGS) $(ARGS) pyftpdlib/test/test_functional.py

test-functional-ssl:  ## Run functional FTPS tests.
	$(TEST_PREFIX) $(PYTHON) -m pytest $(PYTEST_ARGS) $(ARGS) pyftpdlib/test/test_functional_ssl.py

test-servers:  ## Run tests for FTPServer and its subclasses.
	$(TEST_PREFIX) $(PYTHON) -m pytest $(PYTEST_ARGS) $(ARGS) pyftpdlib/test/test_servers.py

test-authorizers:  ## Run tests for authorizers.
	$(TEST_PREFIX) $(PYTHON) -m pytest $(PYTEST_ARGS) $(ARGS) pyftpdlib/test/test_authorizers.py

test-filesystems:  ## Run filesystem tests.
	$(TEST_PREFIX) $(PYTHON) -m pytest $(PYTEST_ARGS) $(ARGS) pyftpdlib/test/test_filesystems.py

test-ioloop:  ## Run IOLoop tests.
	$(TEST_PREFIX) $(PYTHON) -m pytest $(PYTEST_ARGS) $(ARGS) pyftpdlib/test/test_ioloop.py

test-cli:  ## Run miscellaneous tests.
	$(TEST_PREFIX) $(PYTHON) -m pytest $(PYTEST_ARGS) $(ARGS) pyftpdlib/test/test_cli.py

test-lastfailed:  ## Run previously failed tests
	$(TEST_PREFIX) $(PYTHON) -m pytest $(PYTEST_ARGS) --last-failed $(ARGS)

test-coverage:  ## Run test coverage.
	rm -rf .coverage htmlcov
	$(TEST_PREFIX) $(PYTHON) -m coverage run -m pytest $(PYTEST_ARGS) $(ARGS)
	$(PYTHON) -m coverage report
	@echo "writing results to htmlcov/index.html"
	$(PYTHON) -m coverage html
	$(PYTHON) -m webbrowser -t htmlcov/index.html

# ===================================================================
# Linters
# ===================================================================

black:  ## Python files linting (via black)
	@git ls-files '*.py' | xargs $(PYTHON) -m black --check --safe

ruff:  ## Run ruff linter.
	@git ls-files '*.py' | xargs $(PYTHON) -m ruff check --output-format=concise

_pylint:  ## Python pylint (not mandatory, just run it from time to time)
	@git ls-files '*.py' | xargs $(PYTHON) -m pylint --rcfile=pyproject.toml --jobs=${NUM_WORKERS}

lint-rst:  ## Run RsT linter.
	@git ls-files '*.rst' | xargs rstcheck --config=pyproject.toml

lint-toml:  ## Linter for pyproject.toml
	@git ls-files '*.toml' | xargs toml-sort --check

lint-all:  ## Run all linters
	${MAKE} black
	${MAKE} ruff
	${MAKE} lint-rst
	${MAKE} lint-toml

# ===================================================================
# Fixers
# ===================================================================

fix-black:
	git ls-files '*.py' | xargs $(PYTHON) -m black

fix-ruff:
	@git ls-files '*.py' | xargs $(PYTHON) -m ruff check --fix --output-format=concise $(ARGS)

fix-toml:  ## Fix pyproject.toml
	@git ls-files '*.toml' | xargs toml-sort

fix-all:  ## Run all code fixers.
	${MAKE} fix-black
	${MAKE} fix-ruff
	${MAKE} fix-toml

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

# ===================================================================
# Misc
# ===================================================================

check-broken-links:  ## Look for broken links in source files.
	git ls-files | xargs $(PYTHON) -Wa scripts/internal/check_broken_links.py

help: ## Display callable targets.
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | sort | awk 'BEGIN {FS = ":.*?## "}; {printf "\033[36m%-20s\033[0m %s\n", $$1, $$2}'
