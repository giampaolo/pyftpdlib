# Shortcuts for various tasks (UNIX only).
# To use a specific Python version run:
# 	$ make install PYTHON=python3.13
# To run a specific test:
# 	$ make test ARGS="-v -s tests/test_functional.py::TestIPv6MixedEnvironment::test_port_v4"

# Configurable
PYTHON = python3
ARGS =
FILES =

PYTHON_ENV_VARS = PYTHONWARNINGS=always PYTHONUNBUFFERED=1 PYTEST_DISABLE_PLUGIN_AUTOLOAD=1
INSTALL_PYDEPS = PYTHON=$(PYTHON) ./scripts/internal/install-pydeps.sh

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
	$(INSTALL_PYDEPS) --editable .

uninstall:  ## Uninstall this package.
	cd ..; $(PYTHON) -m pip uninstall -y -v pyftpdlib || true
	$(PYTHON) scripts/internal/purge_installation.py

install-pip:  ## Install pip, or upgrade it if it's too old.
	$(PYTHON) scripts/internal/install_pip.py

install-pydeps-test:  ## Install python deps necessary to run unit tests.
	$(INSTALL_PYDEPS) --group test

install-pydeps-lint:  ## Install python deps necessary to run linters.
	$(INSTALL_PYDEPS) --group lint

install-pydeps-docs:  ## Install python deps necessary to build the doc.
	$(INSTALL_PYDEPS) --group docs

install-pydeps-dev:  ## Install python deps meant for local development.
	${MAKE} install-git-hooks
	$(INSTALL_PYDEPS) --group dev

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

# Return a shell pipeline that outputs one file per line. Uses
# $(FILES) if set, else "git ls-files" with given pattern(s).
_ls = $(if $(FILES), printf '%s\n' $(FILES), git ls-files $(1))

black:  ## Python files linting (via black)
	@$(call _ls,'*.py') | xargs $(PYTHON) -m black --check --safe

ruff:  ## Run ruff linter.
	@$(call _ls,'*.py') | xargs $(PYTHON) -m ruff check --output-format=concise

_pylint:  ## Python pylint (not mandatory, just run it from time to time)
	@$(call _ls,'*.py') | xargs $(PYTHON) -m pylint --rcfile=pyproject.toml --jobs=0 $(ARGS)

lint-rst:  ## Run RsT linter.
	@$(call _ls,'*.rst') | xargs $(PYTHON) scripts/internal/rst_unused_targets.py
	@$(call _ls,'*.rst') | xargs sphinx-lint --enable all --disable line-too-long

lint-toml:  ## Linter for pyproject.toml
	@$(call _ls,'*.toml') | xargs toml-sort --check

lint-all:  ## Run all linters in parallel
	$(MAKE) -j \
		black \
		ruff \
		lint-rst \
		lint-toml

# ===================================================================
# Fixers
# ===================================================================

fix-black:  ## Reformat python code with black.
	@$(call _ls,'*.py') | xargs $(PYTHON) -m black

fix-ruff:  ## Fix ruff errors.
	@$(call _ls,'*.py') | xargs $(PYTHON) -m ruff check --fix --output-format=concise $(ARGS)

fix-toml:  ## Fix pyproject.toml
	@$(call _ls,'*.toml') | xargs toml-sort

fix-all:  ## Run all code fixers.
	$(MAKE) fix-ruff
	$(MAKE) fix-black
	$(MAKE) fix-toml

# ===================================================================
# Distribution
# ===================================================================

# --- create

generate-manifest:  ## Generates MANIFEST.in file.
	$(PYTHON) scripts/internal/generate_manifest.py > MANIFEST.in

create-sdist:  ## Create tar.gz source distribution.
	$(MAKE) generate-manifest
	$(PYTHON_ENV_VARS) $(PYTHON) -m build . --sdist

create-wheels:  ## Create .whl distribution.
	$(MAKE) generate-manifest
	$(PYTHON_ENV_VARS) $(PYTHON) -m build . --wheel

create-dist:  ## Create .tar.gz + .whl distribution.
	$(MAKE) create-sdist
	$(MAKE) create-wheels

# --- check

check-manifest:  ## Check sanity of MANIFEST.in file.
	$(PYTHON) -m check_manifest -v

check-pyproject:  ## Check sanity of pyproject.toml file.
	$(PYTHON) -m validate_pyproject -v pyproject.toml

check-sdist:  ## Check sanity of source distribution.
	$(PYTHON_ENV_VARS) $(PYTHON) -m virtualenv --clear --no-wheel --quiet build/venv
	$(PYTHON_ENV_VARS) build/venv/bin/python -m pip install -v --isolated --quiet dist/*.tar.gz
	$(PYTHON_ENV_VARS) build/venv/bin/python -c "import os; os.chdir('build/venv'); import pyftpdlib"
	$(PYTHON) -m twine check --strict dist/*.tar.gz

check-wheels:  ## Check sanity of wheels.
	$(PYTHON) -m twine check --strict dist/*.whl

check-dist:  ## Run all sanity checks re. to the package distribution.
	$(MAKE) check-manifest
	$(MAKE) check-pyproject
	$(MAKE) check-sdist
	$(MAKE) check-wheels

# --- release

pre-release:  ## Check if we're ready to produce a new release.
	$(MAKE) clean
	$(MAKE) create-dist
	$(MAKE) check-dist
	$(MAKE) install
	@$(PYTHON) -c \
		"import requests, sys; \
		from packaging.version import parse; \
		from pyftpdlib import __ver__; \
		res = requests.get('https://pypi.org/pypi/pyftpdlib/json', timeout=5); \
		versions = sorted(res.json()['releases'], key=parse, reverse=True); \
		sys.exit('version %r already exists on PYPI' % __ver__) if __ver__ in versions else 0"
	@$(PYTHON) -c \
		"from pyftpdlib import __ver__ as ver; \
		history = open('HISTORY.rst').read(); \
		assert ver in history, '%r not found in HISTORY.rst' % ver; \
		assert 'IN DEVELOPMENT' not in history, 'IN DEVELOPMENT found in HISTORY.rst';"

release:  ## Upload a new release.
	$(PYTHON) -m twine upload dist/*.tar.gz
	$(PYTHON) -m twine upload dist/*.whl
	$(MAKE) git-tag-release

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

check-broken-links:  ## Look for broken links in source files.
	git ls-files | xargs $(PYTHON) -Wa scripts/internal/check_broken_links.py

help: ## Display callable targets.
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | sort | awk 'BEGIN {FS = ":.*?## "}; {printf "\033[36m%-20s\033[0m %s\n", $$1, $$2}'
