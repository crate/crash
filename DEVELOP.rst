=================
Crash Development
=================

Development Setup
=================

To get a development environment crash uses `buildout
<https://pypi.python.org/pypi/zc.buildout>`_.

Run `bootstrap.py`::

    python bootstrap.py

And afterwards run buildout::

    ./bin/buildout -N


Start the ``crash`` shell with::

   ./bin/crash

Running Tests
=============

The tests are run using the `zope.testrunner
<https://pypi.python.org/pypi/zope.testrunner/4.4.1>`_::

    ./bin/test

This will run all tests using the python interpreter that was used to
bootstrap buildout.

In addition to that it is also possible to run the test case against multiple
python interpreter using `tox <http://testrun.org/tox/latest/>`_::

    ./bin/tox

This required the interpreters `python2.7`, `python3.3` and `pypy` to be
available in `$PATH`. To run against a single interpreter tox can also be
invoked like this::

    ./bin/tox -e py33

Bundling
========

It is possible to build an executable zip archive, which starts crash
like this:

    ./bin/py devtools/bundle.py crash_standalone

You can then start the generated file like this::

    ./crash_standalone

Preparing a new Release
=======================

Before creating a new Crash distribution, a new version and tag need to be created:

 - Update the ``__version__`` in ``src/crate/crash/__init__.py``.

 - Add a note for the new version at the ``CHANGES.txt`` file.

 - Commit e.g. using message 'prepare release x.x.x'.

 - Push to origin

 - Create a tag using the ``create_tag.sh`` script
   (run ``./devtools/create_tag.sh``).

Deployment to PyPi
------------------

To create the packages use::

    bin/py setup.py sdist bdist_wheel

and then use `twine <https://pypi.python.org/pypi/twine>`_ to upload the
packages::

    twine upload dist/*

If twine is not installed locally the regular setup.py upload can also be used,
but does only support plaintext authentication::

    bin/py setup.py upload

Release Crate Standalone
-------------------------

Building and releasing the standalone version is done by a Jenkins_ job.

Writing Documentation
=====================

The documentation is maintained under the ``docs`` directory and
written in ReStructuredText_ and processed with Sphinx_.

Normally the documentation is built by `Read the Docs`_.
However if you work on the documentation you can run sphinx
directly, which can be done by just running ``bin/sphinx``.
The output can then be found in the ``out/html`` directory.

.. _Jenkins: http://jenkins-ci.org/

.. _Sphinx: http://sphinx-doc.org/

.. _ReStructuredText: http://docutils.sourceforge.net/rst.html

.. _`Read the Docs`: http://readthedocs.org
