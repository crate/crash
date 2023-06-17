#!/bin/sh

set -e -x

isort --check --diff crate/ tests/ setup.py
flake8 crate/crash
coverage run -m unittest -v