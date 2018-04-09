===============
Developer Guide
===============

Setup
=====

This project uses `buildout`_ to set up the development environment.

To start things off, run::

    $ python bootstrap.py

Your system python should be Python 3. If it isn't, try running `python3`
instead. If that doesn't exist, you will have to install Python 3.

Then, run::

    $ ./bin/buildout -N

Then to run your local crash, use::

   $ ./bin/crash

Running Tests
=============

The tests are run using the `zope.testrunner`_::

    $ ./bin/test

This will run all tests using the Python interpreter that was used to bootstrap
buildout.

You can run the tests against multiple Python interpreters with tox_::

    $ ./bin/tox

To do this, you will need (for example) ``python3.3`` (any other interpreters
you want to test against) as well as ``pypy`` on your ``$PATH``.

To run against a single interpreter, you can also do::

    $ ./bin/tox -e py33

Standalone Executable
=====================

To build the standalone executable, run::

    $ ./bin/py devtools/bundle.py crash_standalone

Run the executable like so::

    $ ./crash_standalone

Preparing a Release
===================

To create a new release, you must:

- Update ``__version__`` in ``src/crate/crash/__init__.py``

- Add a section for the new version in the ``CHANGES.txt`` file

- Commit your changes with a message like "prepare release x.y.z"

- Push to origin

- Create a tag by running ``./devtools/create_tag.sh``

- Deploy to PyPI (see below)

- Archive docs for old releases (see below)

PyPI Deployment
---------------

To create the package use::

    $ bin/py setup.py sdist bdist_wheel

Then, use twine_ to upload the package to `PyPI`_::

    $ bin/twine upload dist/*

For this to work, you will need a personal PyPI account that is set up as a
project admin.

You'll also need to create a ``~/.pypirc`` file, like so::

    [distutils]
    index-servers =
      pypi

    [pypi]
    repository=https://upload.pypi.org/legacy/
    username=<USERNAME>
    password=<PASSWORD>

Here, ``<USERNAME>`` and ``<PASSWORD>`` should be replaced with your username
and password, respectively.

If you want to check the PyPI description before uploading, run::

    $ bin/py setup.py check --strict --restructuredtext

Archiving Docs Versions
-----------------------

Check the `versions hosted on ReadTheDocs`_.

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

Sometimes you might find that there are multiple older releases that need to be
archived.

You can archive releases by selecting *Edit*, unselecting the *Active*
checkbox, and then saving.

Standalone Deployment
=====================

The standalone executable is built and deployed by a `Jenkins`_ job.

Writing Documentation
=====================

The docs live under the ``docs`` directory.

The docs are written written with `ReStructuredText`_ and processed with
`Sphinx`_.

Build the docs by running::

    $ bin/sphinx

The output can then be found in the ``out/html`` directory.

The docs are automatically built from Git by `Read the Docs`_ and there is
nothing special you need to do to get the live docs to update.

.. _buildout: https://pypi.python.org/pypi/zc.buildout
.. _Jenkins: http://jenkins-ci.org/
.. _PyPI: https://pypi.python.org/pypi
.. _Read the Docs: http://readthedocs.org
.. _ReStructuredText: http://docutils.sourceforge.net/rst.html
.. _Sphinx: http://sphinx-doc.org/
.. _tox: http://testrun.org/tox/latest/
.. _twine: https://pypi.python.org/pypi/twine
.. _versions hosted on ReadTheDocs: https://readthedocs.org/projects/crash/versions/
.. _zope.testrunner: https://pypi.python.org/pypi/zope.testrunner/4.4.1
