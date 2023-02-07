=================
The CrateDB Shell
=================

.. image:: https://github.com/crate/crash/workflows/test/badge.svg
    :target: https://github.com/crate/crash/actions
    :alt: Outcome of CI

.. image:: https://img.shields.io/pypi/v/crash.svg
    :target: https://pypi.python.org/pypi/crash
    :alt: Most recent version on PyPI

.. image:: https://img.shields.io/pypi/dm/crash.svg
    :target: https://pypi.org/project/crash/
    :alt: Number of downloads per month

.. image:: https://img.shields.io/pypi/pyversions/crash.svg
    :target: https://pypi.python.org/pypi/crash
    :alt: Supported Python versions

.. image:: https://img.shields.io/github/license/crate/crash
    :target: https://github.com/crate/crash/blob/master/LICENSE
    :alt: License

|

The CrateDB Shell (aka *Crash*) is an interactive `command-line interface`_
(CLI) tool for interacting with CrateDB.

Screenshot
==========

.. image:: https://raw.githubusercontent.com/crate/crash/master/docs/query.png
    :alt: A screenshot of Crash


Documentation
=============
The official documentation is available at `CrateDB shell documentation`_.


Installation
============

Python Package
--------------

Crash is available as a `pip`_ package.

To install, run::

    pip install crash

Now, run it::

    crash

To update, run::

    pip install -U crash

Standalone
----------

Crash is also available as a standalone executable that includes all the
necessary dependencies.

First, download the executable file::

    curl -o crash https://cdn.crate.io/downloads/releases/crash_standalone_latest

Then, set the executable bit::

    chmod +x crash

Now, run it::

    ./crash

If you would like to run ``crash`` from any directory, and without the leading
``./``, the file has to be in a directory that is on your `PATH`_.

Contributing
============

This project is primarily maintained by Crate.io_, but we welcome community
contributions!

See the `developer docs`_ and the `contribution docs`_ for more information.

Help
====

Looking for more help? Check out our `support channels`_.


.. _command-line interface: https://en.wikipedia.org/wiki/Command-line_interface
.. _contribution docs: CONTRIBUTING.rst
.. _Crate.io: https://crate.io/
.. _developer docs: DEVELOP.rst
.. _PATH: https://en.wikipedia.org/wiki/PATH_(variable)
.. _pip: https://pypi.python.org/pypi/pip
.. _CrateDB shell documentation: https://crate.io/docs/crate/crash/
.. _support channels: https://crate.io/support/
