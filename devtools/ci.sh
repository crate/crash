#!/bin/sh

set -e -x

isort --check --diff src/crate/ tests/ setup.py
flake8 src/crate/crash
export TESTCONTAINERS_RYUK_DISABLED=true
coverage run -m unittest -v
