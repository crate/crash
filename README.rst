=================
The CrateDB Shell
=================

.. image:: https://github.com/crate/crash/workflows/test/badge.svg
    :target: https://github.com/crate/crash/actions
    :alt: Github Actions

.. image:: https://badge.fury.io/py/crash.svg
    :target: http://badge.fury.io/py/crash
    :alt: Version

.. image:: https://img.shields.io/badge/docs-latest-brightgreen.svg
    :target: https://crate.io/docs/reference/crash/
    :alt: Documentation

.. image:: https://coveralls.io/repos/github/crate/crash/badge.svg?branch=master
    :target: https://coveralls.io/github/crate/crash?branch=master
    :alt: Coverage

|


The CrashDB Shell (aka *Crash*) is an interactive `command-line interface`_
(CLI) tool for interacting with CrateDB.

Screenshot
==========

.. image:: https://raw.githubusercontent.com/crate/crash/master/docs/query.png
    :alt: A screenshot of Crash

Installation
============

Python Package
--------------

Crash is available as a `pip`_ package.

To install, run::

    $ pip install crash

Now, run it::

    $ crash

To update, run::

     $ pip install -U crash

If you are not using Python version 3.5 or above, recent version of `pip`_ will
install an earlier version of Crash. This is because newer versions of this
package are not compatible with Python 2.7 or 3.4 and below.

Standalone
----------

Crash is also available as a standalone executable that includes all the
necessary dependencies, and can be run as long as Python (>= 3.5) is available
on your system.

First, download the executable file::

    $ curl -o crash https://cdn.crate.io/downloads/releases/crash_standalone_latest

Then, set the executable bit::

    $ chmod +x crash

Now, run it::

    $ ./crash

If you would like to run ``crash`` from any directory, and without the leading
``./``, the file has to be in a directory that is on your `PATH`_.

Contributing
============

This project is primarily maintained by Crate.io_, but we welcome community
contributions!

See the `developer docs`_ and the `contribution docs`_ for more information.

Help
====

Looking for more help?

- Read the `project docs`_
- Check out our `support channels`_

.. _command-line interface: https://en.wikipedia.org/wiki/Command-line_interface
.. _contribution docs: CONTRIBUTING.rst
.. _Crate.io: http://crate.io/
.. _developer docs: DEVELOP.rst
.. _PATH: https://en.wikipedia.org/wiki/PATH_(variable)
.. _pip: https://pypi.python.org/pypi/pip
.. _project docs: https://crate.io/docs/reference/crash/
.. _support channels: https://crate.io/support/
