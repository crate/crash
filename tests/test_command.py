# -*- coding: utf-8 -*-
# vim: set fileencodings=utf-8

from unittest import TestCase

from verlib2 import Version

from crate.crash.command import (
    Result,
    _decode_timeout,
    _decode_timeouts,
    get_information_schema_query,
    host_and_port,
    stmt_type,
)
from crate.crash.outputs import OutputWriter


class OutputWriterTest(TestCase):

    def setUp(self):
        self.ow = OutputWriter(writer=None, is_tty=False)

    def test_mixed_format_float_precision(self):
        expected = 'foo | 152462.70754934277'
        result = Result(cols=['foo'],
                        rows=[[152462.70754934277]],
                        rowcount=1,
                        duration=1,
                        output_width=80)
        self.assertEqual(
            next(self.ow.mixed(result)).rstrip(), expected)

    def test_mixed_format_utf8(self):
        expected = 'name | Großvenediger'
        result = Result(cols=['name'],
                        rows=[['Großvenediger']],
                        rowcount=1,
                        duration=1,
                        output_width=80)
        self.assertEqual(
            next(self.ow.mixed(result)).rstrip(), expected)

    def test_tabular_format_float_precision(self):
        expected = '152462.70754934277'

        result = Result(cols=['foo'],
                        rows=[[152462.70754934277]],
                        rowcount=1,
                        duration=1,
                        output_width=80)

        # output is
        # +---
        # | header
        # +----
        # | value
        # get the row with the value in it
        output = self.ow.tabular(result).split('\n')[3]
        self.assertEqual(
            output.strip('|').strip(' '), expected)

    def test_tabular_format_content_trimming(self):
        """
        Proof that tabular output renders all records, even if some cells are
        empty or only made of whitespace or other non-printable characters.
        """
        records = [[""], [" "], ["\t"]]

        result = Result(cols=['foo'],
                        rows=records,
                        rowcount=len(records),
                        duration=1,
                        output_width=80)

        # Render in tabular format.
        output = self.ow.tabular(result)

        # Separate by newlines and remove header and footer, essentially
        # keeping all "record" lines.
        lines = [line for line in output.split("\n")[3:]
                 if line.startswith("|")]

        # Check.
        self.assertEqual(
            len(records), len(lines),
            msg="Tabular format does not reflect correct number of records")


class CommandLineArgumentsTest(TestCase):

    def test_short_hostnames(self):
        # both host and port are provided
        self.assertEqual(host_and_port('localhost:4321'), 'localhost:4321')
        # only host is provided
        # default port is used
        self.assertEqual(host_and_port('localhost'), 'localhost:4200')
        # only port is provided
        # localhost is used
        self.assertEqual(host_and_port(':4000'), 'localhost:4000')
        # neither host nor port are provided
        # default host and default port are used
        self.assertEqual(host_and_port(':'), 'localhost:4200')


class CommandUtilsTest(TestCase):

    def test_stmt_type(self):
        # regular multi word statement
        self.assertEqual(stmt_type('SELECT 1;'), 'SELECT')
        # regular single word statement
        self.assertEqual(stmt_type('BEGIN;'), 'BEGIN')
        # statements with trailing or leading spaces/tabs/linebreaks
        self.assertEqual(stmt_type(' SELECT 1 ;'), 'SELECT')
        self.assertEqual(stmt_type('\nSELECT\n1\n;\n'), 'SELECT')

    def test_decode_timeout_success(self):
        self.assertEqual(_decode_timeout(None), None)
        self.assertEqual(_decode_timeout(-1), None)
        self.assertEqual(_decode_timeout(42.42), 42.42)
        self.assertEqual(_decode_timeout("42.42"), 42.42)

    def test_decode_timeouts_success(self):
        # `_decode_timeouts` returns an urllib3.Timeout instance.
        self.assertEqual(str(_decode_timeouts(None)), 'Timeout(connect=None, read=None, total=None)')
        self.assertEqual(str(_decode_timeouts(-1)), 'Timeout(connect=None, read=None, total=None)')
        self.assertEqual(str(_decode_timeouts("-1")), 'Timeout(connect=None, read=None, total=None)')
        self.assertEqual(str(_decode_timeouts(42.42)), 'Timeout(connect=42.42, read=None, total=None)')
        self.assertEqual(str(_decode_timeouts("42.42")), 'Timeout(connect=42.42, read=None, total=None)')
        self.assertEqual(str(_decode_timeouts((42.42, 84.84))), 'Timeout(connect=42.42, read=84.84, total=None)')
        self.assertEqual(str(_decode_timeouts('42.42, 84.84')), 'Timeout(connect=42.42, read=84.84, total=None)')
        self.assertEqual(str(_decode_timeouts((-1, 42.42))), 'Timeout(connect=None, read=42.42, total=None)')
        self.assertEqual(str(_decode_timeouts("-1, 42.42")), 'Timeout(connect=None, read=42.42, total=None)')

    def test_decode_timeouts_failure(self):
        with self.assertRaises(TypeError) as ecm:
            _decode_timeouts({})
        self.assertEqual(str(ecm.exception), "Cannot decode timeout value from type `<class 'dict'>`, "
                                             "expected format `<connect_sec>,<read_sec>`")

        with self.assertRaises(ValueError) as ecm:
            _decode_timeouts([])
        self.assertEqual(str(ecm.exception), "Cannot decode timeout `[]`, "
                                             "expected format `<connect_sec>,<read_sec>`")


class TestGetInformationSchemaQuery(TestCase):

    def test_low_version(self):
        lowest_server_version = Version("0.56.4")
        query = get_information_schema_query(lowest_server_version)
        self.assertEqual(""" select count(distinct(table_name))
                as number_of_tables
            from information_schema.tables
            where schema_name
            not in ('information_schema', 'sys', 'pg_catalog') """, query)

    def test_high_version(self):
        lowest_server_version = Version("1.0.4")
        query = get_information_schema_query(lowest_server_version)
        self.assertEqual(""" select count(distinct(table_name))
                as number_of_tables
            from information_schema.tables
            where table_schema
            not in ('information_schema', 'sys', 'pg_catalog') """, query)
