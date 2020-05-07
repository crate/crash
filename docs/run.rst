.. _run:

=============
Running Crash
=============

This document covers the basics of running Crash from the `command-line`_.

.. NOTE::

   For help using Crash for the first time, check out :ref:`getting-started`.

.. _options:

.. rubric:: Table of contents

.. contents::
   :local:

Command-line options
====================

The ``crash`` executable supports multiple command-line options:

+-------------------------------+----------------------------------------------+
| Argument                      | Description                                  |
+===============================+==============================================+
| | ``-h``,                     | Print the help message and exit.             |
| | ``--help``                  |                                              |
+-------------------------------+----------------------------------------------+
| | ``-v``,                     | Print debug information to `STDOUT`_.        |
| | ``--verbose``               |                                              |
+-------------------------------+----------------------------------------------+
| ``--version``                 | Print the Crash version and exit.            |
+-------------------------------+----------------------------------------------+
| ``--sysinfo``                 | Print system and cluster information.        |
+-------------------------------+----------------------------------------------+
| | ``-U <USERNAME>``,          | Authenticate as ``<USERNAME>``.              |
| | ``--username <USERNAME>``   |                                              |
+-------------------------------+----------------------------------------------+
| | ``-W``,                     | Force a password prompt.                     |
| | ``--password``              |                                              |
|                               | If not set, a password prompt happens when   |
|                               | required.                                    |
+-------------------------------+----------------------------------------------+
| | ``-c <STATEMENT>``,         | Execute the ``<STATEMENT>`` and exit.        |
| | ``--command <STATEMENT>``   |                                              |
+-------------------------------+----------------------------------------------+
| ``--hosts <HOSTS>``           | Connect to ``<HOSTS>``.                      |
|                               |                                              |
|                               | ``<HOSTS>`` can be a single host, or it can  |
|                               | be a  space separated list of hosts.         |
|                               |                                              |
|                               | If multiple hosts are specified, Crash will  |
|                               | attempt to connect to all of them. The       |
|                               | command will succeed if at least one         |
|                               | connection is successful.                    |
+-------------------------------+----------------------------------------------+
| ``--history <FILENAME>``      | Use ``<FILENAME>`` as a history file.        |
|                               |                                              |
|                               | Defaults to the ``crash_history`` file in    |
|                               | the :ref:`user configuration directory       |
|                               | <user-conf-dir>`.                            |
+-------------------------------+----------------------------------------------+
| ``--config <FILENAME>``       | Use ``<FILENAME>`` as a configuration file.  |
|                               |                                              |
|                               | Defaults to the ``crash.cfg`` file in the    |
|                               | :ref:`user configuration directory           |
|                               | <user-conf-dir>`.                            |
+-------------------------------+----------------------------------------------+
| ``--format <FORMAT>``         | The output ``<FORMAT>`` of the SQL response. |
|                               |                                              |
|                               | Available formats are: ``tabular``, ``raw``, |
|                               | ``json``, ``json_row``, ``csv`` and          |
|                               | ``mixed``.                                   |
+-------------------------------+----------------------------------------------+
| ``--schema <SCHEMA>``         | The default schema that should be used for   |
|                               | statements.                                  |
+-------------------------------+----------------------------------------------+
| | ``-A`` ,                    | Disable SQL keywords autocompletion.         |
| | ``--no-autocomplete``       |                                              |
|                               | Autocompletion requires a minimum terminal   |
|                               | height of eight lines due to size of the     |
|                               | dropdown overlay for suggestions. Disabling  |
|                               | autocompletion removes this limitation.      |
+-------------------------------+----------------------------------------------+
| | ``-a`` ,                    | Enable automatic capitalization of SQL       |
| | ``--autocapitalize``        | keywords while typing.                       |
|                               |                                              |
|                               | This feature is experimental and may be      |
|                               | removed in future versions.                  |
+-------------------------------+----------------------------------------------+
| ``--verify-ssl``              | Force the verification of the server SSL     |
|                               | certificate.                                 |
+-------------------------------+----------------------------------------------+
| ``--cert-file <FILENAME>``    | Use ``<FILENAME>`` as the client certificate |
|                               | file.                                        |
+-------------------------------+----------------------------------------------+
| ``--key-file <FILENAME>``     | Use ``<FILENAME>`` as the client certificate |
|                               | key file.                                    |
+-------------------------------+----------------------------------------------+
| ``--ca-cert-file <FILENAME>`` | Use ``<FILENAME>`` as the certificate        |
|                               | authority (CA) certificate file (used to     |
|                               | verify the server certificate).              |
+-------------------------------+----------------------------------------------+

