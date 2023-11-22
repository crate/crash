.. highlight:: sh

===============
Developer Guide
===============


Setup
=====

Create a virtualenv and install the project::

    python3 -m venv .venv
    source .venv/bin/activate
    pip install --upgrade --editable=".[test,devel]"

Afterwards you can launch crash::

    crash

Continuous Integration
======================

You can run all CI steps using::

    ./devtools/ci.sh

Individual steps are described below.

Linting
-------

You can check if your code is compliant to the project's standard using::

    isort --check --diff crate/ tests/ setup.py
    flake8 crate/crash

Running Tests
-------------

The tests are run using the `unittest`_ module::

    python -m unittest -v

In order to adjust the CrateDB version used for running the tests, amend the
environment variable ``CRATEDB_VERSION`` like::

    export CRATEDB_VERSION=5.5.0

If you install tox_, you can also run tests against multiple Python interpreters::

    pip install tox
    tox

This requires you to have the python interpreters available in ``$PATH``.

To run against a single interpreter, you can also do::

    tox -e py33

Standalone Executable
=====================

To build a standalone executable, you can use shiv_::

    shiv -p /usr/bin/python -c crash -o crash.pyz crash

Run the executable like so::

    ./crash.pyz


Standalone Deployment
=====================

The standalone executable is built and deployed by a `Jenkins`_ job.


Documentation
=============

The documentation is written using `Sphinx`_ and `ReStructuredText`_.


Working on the documentation
----------------------------

Python 3.7 or higher is required.

Change into the ``docs`` directory::

    cd docs

For help, run::

    make

    Crate Docs Build

    Run `make <TARGET>`, where <TARGET> is one of:

      dev     Run a Sphinx development server that builds and lints the
              documentation as you edit the source files

      html    Build the static HTML output

      check   Build, test, and lint the documentation

      reset   Reset the build cache

You must install `fswatch`_ to use the ``dev`` target.


Continuous integration and deployment
-------------------------------------

|build| |travis| |rtd|

Travis CI is `configured`_ to run ``make check`` from the ``docs`` directory.
Please do not merge pull requests until the tests pass.

`Read the Docs`_ (RTD) automatically deploys the documentation whenever a
configured branch is updated.


Preparing a Release
===================

To create a new release, you must:

- Update ``__version__`` in ``crate/crash/__init__.py``

- Add a section for the new version in the ``CHANGES.txt`` file

- Commit your changes with a message like "prepare release x.y.z"

- Push to origin

- Create a tag by running ``./devtools/create_tag.sh``.
  It will push a new tag to GitHub, which in turn will trigger a GitHub action
  that releases the new version to PyPI at https://pypi.org/project/crash/

- Designate the new release on GitHub at https://github.com/crate/crash/releases

- Run the ``crash_standalone`` job on Jenkins in order to produce and publish
  a self-contained executable to https://cdn.crate.io/downloads/releases/

- Archive docs for old releases (see below)


Archiving Docs Versions
-----------------------

Check the `versions`_ hosted on ReadTheDocs.

We should only be hosting the docs for ``latest``, the last three minor release
branches of the last major release, and the last minor release branch
corresponding to the last two major releases.

For example:

- ``latest``
- ``0.22``
- ``0.21``
- ``0.20``

Because this project has not yet had a major release, as of yet, there are no
major releases before ``0`` to include in this list.

To make changes to the RTD configuration (e.g., to activate or deactivate a
release version), please contact the `@crate/tech-writing`_ team.


.. _@crate/tech-writing: https://github.com/orgs/crate/teams/tech-writing
.. _configured: https://github.com/crate/crash/blob/master/.travis.yml
.. _fswatch: https://github.com/emcrisostomo/fswatch
.. _Jenkins: https://jenkins-ci.org/
.. _PyPI: https://pypi.python.org/pypi
.. _Read the Docs: https://readthedocs.org/
.. _ReStructuredText: https://docutils.sourceforge.net/rst.html
.. _Sphinx: https://sphinx-doc.org/
.. _tox: https://testrun.org/tox/latest/
.. _twine: https://pypi.python.org/pypi/twine
.. _versions: https://readthedocs.org/projects/crash/versions/
.. _zope.testrunner: https://pypi.python.org/pypi/zope.testrunner/4.4.1


.. |build| image:: https://img.shields.io/endpoint.svg?color=blue&url=https%3A%2F%2Fraw.githubusercontent.com%2Fcrate%2Fcrash%2Fmaster%2Fdocs%2Fbuild.json
    :alt: Build version
    :target: https://github.com/crate/crash/blob/master/docs/build.json

.. |travis| image:: https://img.shields.io/travis/crate/crash.svg?style=flat
    :alt: Travis CI status
    :target: https://travis-ci.org/crate/crash

.. |rtd| image:: https://readthedocs.org/projects/crash/badge/?version=latest
    :alt: Read The Docs status
    :target: https://readthedocs.org/projects/crash
