import sys
import os
import re
from unittest import TestCase
from six import PY2, StringIO
import tempfile
from io import TextIOWrapper
from mock import patch, Mock
from crate.client.exceptions import ProgrammingError

from .command import CrateCmd, main, get_stdin, noargs_command, Result
from .outputs import _val_len as val_len, OutputWriter
from .printer import ColorPrinter
from .commands import Command


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
    def test_mixed_format_float_precision(self):
        expected = 'foo | 152462.70754934277'
        ow = OutputWriter(writer=None, is_tty=False)
        result = Result(cols=['foo'],
                        rows=[[152462.70754934277]],
                        rowcount=1,
                        duration=1,
                        output_width=80)
        self.assertEqual(
            next(ow.mixed(result)).rstrip(), expected)

    def test_tabular_format_float_precision(self):
        expected = u'152462.70754934277'

        ow = OutputWriter(writer=None, is_tty=False)
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
        output = ow.tabular(result).split('\n')[3]
        self.assertEqual(
            output.strip('|').strip(' '), expected)


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
        query = "select schema_name from information_schema.tables where schema_name = 'sys' limit 2"

        def assert_func(self, e, output, err):
            exception_code = e.code
            self.assertEqual(exception_code, 0)
            output = output.getvalue()
            self.assertTrue('{"schema_name": "sys"}\n{"schema_name": "sys"}' in output)
        self._output_format('json_row', assert_func, query)

    def test_csv_obj_output(self):
        query = "select name, settings['udc'] from sys.cluster"

        def assert_func(self, e, output, err):
            exception_code = e.code
            self.assertEqual(exception_code, 0)
            output = output.getvalue()
            self.assertTrue('Testing44209,\'{' in output)
            self.assertTrue('"url": "https://udc.crate.io"' in output)
            self.assertTrue('"interval": "1d"' in output)
            self.assertTrue('"enabled": true' in output)

        self._output_format('csv', assert_func, query)

    def test_csv_array_output(self):
        query = "select fs['disks']['dev'] from sys.nodes"

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
                        '-vv',
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
        with patch('sys.stdout', new_callable=StringIO) as output:
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

    def test_error_exit_code(self):
        """Test returns an error exit code"""
        stmt = u"select * from invalid sql statement"
        sys.argv = ['testcrash',
                    "--command", stmt,
                    '--hosts', self.crate_host]
        try:
            main()
        except SystemExit as e:
            exception_code = e.code
        self.assertEqual(exception_code, 1)

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
            '\\autocomplete                   toggle autocomplete',
            '\\c                              connect to the given server, e.g.: \connect localhost:4200',
            '\\check                          print failed cluster and/or node checks, e.g. \check nodes',
            '\\connect                        connect to the given server, e.g.: \connect localhost:4200',
            '\\dt                             print the existing tables within the \'doc\' schema',
            '\\format                         switch output format',
            '\\q                              quit crash',
            '\\r                              read and execute statements from a file',
            '\\sysinfo                        print system and cluster info',
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
