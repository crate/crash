.. _formats:

================
Response formats
================

Crash supports multiple output formats.

You can select between these output formats using either :ref:`commands` or
:ref:`options`.

.. rubric:: Table of contents

.. contents::
   :local:

.. _format-tabluar:

``tabular``
===========

This is the default output format.

Query results are printed as a plain text formatted table.

For example:

.. code-block:: text

    +--------+---------+
    | name   | version |
    +--------+---------+
    | crate1 | 0.46.3  |
    +--------+---------+
    | crate2 | 0.46.3  |
    +--------+---------+

.. _format-json:

``json``
========

Query results are printed as a `JSON`_ formatted object array. Keys hold the
column name, and the key value holds the row value.

.. TIP::

   This format is useful for dumping results to a file that can be parsed by
   another tool.

Here's an example::

    [
      {
        "name": "crate1",
        "version": "0.46.3"
      },
      {
        "name": "crate2",
        "version": "0.46.3"
      }
    ]


.. _format-json_row:

``json_row``
============

Query results are printed as a JSON formatted object array, like the
:ref:`format-json` format. However, each row gets its own line. For example::

  {"name": "crate1", "version": "0.46.3"}
  {"name": "crate2", "version": "0.46.3"}


.. TIP::

   This format is compatible with `COPY FROM`_ for re-importing data.

.. _format-csv:

``csv``
=======

Query results are printed as `comma separated values`_ (CSV).

Specifically:

- The delimiter is a comma (``,``)
- The quote character is an apostrophe (``'``)
- The escape character is a reverse solidus (``\``)

The first line of the CSV output contains the name of the selected columns::

    name,version
    crate1,0.46.3
    crate2,0.46.3


``object`` types and ``array`` types are returned as a JSON string::

    name,settings[\'udc\']
    crate,'{"enabled": true, "initial_delay": "10m"}'

.. _format-raw:

``raw``
=======

Query results are printed as the raw JSON produced by `the CrateDB Python
client library`_ used by Crash.

This JSON structure provides:

- A ``rows`` key for holding a list of rows
- A ``cols`` key for holding a list of column titles
- A ``rowcount`` key which holds the total number of rows returned
- A ``duration`` key which holds the total duration of the query execution in
  seconds

Here's an example::

    {
      "rows": [
        [
          "crate1",
          "0.46.0"
        ],
        [
          "crate2",
          "0.46.0"
        ]
      ],
      "cols": [
        "name",
        "0.46.3"
      ],
      "rowcount": 1,
      "duration": 0.00477246
    }

.. _format-mixed:

``mixed``
=========

Query results are printed as a plain text formatted table.

However, unlike the :ref:`format-tabluar` format, each row (separated by ``-``
characters) contains the column title and column value (separated by the ``|``
character).

Example::

    name    | crate1
    version | 0.46.3
    ---------------------------------------------------------------
    name    | crate2
    version | 0.46.3
    ---------------------------------------------------------------

.. _comma separated values: https://en.wikipedia.org/wiki/Comma-separated_values
.. _COPY FROM: https://cratedb.com/docs/crate/reference/en/latest/general/dml.html#import-and-export
.. _JSON: https://www.json.org/
.. _the CrateDB Python client library: https://cratedb.com/docs/python/en/latest/