Examples
--------

Here's an example command:

.. code-block:: console

    sh$ crash --hosts node1.example.com \
                    node2.example.com \
            -c "SELECT * FROM sys.nodes" \
            --format json \
        > output.json

This command will:

- Run ``crash``, which will:

  - Attempt to connect to ``node1.example.com`` and ``node2.example.com``

  - Execute ``SELECT * FROM sys.nodes``

  - Print the results as JSON

- Redirect output to the ``output.json`` file

.. TIP::

   Instead of `redirecting`_ to a file, you can `pipe`_ into a tool like `jq`_
   for for further processing of the response.

We can modify this command to use SSL, like so:

.. code-block:: console

    sh$ crash --hosts node1.example.com \
                    node2.example.com \
            --verify-ssl true \
            --cert-file ~/.certs/client.crt \
            --key-file ~/.certs/client.key \
            --ca-cert-file ~/.certs/server-ca.crt \
            -c "SELECT * FROM sys.nodes" \
            --format json \
        > output.json

Here, we're using:

- ``~/.certs/client.crt`` as the client certificate
- ``~/.certs/client.key`` as the client certificate key
- ``~/.certs/server-ca.crt`` as the server CA certificate

.. _user-conf-dir:

User configuration directory
============================

The ``crash`` executable looks for its configuration file and history file in
the appropriate user configuration directory for your operating system.

For Linux, that is::

    ~/.config/Crate

For macOS, it is::

    ~/Library/Application Support/Crate

And for Microsoft Windows, it is::

    C:\\Users\user\AppData\Local\Crate\Crate

.. _env-vars:

Environment variables
=====================

The ``crash`` executable will take configuration from the environment.

At the moment, only one environment variable is supported.

:``CRATEPW``: The password to be used if password authentication is necessary.

              .. CAUTION::

                 Storing passwords in the environment is not always a good idea
                 from a security perspective.

You can set ``CRATEPW`` like so:

.. code-block:: console

    sh$ export CRATEPW=<PASSWORD>

Here, ``<PASSWORD>`` should be replaced with the password you want to use.

For the duration of your current session, invokations of ``crash`` will use this
password when needed (unless you force a password prompt with ``--password`` or
``-W``).

.. _status-messages:

Status messages
===============

When used interactively, Crash will print a status message after every
successfully executed query.

.. NOTE::

   When used non-interactively, these messages are omitted.

   Examples of non-interactive use include: executing ``crash`` in a shell
   script, `redirecting`_ output to a file, or `piping`_ output into a another
   command

If the query alters rows, the status message looks like this::

    <STATEMENT>, <NUMBER> row(s) affected (<DURATION> sec)

If the query returns rows, the message looks like this::

    <STATEMENT> <NUMBER> row(s) in set (<DURATION> sec)

In both instances:

- ``<STATEMENT>`` is the query keyword (e.g. ``CREATE``, ``INSERT``,
  ``UPDATE``, ``DELETE``, ``SELECT``, and so on)

- ``<NUMBER>`` is the number of rows (``-1`` for queries that do not affect any
  rows or if the row count is unknown)

- ``<DURATION>`` is the total number of seconds the query took to execute on the
  cluster

.. _command-line: https://en.wikipedia.org/wiki/Command-line_interface
.. _jq: http://stedolan.github.io/jq/
.. _pipe: https://www.wikiwand.com/en/Pipeline_(Unix)
.. _piping: https://www.wikiwand.com/en/Pipeline_(Unix)
.. _redirecting: https://www.tldp.org/LDP/abs/html/io-redirection.html
.. _STDOUT: https://en.wikipedia.org/wiki/Standard_streams
.. _user configuration directory: https://specifications.freedesktop.org/basedir-spec/basedir-spec-latest.html
