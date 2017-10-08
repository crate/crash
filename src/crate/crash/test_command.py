# -*- coding: utf-8 -*-
# vim: set fileencodings=utf-8

import sys
import os
import re
import ssl
from unittest import TestCase
from six import PY2, StringIO
import tempfile
from io import TextIOWrapper
from mock import patch, Mock
from crate.client.exceptions import ProgrammingError
from urllib3.exceptions import LocationParseError

from .command import CrateCmd, main, get_stdin, noargs_command, Result, \
    host_and_port, get_information_schema_query, stmt_type, _create_cmd, \
    get_parser, parse_args
from .outputs import _val_len as val_len, OutputWriter
from .printer import ColorPrinter
from .commands import Command
from distutils.version import StrictVersion


def fake_stdin(data):
    if PY2:
        stdin = tempfile.TemporaryFile()
    else:
        stdin = TextIOWrapper(tempfile.TemporaryFile())
    stdin.write(data)
    stdin.flush()
    stdin.seek(0)
    return stdin


class OutputWriterTest(TestCase):

    def setUp(self):
        self.ow = OutputWriter(writer=None, is_tty=False)

    def test_mixed_format_float_precision(self):
        expected = u'foo | 152462.70754934277'
        result = Result(cols=['foo'],
                        rows=[[152462.70754934277]],
                        rowcount=1,
                        duration=1,
                        output_width=80)
        self.assertEqual(
            next(self.ow.mixed(result)).rstrip(), expected)

    def test_mixed_format_utf8(self):
        expected = u'name | Großvenediger'
        result = Result(cols=['name'],
                        rows=[[u'Großvenediger']],
                        rowcount=1,
                        duration=1,
                        output_width=80)
        self.assertEqual(
            next(self.ow.mixed(result)).rstrip(), expected)

    def test_tabular_format_float_precision(self):
        expected = u'152462.70754934277'

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
        self.assertEquals(stmt_type('SELECT 1;'), 'SELECT')
        # regular single word statement
        self.assertEquals(stmt_type('BEGIN;'), 'BEGIN')
        # statements with trailing or leading spaces/tabs/linebreaks
        self.assertEquals(stmt_type(' SELECT 1 ;'), 'SELECT')
        self.assertEquals(stmt_type('\nSELECT\n1\n;\n'), 'SELECT')

