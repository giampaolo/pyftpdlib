# Shortcuts for various tasks (UNIX only).
# To use a specific Python version run:
# 	$ make install PYTHON=python3.7
# To run a specific test:
# 	$ make test ARGS="-v -s tests/test_functional.py::TestIPv6MixedEnvironment::test_port_v4"

# Configurable
PYTHON = python3
ARGS =

# In not in a virtualenv, add --user options for install commands.
SETUP_INSTALL_ARGS = `$(PYTHON) -c \
	"import sys; print('' if hasattr(sys, 'real_prefix') or hasattr(sys, 'base_prefix') and sys.base_prefix != sys.prefix else '--user')"`
PYTHON_ENV_VARS = PYTHONWARNINGS=always PYTHONUNBUFFERED=1 PYTEST_DISABLE_PLUGIN_AUTOLOAD=1
PIP_INSTALL_ARGS = --trusted-host files.pythonhosted.org --trusted-host pypi.org --upgrade

# if make is invoked with no arg, default to `make help`
.DEFAULT_GOAL := help

# install git hook
_ := $(shell mkdir -p .git/hooks/ && ln -sf ../../scripts/internal/git_pre_commit.py .git/hooks/pre-commit && chmod +x .git/hooks/pre-commit)

# ===================================================================
# Install
# ===================================================================

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
	$(PYTHON) -m pip install $(PIP_INSTALL_ARGS) pip setuptools
	$(PYTHON) -m pip install $(PIP_INSTALL_ARGS) `$(PYTHON) -c "import setup; print(' '.join(setup.TEST_DEPS))"`

install-pydeps-dev:  ## Install python deps meant for local development.
	${MAKE} install-git-hooks
	${MAKE} install-pip
	$(PYTHON) -m pip install $(PIP_INSTALL_ARGS) pip setuptools
	$(PYTHON) -m pip install $(PIP_INSTALL_ARGS) `$(PYTHON) -c "import setup; print(' '.join(setup.TEST_DEPS + setup.DEV_DEPS))"`

install-git-hooks:  ## Install GIT pre-commit hook.
	ln -sf ../../scripts/internal/git_pre_commit.py .git/hooks/pre-commit
	chmod +x .git/hooks/pre-commit

# ===================================================================
# Tests
# ===================================================================

test:  ## Run all tests. To run a specific test: do "make test ARGS=pyftpdlib.test.test_functional.TestFtpStoreData"
	$(PYTHON_ENV_VARS) $(PYTHON) -m pytest $(ARGS)

test-parallel:  ## Run all tests in parallel.
	$(PYTHON_ENV_VARS) $(PYTHON) -m pytest -n auto --dist loadgroup $(ARGS)

test-functional:  ## Run functional FTP tests.
	$(PYTHON_ENV_VARS) $(PYTHON) -m pytest $(ARGS) tests/test_functional.py

test-functional-ssl:  ## Run functional FTPS tests.
	$(PYTHON_ENV_VARS) $(PYTHON) -m pytest $(ARGS) tests/test_functional_ssl.py

test-servers:  ## Run tests for FTPServer and its subclasses.
	$(PYTHON_ENV_VARS) $(PYTHON) -m pytest $(ARGS) tests/test_servers.py

test-authorizers:  ## Run tests for authorizers.
	$(PYTHON_ENV_VARS) $(PYTHON) -m pytest $(ARGS) tests/test_authorizers.py

test-filesystems:  ## Run filesystem tests.
	$(PYTHON_ENV_VARS) $(PYTHON) -m pytest $(ARGS) tests/test_filesystems.py

test-ioloop:  ## Run IOLoop tests.
	$(PYTHON_ENV_VARS) $(PYTHON) -m pytest $(ARGS) tests/test_ioloop.py

test-cli:  ## Run miscellaneous tests.
	$(PYTHON_ENV_VARS) $(PYTHON) -m pytest $(ARGS) tests/test_cli.py

test-lastfailed:  ## Run previously failed tests
	$(PYTHON_ENV_VARS) $(PYTHON) -m pytest --last-failed $(ARGS)

test-coverage:  ## Run test coverage.
	rm -rf .coverage htmlcov
	$(PYTHON_ENV_VARS) $(PYTHON) -m coverage run -m pytest $(ARGS)
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
	@git ls-files '*.py' | xargs $(PYTHON) -m pylint --rcfile=pyproject.toml --jobs=0 $(ARGS)

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

sdist:  ## Create tar.gz source distribution.
	${MAKE} generate-manifest
	$(PYTHON_ENV_VARS) $(PYTHON) setup.py sdist
	# Check sanity of source distribution.
	$(PYTHON_ENV_VARS) $(PYTHON) -m virtualenv --clear --no-wheel --quiet build/venv
	$(PYTHON_ENV_VARS) build/venv/bin/python -m pip install -v --isolated --quiet dist/*.tar.gz
	$(PYTHON_ENV_VARS) build/venv/bin/python -c "import os; os.chdir('build/venv'); import pyftpdlib"
	$(PYTHON) -m twine check --strict dist/*.tar.gz

pre-release:  ## All the necessary steps before making a release.
	${MAKE} clean
	${MAKE} sdist
	$(PYTHON) -c \
		"from pyftpdlib import __ver__ as ver; \
		doc = open('docs/index.rst').read(); \
		history = open('HISTORY.rst').read(); \
		assert ver in history, '%r not in HISTORY.rst' % ver; \
		assert 'XXXX' not in history; \
		"

release:  ## Creates a release (tar.gz + upload + git tag release).
	${MAKE} pre-release
	$(PYTHON) -m twine upload dist/*.tar.gz  # upload tar on PYPI
	${MAKE} git-tag-release

generate-manifest:  ## Generates MANIFEST.in file.
	$(PYTHON) scripts/internal/generate_manifest.py > MANIFEST.in

git-tag-release:  ## Git-tag a new release.
	git tag -a release-`$(PYTHON) -c "import pyftpdlib; print(pyftpdlib.__ver__)"` -m `git rev-list HEAD --count`:`git rev-parse --short HEAD`
	git push --follow-tags

print-announce:  ## Print announce of new release.
	@$(PYTHON) scripts/internal/print_announce.py

# ===================================================================
# Misc
# ===================================================================

grep-todos:  ## Look for TODOs in source files.
	git grep -EIn "TODO|FIXME|XXX"

check-manifest:  ## Inspect MANIFEST.in file.
	$(PYTHON) -m check_manifest -v $(ARGS)

check-broken-links:  ## Look for broken links in source files.
	git ls-files | xargs $(PYTHON) -Wa scripts/internal/check_broken_links.py

help: ## Display callable targets.
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | sort | awk 'BEGIN {FS = ":.*?## "}; {printf "\033[36m%-20s\033[0m %s\n", $$1, $$2}'
