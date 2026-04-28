# -*- coding: utf-8 -*-
# vim: set fileencodings=utf-8

from argparse import ArgumentTypeError
from unittest import TestCase

from verlib2 import Version

from crate.crash.command import (
    Result,
    _decode_timeout,
    _decode_timeouts,
    collect_url_params,
    extract_url_params,
    get_information_schema_query,
    get_parser,
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


class UrlParamsTest(TestCase):

    def test_extract_url_params(self):
        for value, expected in [
            ('false', False), ('False', False), ('0', False), ('no', False),
            ('true', True), ('1', True), ('yes', True),
        ]:
            cleaned, params = extract_url_params(
                f'https://u:p@h:4200/?foo=bar&verify_ssl={value}')
            self.assertEqual(cleaned, 'https://u:p@h:4200/?foo=bar')
            self.assertEqual(params, {'verify_ssl': expected})

        for host in ('localhost:4200', ':4200', ':', 'localhost',
                     'https://h:4200/', 'postgresql://h/?verify_ssl=false',
                     'localhost:4200?foo=bar'):
            self.assertEqual(extract_url_params(host), (host, {}))

        with self.assertRaises(ArgumentTypeError):
            extract_url_params('https://h/?verify_ssl=maybe')

    def test_first_host_wins(self):
        _, params = collect_url_params([
            'https://a/?verify_ssl=false',
            'https://b/?verify_ssl=true',
        ])
        self.assertIs(params['verify_ssl'], False)

    def test_verify_ssl_precedence(self):
        # --verify-ssl > url > default True.
        def resolve(argv):
            args = get_parser().parse_args(argv)
            _, url_params = collect_url_params(args.hosts)
            return url_params.get('verify_ssl', True) \
                if args.verify_ssl is None else args.verify_ssl

        self.assertIs(resolve(['--hosts', 'h:4200']), True)
        self.assertIs(
            resolve(['--hosts', 'https://h/?verify_ssl=false']), False)
        self.assertIs(
            resolve(['--hosts', 'https://h/?verify_ssl=false',
                     '--verify-ssl', 'true']), True)
        self.assertIs(
            resolve(['--hosts', 'https://h/?verify_ssl=true',
                     '--verify-ssl', 'false']), False)


class CommandUtilsTest(TestCase):

    def test_stmt_type(self):
        # regular multi word statement
        self.assertEqual(stmt_type('SELECT 1;'), 'SELECT')
        # regular single word statement
        self.assertEqual(stmt_type('BEGIN;'), 'BEGIN')
        # statements with trailing or leading spaces/tabs/linebreaks
        self.assertEqual(stmt_type(' SELECT 1 ;'), 'SELECT')
        self.assertEqual(stmt_type('\nSELECT\n1\n;\n'), 'SELECT')
        # statements with trailing or leading comments
        self.assertEqual(stmt_type('/* foo */ SELECT 1;'), 'SELECT')
        self.assertEqual(stmt_type('SELECT 1; /* foo */'), 'SELECT')
        self.assertEqual(stmt_type('-- foo \n SELECT 1;'), 'SELECT')
        self.assertEqual(stmt_type('SELECT 1; -- foo'), 'SELECT')
        # statements with arguments as part of the command
        self.assertEqual(stmt_type('/* foo */ DENY DQL, DML, DDL, AL ON SCHEMA sys TO test;'), 'DENY')

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
