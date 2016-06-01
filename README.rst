.. image:: https://cdn.crate.io/web/2.0/img/crate-logo_330x72.png
   :width: 165px
   :height: 36px
   :alt: Crate.IO
   :target: https://crate.io

|

.. image:: https://travis-ci.org/crate/crash.svg?branch=master
        :target: https://travis-ci.org/crate/crash
        :alt: Test

.. image:: https://badge.fury.io/py/crash.png
    :target: http://badge.fury.io/py/crash
    :alt: Version

.. image:: https://pypip.in/download/crash/badge.png
    :target: https://pypi.python.org/pypi/crash/
    :alt: Downloads

.. image:: https://img.shields.io/badge/docs-latest-brightgreen.svg
    :target: https://crate.io/docs/reference/crash/

.. image:: https://img.shields.io/pypi/pyversions/crash.svg
   :target: https://pypi.python.org/pypi/crash/
   :alt: Python Version


========
Overview
========

This is the Crate shell called ``crash``.

Installation
============

Installing via pip
------------------

To install crash via `pip <https://pypi.python.org/pypi/pip>`_ use
the following command::

    $ pip install crash

To update use::

    $ pip install -U crash

Standalone
----------

There is also a single file executable that includes all dependencies and can
be run as long as python (>= 2.7) is available on the system.

`Download Crash bundle
<https://cdn.crate.io/downloads/releases/crash_standalone_latest>`_

The bundle can then be executed using python::

    python ./crash_standalone_latest

Or::

    chmod +x ./crash_standalone_latest
    ./crash_standalone_latest


Crash supported Python 2.6 until 0.16. `Use Crash 0.16.0
<https://cdn.crate.io/downloads/releases/crash_standalone_0.16.0>`_ if you're
running Python 2.6

Usage
-----

If the package was installed using `pip` the shell can be started by
running the command `crash` in a terminal.

For usage information and command line options invoke::

    crash --help

Or consult the `crash documentation 📚 <https://crate.io/docs/reference/crash/>`_.

Are you a Developer?
====================

You can build Crash on your own with the latest version hosted on GitHub.
To do so, please refer to ``DEVELOP.rst`` for further information.

Help & Contact
==============

Do you have any questions? Or suggestions? We would be very happy
to help you. So, feel free to swing by our Community on Slack_.
Or for further information and official contact please
visit `https://crate.io/ <https://crate.io/>`_.

.. _Slack: https://crate.io/docs/support/slackin/

License
=======

Copyright 2013-2014 CRATE Technology GmbH ("Crate")

Licensed to CRATE Technology GmbH ("Crate") under one or more contributor
license agreements.  See the NOTICE file distributed with this work for
additional information regarding copyright ownership.  Crate licenses
this file to you under the Apache License, Version 2.0 (the "License");
you may not use this file except in compliance with the License.  You may
obtain a copy of the License at

  http://www.apache.org/licenses/LICENSE-2.0

Unless required by applicable law or agreed to in writing, software
distributed under the License is distributed on an "AS IS" BASIS, WITHOUT
WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.  See the
License for the specific language governing permissions and limitations
under the License.

However, if you have executed another commercial license agreement
with Crate these terms will supersede the license and you may use the
software solely pursuant to the terms of the relevant commercial agreement.
