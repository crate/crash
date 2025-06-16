.. _commands:

========
Commands
========

Crash has several built-in client commands that you can run from the prompt.

Every command starts with a ``\`` character.

+------------------------+-----------------------------------------------------+
| Command                | Description                                         |
+========================+=====================================================+
| ``\?``                 | List all available commands.                        |
+------------------------+-----------------------------------------------------+
| | ``\c <HOSTS>``,      | Connect to ``<HOSTS>``.                             |
| | ``\connect <HOSTS>`` |                                                     |
|                        |                                                     |
|                        | Same as ``--hosts`` command line option.            |
|                        |                                                     |
|                        | ``HOSTS`` can be a single host, or it can be a      |
|                        | space separated list of hosts.                      |
|                        |                                                     |
|                        | If multiple hosts are specified, Crash will attempt |
|                        | to connect to all of them. The command will succeed |
|                        | if at least one connection is successful.           |
+------------------------+-----------------------------------------------------+
| ``\dt``                | Print a list of tables.                             |
|                        |                                                     |
|                        | The list does not include tables in the ``sys`` and |
|                        | ``information_schema`` schema.                      |
+------------------------+-----------------------------------------------------+
| ``\format <FORMAT>``   | Specifies the output format of the SQL response.    |
|                        |                                                     |
|                        | Same as ``--format`` command line option.           |
|                        |                                                     |
|                        | Available ``<FORMAT>`` values are: ``tabular``,     |
|                        | ``raw``, ``json``, ``json_row``, ``csv`` and        |
|                        | ``mixed``.                                          |
|                        | See :ref:`formats` for details.                     |
+------------------------+-----------------------------------------------------+
| ``\q``                 | Quit the CrateDB shell.                             |
+------------------------+-----------------------------------------------------+
| ``\check <TYPE>``      | Query the ``sys`` tables for failing checks.        |
|                        |                                                     |
|                        | ``TYPE`` can be one of the following:               |
|                        |                                                     |
|                        | - not set (query for failing cluster and node       |
|                        |   checks)                                           |
|                        | - ``nodes`` (query for failing node checks)         |
|                        | - ``cluster`` (query for failing cluster checks)    |
+------------------------+-----------------------------------------------------+
| ``\pager``             | Use apps like ``jless`` or ``pspg`` to              |
|                        | view the result sets. See also :ref:`use-pager`.    |
+------------------------+-----------------------------------------------------+
| ``\r <FILENAME>``      | Reads statements from ``<FILENAME>`` and execute    |
|                        | them.                                               |
+------------------------+-----------------------------------------------------+
| ``\sysinfo``           | Query the ``sys`` tables for system and cluster     |
|                        | information.                                        |
+------------------------+-----------------------------------------------------+
| ``\autocomplete``      | Turn autocomplete feature on or off.                |
|                        |                                                     |
|                        | Works as a toggle.                                  |
+------------------------+-----------------------------------------------------+
| ``\autocapitalize``    | Turn automatic capitalization for SQL keywords or   |
|                        | off.                                                |
|                        |                                                     |
|                        | Works as a toggle.                                  |
+------------------------+-----------------------------------------------------+
