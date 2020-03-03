===============
Developer Guide
===============

Setup
=====

Create a virtualenv and install the project::

    $ python3 -m venv venv
    $ venv/bin/python -m pip install -U -e ".[test]"

Afterwards you can launch crash::

    $ venv/bin/crash

Running Tests
=============

The tests are run using the `unittest`_::

    $ venv/bin/python -m unittest -v


If you install tox_, you can also run tests against multiple Python interpreters::

    $ venv/bin/python -m pip install tox
    $ venv/bin/tox

But this requires you to have the python interpreters available in ``$PATH``.

To run against a single interpreter, you can also do::

    $ venv/bin/tox -e py33

Standalone Executable
=====================

To build a standalone executable, you can use shiv_::

    $ shiv -p /usr/bin/python -c crash -o crash.pyz crash

Run the executable like so::

    $ ./crash.pyz

Preparing a Release
===================

To create a new release, you must:

- Update ``__version__`` in ``src/crate/crash/__init__.py``

- Add a section for the new version in the ``CHANGES.txt`` file

- Commit your changes with a message like "prepare release x.y.z"

- Push to origin

- Create a tag by running ``./devtools/create_tag.sh``

- Pushing a tag triggers a Github Workflow which creates a new `Release
  <https://github.com/crate/crash/releases>`_. Publish this release to trigger
  a deployment to PyPi and to generate a standalone crash bundle.

- Archive docs for old releases (see below)


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

To make changes to the RTD configuration (e.g., to activate or deactivate a
release version), please contact the `@crate/docs`_ team.

Standalone Deployment
=====================

The standalone executable is built by a Github Workflow.


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

.. _@crate/docs: https://github.com/orgs/crate/teams/docs
.. _buildout: https://pypi.python.org/pypi/zc.buildout
.. _PyPI: https://pypi.python.org/pypi
.. _Read the Docs: http://readthedocs.org
.. _ReStructuredText: http://docutils.sourceforge.net/rst.html
.. _Sphinx: http://sphinx-doc.org/
.. _tox: http://testrun.org/tox/latest/
.. _twine: https://pypi.python.org/pypi/twine
.. _versions hosted on ReadTheDocs: https://readthedocs.org/projects/crash/versions/
.. _zope.testrunner: https://pypi.python.org/pypi/zope.testrunner/4.4.1