class CommandTest(TestCase):

    def _output_format(self, format, func, query="select name from sys.cluster"):
        orig_argv = sys.argv[:]
        try:
            sys.argv = ["testcrash",
                        "-c", query,
                        "--hosts", self.crate_host,
                        '--format', format
                        ]
            with patch('sys.stdout', new_callable=StringIO) as output:
                with patch('sys.stderr', new_callable=StringIO) as err:
                    try:
                        main()
                    except SystemExit as e:
                        func(self, e, output, err)
        finally:
            sys.argv = orig_argv

    def test_val_len(self):
        self.assertEqual(val_len(1), 1)
        self.assertEqual(val_len(12), 2)
        self.assertEqual(val_len('123'), 3)
        self.assertEqual(val_len(True), 4)
        self.assertEqual(val_len(None), 4)
        self.assertEqual(val_len([1, 2, 3]), 9)
        self.assertEqual(val_len({'key': 'val'}), 14)

    def test_tabulate_output(self):
        def assert_func(self, e, output, err):
            exception_code = e.code
            self.assertEqual(exception_code, 0)
            output = output.getvalue()
            self.assertTrue('| name         |' in output)
            self.assertTrue('| Testing44209 |' in output)
        self._output_format('tabular', assert_func)

    def test_json_output(self):
        def assert_func(self, e, output, err):
            exception_code = e.code
            self.assertEqual(exception_code, 0)
            output = output.getvalue()
            self.assertTrue('"name": "Testing44209"' in output)
        self._output_format('json', assert_func)

    def test_json_row_output(self):
        query = "select table_name from information_schema.tables where table_name = 'cluster'"

        def assert_func(self, e, output, err):
            exception_code = e.code
            self.assertEqual(exception_code, 0)
            output = output.getvalue()
            self.assertTrue('{"table_name": "cluster"}' in output)
        self._output_format('json_row', assert_func, query)

    def test_csv_obj_output(self):
        query = "select name, port from sys.nodes limit 1"

        def assert_func(self, e, output, err):
            exception_code = e.code
            self.assertEqual(exception_code, 0)
            output = output.getvalue()
            self.assertTrue("""crate,'{"http": 44209, "psql": 45441, "transport": 44309}'""" in output)

        self._output_format('csv', assert_func, query)

    def test_csv_array_output(self):
        query = "select ['/dev/', 'foo'] as arr"

        def assert_func(self, e, output, err):
            exception_code = e.code
            self.assertEqual(exception_code, 0)
            output = output.getvalue()
            self.assertTrue('["/dev/' in output)

        self._output_format('csv', assert_func, query)

    def test_raw_output(self):
        def assert_func(self, e, output, err):
            exception_code = e.code
            self.assertEqual(exception_code, 0)
            output = output.getvalue()
            self.assertTrue('"duration":' in output)
            self.assertTrue('"rowcount":' in output)
            self.assertTrue('"rows":' in output)
            self.assertTrue('"cols":' in output)
        self._output_format('raw', assert_func)

    def test_mixed_output(self):
        def assert_func(self, e, output, err):
            exception_code = e.code
            self.assertEqual(exception_code, 0)
            output = output.getvalue()
            self.assertTrue("name | Testing44209" in output)
        self._output_format('mixed', assert_func)

    def test_pprint_duplicate_keys(self):
        "Output: table with duplicate keys"
        expected = "\n".join(["+------+------+",
                              "| name | name |",
                              "+------+------+",
                              "+------+------+\n"])
        command = CrateCmd()
        with patch('sys.stdout', new_callable=StringIO) as output:
            command.pprint([], ['name', 'name'])
            self.assertEqual(expected, output.getvalue())

    def test_pprint_dont_guess_type(self):
        "Output: table with duplicate keys"
        expected = "\n".join(["+---------+",
                              "| version |",
                              "+---------+",
                              "| 0.50    |",
                              "+---------+\n"])
        command = CrateCmd()
        with patch('sys.stdout', new_callable=StringIO) as output:
            command.pprint([["0.50"]], ['version'])
            self.assertEqual(expected, output.getvalue())

    @patch('sys.stdin', fake_stdin(u"select 'via-stdin' from sys.cluster"))
    def test_stdin_cmd(self):
        "Test passing in SQL via stdin"
        try:
            orig_argv = sys.argv[:]
            tmphistory = tempfile.mkstemp()[1]
            sys.argv = ['testcrash',
                        '--hosts', self.crate_host,
                        '--history', tmphistory]
            with patch('sys.stdout', new_callable=StringIO) as output:
                try:
                    main()
                except SystemExit as e:
                    exception_code = e.code
                self.assertEqual(exception_code, 0)
                output = output.getvalue()
                self.assertTrue('via-stdin' in output)
        finally:
            try:
                os.remove(tmphistory)
            except IOError:
                pass
            sys.argv = orig_argv

    @patch('sys.stdin', fake_stdin(u"select 'via-stdin' from sys.cluster"))
    def test_cmd_precedence(self):
        """Test precedence of SQL passed in via -c vs. stdin
        SQL passed in via --command should take precedence
        over stdin
        """
        try:
            stmt = u"select 'via-command' from information_schema.tables limit 1"
            orig_argv = sys.argv[:]
            tmphistory = tempfile.mkstemp()[1]
            sys.argv = ['testcrash',
                        "--command", stmt,
                        '--hosts', self.crate_host,
                        '--history', tmphistory]
            with patch('sys.stdout', new_callable=StringIO) as output:
                try:
                    main()
                except SystemExit as e:
                    exception_code = e.code
                self.assertEqual(exception_code, 0)
                output = output.getvalue()
                self.assertTrue('via-command' in output)
                self.assertFalse('via-stdin' in output)
        finally:
            try:
                os.remove(tmphistory)
            except IOError:
                pass
            sys.argv = orig_argv

    def test_multiple_hosts(self):
        orig_argv = sys.argv[:]
        try:
            tmphistory = tempfile.mkstemp()[1]
            sys.argv = ["testcrash",
                        "-c", "select * from sys.cluster",
                        "--hosts", self.crate_host, "300.300.300.300:123",
                        '--history', tmphistory,
                        '--format', 'tabular',
                        '-v',
                        ]
            with patch('sys.stdout', new_callable=StringIO) as output:
                try:
                    main()
                except SystemExit as e:
                    exception_code = e.code
                    self.assertEqual(exception_code, 0)
                    output = output.getvalue()
                    lines = output.split('\n')
                    self.assertTrue(re.match('^\| http://[\d\.:]+. *\| crate .*\| TRUE .*\| OK', lines[3]) is not None, lines[3])
                    self.assertTrue(re.match('^\| http://[\d\.:]+ .*\| NULL .*\| FALSE .*\| Server not available', lines[4]) is not None, lines[4])
        finally:
            try:
                os.remove(tmphistory)
            except IOError:
                pass
            sys.argv = orig_argv

    def test_cmd_line_sys_info(self):
        sys.argv = ["testcrash",
                    "--hosts", self.crate_host,
                    "--sysinfo"
                    ]
        with patch('sys.stdout', new_callable=StringIO):
            try:
                main()
            except SystemExit as e:
                self.assertEqual(e.code, 0)

    @patch('sys.stdin', fake_stdin('\n'.join(["create table test(",
                                              "d string",
                                              ")",
                                              "clustered into 2 shards",
                                              "with (number_of_replicas=0)"])))
    def test_multiline_stdin(self):
        """Test pass multiline statement via stdin

        Newlines must be replaced with whitespaces
        """
        stmt = ''.join(list(get_stdin())).replace('\n', ' ')
        expected = ("create table test( d string ) "
                    "clustered into 2 shards "
                    "with (number_of_replicas=0)")
        self.assertEqual(stmt, expected)

    @patch('sys.stdin', fake_stdin('\n'.join(["create table test(",
                                              "d string",
                                              ")",
                                              "clustered into 2 shards",
                                              "with (number_of_replicas=0);"])))
    def test_multiline_stdin_delimiter(self):
        """Test pass multiline statement with delimiter via stdin

        Newlines must be replaced with whitespaces
        """
        stmt = ''.join(list(get_stdin())).replace('\n', ' ')
        expected = ("create table test( d string ) "
                    "clustered into 2 shards "
                    "with (number_of_replicas=0);")
        self.assertEqual(stmt, expected)

    def test_tabulate_null_int_column(self):
        """
        Create a column with a non-string value and NULL.
        """
        rows = [[1], [None]]
        expected = "\n".join(['+------+',
                              '|    x |',
                              '+------+',
                              '|    1 |',
                              '| NULL |',
                              '+------+\n'])
        cmd = CrateCmd()
        with patch('sys.stdout', new_callable=StringIO) as output:
            cmd.pprint(rows, cols=['x'])
            self.assertEqual(expected, output.getvalue())

    def test_tabulate_boolean_int_column(self):
        """
        Create another column with a non-string value and FALSE.
        """
        rows = [[u'FALSE'], [1]]
        expected = "\n".join(['+-------+',
                              '| x     |',
                              '+-------+',
                              '| FALSE |',
                              '| 1     |',
                              '+-------+\n'])
        cmd = CrateCmd()
        with patch('sys.stdout', new_callable=StringIO) as output:
            cmd.pprint(rows, cols=['x'])
            self.assertEqual(expected, output.getvalue())

    def test_multiline_header(self):
        """
        Create another column with a non-string value and FALSE.
        """
        rows = [[u'FALSE'], [1]]
        expected = "\n".join(['+-------+',
                              '| x     |',
                              '| y     |',
                              '+-------+',
                              '| FALSE |',
                              '| 1     |',
                              '+-------+\n'])
        cmd = CrateCmd()
        with patch('sys.stdout', new_callable=StringIO) as output:
            cmd.pprint(rows, cols=['x\ny'])
            self.assertEqual(expected, output.getvalue())

    def test_multiline_row(self):
        """
        Create ta column that holds rows with multiline text.
        """
        rows = [[u'create table foo (\n  id integer,\n  name string\n)', 'foo\nbar', 1]]
        expected = "\n".join(['+-----------------------+-----+---+',
                              '| show create table foo | a   | b |',
                              '+-----------------------+-----+---+',
                              '| create table foo (    | foo | 1 |',
                              '|   id integer,         | bar |   |',
                              '|   name string         |     |   |',
                              '| )                     |     |   |',
                              '+-----------------------+-----+---+\n'])
        cmd = CrateCmd()
        with patch('sys.stdout', new_callable=StringIO) as output:
            cmd.pprint(rows, cols=['show create table foo', 'a', 'b'])
            self.assertEqual(expected, output.getvalue())

    def test_tabulate_empty_line(self):

        self.maxDiff=None
        rows = [u'Aldebaran', u'Star System'], [u'Berlin', u'City'], [u'Galactic Sector QQ7 Active J Gamma', u'Galaxy'], [u'', u'Planet']
        expected = "\n".join(['+------------------------------------+-------------+',
                              '| min(name)                          | kind        |',
                              '+------------------------------------+-------------+',
                              '| Aldebaran                          | Star System |',
                              '| Berlin                             | City        |',
                              '| Galactic Sector QQ7 Active J Gamma | Galaxy      |',
                              '|                                    | Planet      |',
                              '+------------------------------------+-------------+\n'])

        cmd = CrateCmd()
        with patch('sys.stdout', new_callable=StringIO) as output:
            cmd.pprint(rows, cols=['min(name)', 'kind'])
            #assert 0
            self.assertEqual(expected, output.getvalue())

    def test_empty_line_first_row_first_column(self):

        self.maxDiff=None
        rows = [u'', u'Planet'], [u'Aldebaran', u'Star System'], [u'Berlin', u'City'], [u'Galactic Sector QQ7 Active J Gamma', u'Galaxy']
        expected = "\n".join(['+------------------------------------+-------------+',
                              '| min(name)                          | kind        |',
                              '+------------------------------------+-------------+',
                              '|                                    | Planet      |',
                              '| Aldebaran                          | Star System |',
                              '| Berlin                             | City        |',
                              '| Galactic Sector QQ7 Active J Gamma | Galaxy      |',
                              '+------------------------------------+-------------+\n'])

        cmd = CrateCmd()
        with patch('sys.stdout', new_callable=StringIO) as output:
            cmd.pprint(rows, cols=['min(name)', 'kind'])
            self.assertEqual(expected, output.getvalue())

    def test_empty_first_row(self):

            self.maxDiff=None
            rows = [u'', u''], [u'Aldebaran', u'Aldebaran'], [u'Algol', u'Algol'], [u'Allosimanius Syneca', u'Allosimanius - Syneca'], [u'Alpha Centauri', u'Alpha - Centauri']
            expected = "\n".join(['+---------------------+-----------------------+',
                                  '| name                | replaced              |',
                                  '+---------------------+-----------------------+',
                                  '|                     |                       |',
                                  '| Aldebaran           | Aldebaran             |',
                                  '| Algol               | Algol                 |',
                                  '| Allosimanius Syneca | Allosimanius - Syneca |',
                                  '| Alpha Centauri      | Alpha - Centauri      |',
                                  '+---------------------+-----------------------+\n'])

            cmd = CrateCmd()
            with patch('sys.stdout', new_callable=StringIO) as output:
                cmd.pprint(rows, cols=['name', 'replaced'])
                self.assertEqual(expected, output.getvalue())

    def test_any_empty(self):

            self.maxDiff=None
            rows = [u'Features and conformance views', u'FALSE', u'', u''], [u'Features and conformance views', u'TRUE', 1, u'SQL_FEATURES view'], [u'Features and conformance views', u'FALSE', 2, u'SQL_SIZING view'], [u'Features and conformance views', u'FALSE', 3, u'SQL_LANGUAGES view']
            expected = "\n".join(['+--------------------------------+--------------+----------------+--------------------+',
                                  '| feature_name                   | is_supported | sub_feature_id | sub_feature_name   |',
                                  '+--------------------------------+--------------+----------------+--------------------+',
                                  '| Features and conformance views | FALSE        |                |                    |',
                                  '| Features and conformance views | TRUE         | 1              | SQL_FEATURES view  |',
                                  '| Features and conformance views | FALSE        | 2              | SQL_SIZING view    |',
                                  '| Features and conformance views | FALSE        | 3              | SQL_LANGUAGES view |',
                                  '+--------------------------------+--------------+----------------+--------------------+\n'])

            cmd = CrateCmd()
            with patch('sys.stdout', new_callable=StringIO) as output:
                cmd.pprint(rows, cols=['feature_name', 'is_supported', 'sub_feature_id', 'sub_feature_name'])
                self.assertEqual(expected, output.getvalue())

    def test_first_column_first_row_empty(self):

            self.maxDiff=None
            rows = [u'', 1.0], [u'Aldebaran', 1.0], [u'Algol', 1.0], [u'Allosimanius Syneca', 1.0], [u'Alpha Centauri', 1.0], [u'Argabuthon', 1.0], [u'Arkintoofle Minor', 1.0], [u'Galactic Sector QQ7 Active J Gamma', 1.0], [u'North West Ripple', 1.0], [u'Outer Eastern Rim', 1.0], [u'NULL', 1.0]
            expected = "\n".join(['+------------------------------------+--------+',
                                  '| name                               | _score |',
                                  '+------------------------------------+--------+',
                                  '|                                    |    1.0 |',
                                  '| Aldebaran                          |    1.0 |',
                                  '| Algol                              |    1.0 |',
                                  '| Allosimanius Syneca                |    1.0 |',
                                  '| Alpha Centauri                     |    1.0 |',
                                  '| Argabuthon                         |    1.0 |',
                                  '| Arkintoofle Minor                  |    1.0 |',
                                  '| Galactic Sector QQ7 Active J Gamma |    1.0 |',
                                  '| North West Ripple                  |    1.0 |',
                                  '| Outer Eastern Rim                  |    1.0 |',
                                  '| NULL                               |    1.0 |',
                                  '+------------------------------------+--------+\n'])

            cmd = CrateCmd()
            with patch('sys.stdout', new_callable=StringIO) as output:
                cmd.pprint(rows, cols=['name', '_score'])
                self.assertEqual(expected, output.getvalue())

    def test_error_exit_code(self):
        """Test returns an error exit code"""
        stmt = u"select * from invalid sql statement"
        sys.argv = ['testcrash',
                    "--command", stmt,
                    '--hosts', self.crate_host]
        try:
            main()
        except SystemExit as e:
            self.assertEqual(e.code, 1)

    def test_verbose_with_error_trace(self):
        command = CrateCmd(error_trace=True)
        command.logger = Mock()
        command.cursor.execute = Mock(side_effect=ProgrammingError(msg="the error message",
                                                                   error_trace="error trace"))
        command.execute("select invalid statement")
        command.logger.critical.assert_any_call("the error message")
        command.logger.critical.assert_called_with("\nerror trace")

    def test_verbose_no_error_trace(self):
        command = CrateCmd(error_trace=True)
        command.logger = Mock()
        command.cursor.execute = Mock(side_effect=ProgrammingError(msg="the error message",
                                                                   error_trace=None))
        command.execute("select invalid statement")
        # only the message is logged
        command.logger.critical.assert_called_once_with("the error message")

    def test_rendering_object(self):
        """Test rendering an object"""
        user = {'name': 'Arthur', 'age': 42}
        expected = "\n".join(['+-------------------------------+',
                              '| user                          |',
                              '+-------------------------------+',
                              '| {"age": 42, "name": "Arthur"} |',
                              '+-------------------------------+\n'])
        command = CrateCmd()
        with patch('sys.stdout', new_callable=StringIO) as output:
            command.pprint([[user]], ['user'])
            self.assertEqual(expected, output.getvalue())

    def test_rendering_array(self):
        """Test rendering an array"""
        names = ['Arthur', 'Ford']
        expected = "\n".join(['+--------------------+',
                              '| names              |',
                              '+--------------------+',
                              '| ["Arthur", "Ford"] |',
                              '+--------------------+\n'])
        command = CrateCmd()
        with patch('sys.stdout', new_callable=StringIO) as output:
            command.pprint([[names]], ['names'])
            self.assertEqual(expected, output.getvalue())

    def test_rendering_float(self):
        """Test rendering an array"""
        expected = "\n".join(['+---------------+',
                              '|        number |',
                              '+---------------+',
                              '|  3.1415926535 |',
                              '| 42.0          |',
                              '+---------------+\n'])
        command = CrateCmd()
        with patch('sys.stdout', new_callable=StringIO) as output:
            command.pprint([[3.1415926535], [42.0]], ['number'])
            self.assertEqual(expected, output.getvalue())

    def test_help_command(self):
        """Test output of help command"""
        command = CrateCmd(is_tty=False)
        expected = "\n".join([
            '\\?                              print this help',
            '\\autocapitalize                 toggle automatic capitalization of SQL keywords',
            '\\autocomplete                   toggle autocomplete',
            '\\c                              connect to the given server, e.g.: \connect localhost:4200',
            '\\check                          print failed cluster and/or node checks, e.g. \check nodes',
            '\\connect                        connect to the given server, e.g.: \connect localhost:4200',
            '\\dt                             print the existing tables within the \'doc\' schema',
            '\\format                         switch output format',
            '\\q                              quit crash',
            '\\r                              read and execute statements from a file',
            '\\sysinfo                        print system and cluster info',
            '\\verbose                        toggle verbose mode',
        ])

        help_ = command.commands['?']
        self.assertTrue(isinstance(help_, Command))
        self.assertEqual(expected, help_(command))
        command = CrateCmd(is_tty=False)

        output = StringIO()
        command.logger = ColorPrinter(False, stream=output)
        text = help_(command, 'arg1', 'arg2')
        self.assertEqual(None, text)
        self.assertEqual('Command does not take any arguments.\n', output.getvalue())

    def test_noargs_decorator(self):
        """Test noargs decorator"""
        output = StringIO()

        class MyCmd:

            logger = ColorPrinter(False, stream=output)

            @noargs_command
            def my_cmd(self, *args):
                return 'awesome'

        command = MyCmd()
        command.my_cmd()

        text = command.my_cmd()
        self.assertEqual('awesome', text)

        text = command.my_cmd('arg1')
        self.assertEqual(None, text)
        self.assertEqual('Command does not take any arguments.\n', output.getvalue())

    def test_wrong_host_format(self):
        sys.argv = ["testcrash",
                    "--hosts", 'localhost:12AB'
                    ]
        parser = get_parser()
        args = parse_args(parser)

        crate_hosts = [host_and_port(h) for h in args.hosts]

        with self.assertRaises(LocationParseError):
            _create_cmd(crate_hosts, False, None, False, args)

    def test_command_timeout(self):
        sys.argv = ["testcrash", "--hosts", self.crate_host]
        parser = get_parser()
        args = parse_args(parser)

        crate_hosts = [host_and_port(h) for h in args.hosts]
        crateCmd = _create_cmd(crate_hosts, False, None, False, args, None)
        crateCmd.execute("""
CREATE FUNCTION fib(long)
RETURNS LONG
LANGUAGE javascript AS '
    function fib(n) {
      if (n < 2) return 1;
      return fib(n - 1) + fib(n - 2);
    }'
        """)

        timeout = 0.01
        slow_query = "SELECT fib(35)"

        # without verbose
        crateCmd = _create_cmd(crate_hosts, False, None, False, args, timeout)
        crateCmd.logger = Mock()
        crateCmd.execute(slow_query)
        crateCmd.logger.warn.assert_any_call("Use \connect <server> to connect to one or more servers first.")

        # with verbose
        crateCmd = _create_cmd(crate_hosts, True, None, False, args, timeout)
        crateCmd.logger = Mock()
        crateCmd.execute(slow_query)
        crateCmd.logger.warn.assert_any_call("No more Servers available, exception from last server: HTTPConnectionPool(host='127.0.0.1', port=44209): Read timed out. (read timeout=0.01)")
        crateCmd.logger.warn.assert_any_call("Use \connect <server> to connect to one or more servers first.")

    def test_username_param(self):
        sys.argv = ["testcrash",
                    "--hosts", self.crate_host,
                    "--username", "crate"
                    ]
        parser = get_parser()
        args = parse_args(parser)
        crate_hosts = [host_and_port(h) for h in args.hosts]
        crateCmd = _create_cmd(crate_hosts, False, None, False, args)

        self.assertEqual(crateCmd.username, "crate")
        self.assertEqual(crateCmd.connection.client.username, "crate")

    def test_ssl_params(self):
        tmpdirname = tempfile.mkdtemp()
        cert_filename = os.path.join(tmpdirname, "cert_file")
        key_filename = os.path.join(tmpdirname, "key_file")
        ca_cert_filename = os.path.join(tmpdirname, "ca_cert_file")

        open(cert_filename, 'a').close()
        open(key_filename, 'a').close()
        open(ca_cert_filename, 'a').close()

        sys.argv = ["testcrash",
                    "--hosts", self.crate_host,
                    "--verify-ssl", "false",
                    "--cert-file", cert_filename,
                    "--key-file", key_filename,
                    "--ca-cert-file", ca_cert_filename
                    ]
        parser = get_parser()
        args = parse_args(parser)

        crate_hosts = [host_and_port(h) for h in args.hosts]
        crateCmd = _create_cmd(crate_hosts, False, None, False, args)

        self.assertEqual(crateCmd.verify_ssl, False)
        self.assertEqual(crateCmd.connection.client._pool_kw['cert_reqs'], ssl.CERT_NONE)

        self.assertEqual(crateCmd.cert_file, cert_filename)
        self.assertEqual(crateCmd.connection.client._pool_kw['cert_file'], cert_filename)

        self.assertEqual(crateCmd.key_file, key_filename)
        self.assertEqual(crateCmd.connection.client._pool_kw['key_file'], key_filename)

        self.assertEqual(crateCmd.ca_cert_file, ca_cert_filename)
        self.assertEqual(crateCmd.connection.client._pool_kw['ca_certs'], ca_cert_filename)


    def test_ssl_params_missing_file(self):
        sys.argv = ["testcrash",
                    "--hosts", self.crate_host,
                    "--verify-ssl", "false",
                    "--key-file", "wrong_file",
                    "--ca-cert-file", "ca_cert_file"
                    ]
        parser = get_parser()

        # Python 2
        try:
            FileNotFoundError
        except NameError:
            FileNotFoundError = IOError

        with self.assertRaises(FileNotFoundError):
            parse_args(parser)

    def test_ssl_params_wrong_permision_file(self):
        tmpdirname = tempfile.mkdtemp()
        ca_cert_filename = os.path.join(tmpdirname, "ca_cert_file")
        open(ca_cert_filename, 'a').close()
        os.chmod(ca_cert_filename, 0000)

        sys.argv = ["testcrash",
                    "--hosts", self.crate_host,
                    "--verify-ssl", "false",
                    "--ca-cert-file", ca_cert_filename
                    ]
        parser = get_parser()

        # Python 2
        try:
            PermissionError
        except NameError:
            PermissionError = IOError

        with self.assertRaises(PermissionError):
            parse_args(parser)


class TestGetInformationSchemaQuery(TestCase):

    def test_low_version(self):
        lowest_server_version = StrictVersion("0.56.4")
        query = get_information_schema_query(lowest_server_version)
        self.assertEqual(""" select count(distinct(table_name))
                as number_of_tables
            from information_schema.tables
            where schema_name
            not in ('information_schema', 'sys', 'pg_catalog') """, query)

    def test_high_version(self):
        lowest_server_version = StrictVersion("1.0.4")
        query = get_information_schema_query(lowest_server_version)
        self.assertEqual(""" select count(distinct(table_name))
                as number_of_tables
            from information_schema.tables
            where table_schema
            not in ('information_schema', 'sys', 'pg_catalog') """, query)

