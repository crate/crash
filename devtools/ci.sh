#!/bin/sh

set -e -x

isort --check --diff src/crate/ tests/ setup.py
flake8 src/crate/crash
coverage run -m unittest -v
