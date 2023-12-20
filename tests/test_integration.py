import os
import ssl
import sys
import tempfile
from doctest import testfile
from io import StringIO, TextIOWrapper
from unittest import SkipTest, TestCase
from unittest.mock import Mock, patch

from urllib3.exceptions import LocationParseError

from crate.client.exceptions import ProgrammingError
from crate.crash.command import (
    CrateShell,
    _create_shell,
    get_lines_from_stdin,
    get_parser,
    host_and_port,
    main,
    noargs_command,
)
from crate.crash.commands import Command
from crate.crash.outputs import _val_len as val_len
from crate.crash.printer import ColorPrinter
from crate.testing.layer import CrateLayer
from tests import ftouch

if sys.platform != "linux":
    raise SkipTest("Integration tests only supported on Linux")

crate_version = os.getenv("CRATEDB_VERSION", "5.5.0")
crate_http_port = 44209
crate_transport_port = 44309
crate_settings = {
    'cluster.name': 'Testing44209',
    'node.name': 'crate',
    'psql.port': 45441,
    'lang.js.enabled': True,
    'http.port': crate_http_port,
    'transport.tcp.port': crate_transport_port
}
node = CrateLayer.from_uri(
    f'https://cdn.crate.io/downloads/releases/cratedb/x64_linux/crate-{crate_version}.tar.gz',
    'crate',
    settings=crate_settings
)


def setUpModule():
    node.start()


def tearDownModule():
    node.stop()


def fake_stdin(data):
    stdin = TextIOWrapper(tempfile.TemporaryFile())
    stdin.write(data)
    stdin.flush()
    stdin.seek(0)
    return stdin


class RaiseOnceSideEffect:
    """
    A callable class used for mock side_effect.

    The side effect raises an exception once, every subsequent call invokes the
    original method.
    """

    def __init__(self, exception, original):
        self.exception = exception
        self.original = original
        self.raised = False

    def __call__(self, *args, **kwargs):
        if not self.raised:
            self.raised = True
            raise self.exception
        return self.original(*args, **kwargs)


class DocumentationTest(TestCase):

    def test_output(self):
        testfile('../crate/crash/output.txt')

    def test_connect(self):
        testfile('../crate/crash/connect.txt')


class CommandTest(TestCase):

    def _output_format(self, format, func, query="select name from sys.cluster"):
        orig_argv = sys.argv[:]
        try:
            sys.argv = ["testcrash",
                        "-c", query,
                        "--hosts", node.http_url,
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
            self.assertIn('| name         |', output)
            self.assertIn('| Testing44209 |', output)
        self._output_format('tabular', assert_func)

    def test_json_output(self):
        def assert_func(self, e, output, err):
            exception_code = e.code
            self.assertEqual(exception_code, 0)
            output = output.getvalue()
            self.assertIn('"name": "Testing44209"', output)
        self._output_format('json', assert_func)

    def test_json_row_output(self):
        query = "select table_name from information_schema.tables where table_name = 'cluster'"

        def assert_func(self, e, output, err):
            exception_code = e.code
            self.assertEqual(exception_code, 0)
            output = output.getvalue()
            self.assertIn('{"table_name": "cluster"}', output)
        self._output_format('json_row', assert_func, query)

    def test_csv_obj_output(self):
        query = "select name, port from sys.nodes limit 1"

        def assert_func(self, e, output, err):
            exception_code = e.code
            self.assertEqual(exception_code, 0)
            output = output.getvalue()
            self.assertIn("""crate,'{"http": 44209, "psql": 45441, "transport": 44309}'""", output)

        self._output_format('csv', assert_func, query)

    def test_csv_array_output(self):
        query = "select ['/dev/', 'foo'] as arr"

        def assert_func(self, e, output, err):
            exception_code = e.code
            self.assertEqual(exception_code, 0)
            output = output.getvalue()
            self.assertIn('["/dev/', output)

        self._output_format('csv', assert_func, query)

    def test_raw_output(self):
        def assert_func(self, e, output, err):
            exception_code = e.code
            self.assertEqual(exception_code, 0)
            output = output.getvalue()
            self.assertIn('"duration":', output)
            self.assertIn('"rowcount":', output)
            self.assertIn('"rows":', output)
            self.assertIn('"cols":', output)
        self._output_format('raw', assert_func)

    def test_mixed_output(self):
        def assert_func(self, e, output, err):
            exception_code = e.code
            self.assertEqual(exception_code, 0)
            output = output.getvalue()
            self.assertIn("name | Testing44209", output)
        self._output_format('mixed', assert_func)

    def test_pprint_duplicate_keys(self):
        "Output: table with duplicate keys"
        expected = "\n".join(["+------+------+",
                              "| name | name |",
                              "+------+------+",
                              "+------+------+\n"])
        with CrateShell() as cmd:
            with patch('sys.stdout', new_callable=StringIO) as output:
                cmd.pprint([], ['name', 'name'])
                self.assertEqual(expected, output.getvalue())

    def test_pprint_dont_guess_type(self):
        "Output: Numeric looking strings should still be processed as strings"
        expected = "\n".join(["+---------+",
                              "| version |",
                              "+---------+",
                              "|    0.50 |",
                              "+---------+\n"])
        with CrateShell() as cmd:
            with patch('sys.stdout', new_callable=StringIO) as output:
                cmd.pprint([["0.50"]], ['version'])
                self.assertEqual(expected, output.getvalue())

    @patch('sys.stdin', fake_stdin(u"select 'via-stdin' from sys.cluster"))
    def test_stdin_cmd(self):
        "Test passing in SQL via stdin"
        try:
            orig_argv = sys.argv[:]
            tmphistory = tempfile.mkstemp()[1]
            sys.argv = ['testcrash',
                        '--hosts', node.http_url,
                        '--history', tmphistory]
            with patch('sys.stdout', new_callable=StringIO) as output:
                try:
                    main()
                except SystemExit as e:
                    exception_code = e.code
                self.assertEqual(exception_code, 0)
                output = output.getvalue()
                self.assertIn('via-stdin', output)
        finally:
            try:
                os.remove(tmphistory)
            except IOError:
                pass
            sys.argv = orig_argv
            sys.stdin.close()

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
                        '--hosts', node.http_url,
                        '--history', tmphistory]
            with patch('sys.stdout', new_callable=StringIO) as output:
                try:
                    main()
                except SystemExit as e:
                    exception_code = e.code
                self.assertEqual(exception_code, 0)
                output = output.getvalue()
                self.assertIn('via-command', output)
                self.assertNotIn('via-stdin', output)
        finally:
            try:
                os.remove(tmphistory)
            except IOError:
                pass
            sys.argv = orig_argv
            sys.stdin.close()

    def test_multiple_hosts(self):
        orig_argv = sys.argv[:]
        try:
            tmphistory = tempfile.mkstemp()[1]
            sys.argv = ["testcrash",
                        "-c", "select * from sys.cluster",
                        "--hosts", node.http_url, "127.0.0.1:1",
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
                    self.assertRegex(lines[3], r'^\| http://[\d\.:]+ .*\| NULL .*\| FALSE .*\| Server not available')
                    self.assertRegex(lines[4], r'^\| http://[\d\.:]+. *\| crate .*\| TRUE .*\| OK')
        finally:
            try:
                os.remove(tmphistory)
            except IOError:
                pass
            sys.argv = orig_argv

    def test_cmd_line_sys_info(self):
        sys.argv = ["testcrash",
                    "--hosts", node.http_url,
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
        stmt = ''.join(list(get_lines_from_stdin())).replace('\n', ' ')
        expected = ("create table test( d string ) "
                    "clustered into 2 shards "
                    "with (number_of_replicas=0)")
        try:
            self.assertEqual(stmt, expected)
        finally:
            sys.stdin.close()

    @patch('sys.stdin', fake_stdin('\n'.join(["create table test(",
                                              "d string",
                                              ")",
                                              "clustered into 2 shards",
                                              "with (number_of_replicas=0);"])))
    def test_multiline_stdin_delimiter(self):
        """Test pass multiline statement with delimiter via stdin

        Newlines must be replaced with whitespaces
        """
        stmt = ''.join(list(get_lines_from_stdin())).replace('\n', ' ')
        expected = ("create table test( d string ) "
                    "clustered into 2 shards "
                    "with (number_of_replicas=0);")
        try:
            self.assertEqual(stmt, expected)
        finally:
            sys.stdin.close()

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
        with CrateShell() as cmd:
            with patch('sys.stdout', new_callable=StringIO) as output:
                cmd.pprint(rows, cols=['x'])
                self.assertEqual(expected, output.getvalue())

    def test_tabulate_boolean_int_column(self):
        """
        Create another column with a non-string value and FALSE.
        """
        rows = [['FALSE'], [1]]
        expected = "\n".join(['+-------+',
                              '| x     |',
                              '+-------+',
                              '| FALSE |',
                              '| 1     |',
                              '+-------+\n'])
        with CrateShell() as cmd:
            with patch('sys.stdout', new_callable=StringIO) as output:
                cmd.pprint(rows, cols=['x'])
                self.assertEqual(expected, output.getvalue())

    def test_multiline_header(self):
        """
        Create a column with newline characters.
        """
        rows = [['FALSE'], [1]]
        expected = "\n".join(['+-------+',
                              '| x     |',
                              '| y     |',
                              '+-------+',
                              '| FALSE |',
                              '| 1     |',
                              '+-------+\n'])
        with CrateShell() as cmd:
            with patch('sys.stdout', new_callable=StringIO) as output:
                cmd.pprint(rows, cols=['x\ny'])
                self.assertEqual(expected, output.getvalue())

    def test_multiline_row(self):
        """
        Create a column that holds rows with multiline text.
        """
        self.maxDiff = None
        rows = [['create table foo (\n  id integer,\n  name string\n)', 'foo\nbar', 1]]
        expected = "\n".join(['+-----------------------+-----+---+',
                              '| show create table foo | a   | b |',
                              '+-----------------------+-----+---+',
                              '| create table foo (    | foo | 1 |',
                              '|   id integer,         | bar |   |',
                              '|   name string         |     |   |',
                              '| )                     |     |   |',
                              '+-----------------------+-----+---+\n'])
        with CrateShell() as cmd:
            with patch('sys.stdout', new_callable=StringIO) as output:
                cmd.pprint(rows, cols=['show create table foo', 'a', 'b'])
                self.assertEqual(expected, output.getvalue())

    def test_tabulate_empty_line(self):
        self.maxDiff = None
        rows = (
            ['Aldebaran', 'Star System'],
            ['Berlin', 'City'],
            ['Galactic Sector QQ7 Active J Gamma', 'Galaxy'],
            ['', 'Planet']
        )
        expected = "\n".join(['+------------------------------------+-------------+',
                              '| min(name)                          | kind        |',
                              '+------------------------------------+-------------+',
                              '| Aldebaran                          | Star System |',
                              '| Berlin                             | City        |',
                              '| Galactic Sector QQ7 Active J Gamma | Galaxy      |',
                              '|                                    | Planet      |',
                              '+------------------------------------+-------------+\n'])

        with CrateShell() as cmd:
            with patch('sys.stdout', new_callable=StringIO) as output:
                cmd.pprint(rows, cols=['min(name)', 'kind'])
                # assert 0
                self.assertEqual(expected, output.getvalue())

    def test_empty_line_first_row_first_column(self):
        self.maxDiff = None
        rows = (
            ['', 'Planet'],
            ['Aldebaran', 'Star System'],
            ['Berlin', 'City'],
            ['Galactic Sector QQ7 Active J Gamma', 'Galaxy']
        )
        expected = "\n".join(['+------------------------------------+-------------+',
                              '| min(name)                          | kind        |',
                              '+------------------------------------+-------------+',
                              '|                                    | Planet      |',
                              '| Aldebaran                          | Star System |',
                              '| Berlin                             | City        |',
                              '| Galactic Sector QQ7 Active J Gamma | Galaxy      |',
                              '+------------------------------------+-------------+\n'])

        with CrateShell() as cmd:
            with patch('sys.stdout', new_callable=StringIO) as output:
                cmd.pprint(rows, cols=['min(name)', 'kind'])
                self.assertEqual(expected, output.getvalue())

    def test_empty_first_row(self):
        self.maxDiff = None
        rows = (
            ['', ''],
            ['Aldebaran', 'Aldebaran'],
            ['Algol', 'Algol'],
            ['Allosimanius Syneca', 'Allosimanius - Syneca'],
            ['Alpha Centauri', 'Alpha - Centauri']
        )
        expected = "\n".join(['+---------------------+-----------------------+',
                              '| name                | replaced              |',
                              '+---------------------+-----------------------+',
                              '|                     |                       |',
                              '| Aldebaran           | Aldebaran             |',
                              '| Algol               | Algol                 |',
                              '| Allosimanius Syneca | Allosimanius - Syneca |',
                              '| Alpha Centauri      | Alpha - Centauri      |',
                              '+---------------------+-----------------------+\n'])

        with CrateShell() as cmd:
            with patch('sys.stdout', new_callable=StringIO) as output:
                cmd.pprint(rows, cols=['name', 'replaced'])
                self.assertEqual(expected, output.getvalue())

    def test_any_empty(self):
        self.maxDiff = None
        rows = (
            ['Features and conformance views', 'FALSE', '', ''],
            ['Features and conformance views', 'TRUE', 1, 'SQL_FEATURES view'],
            ['Features and conformance views', 'FALSE', 2, 'SQL_SIZING view'],
            ['Features and conformance views', 'FALSE', 3, 'SQL_LANGUAGES view']
        )
        expected = "\n".join(['+--------------------------------+--------------+----------------+--------------------+',
                              '| feature_name                   | is_supported | sub_feature_id | sub_feature_name   |',
                              '+--------------------------------+--------------+----------------+--------------------+',
                              '| Features and conformance views | FALSE        |                |                    |',
                              '| Features and conformance views | TRUE         | 1              | SQL_FEATURES view  |',
                              '| Features and conformance views | FALSE        | 2              | SQL_SIZING view    |',
                              '| Features and conformance views | FALSE        | 3              | SQL_LANGUAGES view |',
                              '+--------------------------------+--------------+----------------+--------------------+\n'])

        with CrateShell() as cmd:
            with patch('sys.stdout', new_callable=StringIO) as output:
                cmd.pprint(rows, cols=['feature_name', 'is_supported', 'sub_feature_id', 'sub_feature_name'])
                self.assertEqual(expected, output.getvalue())

    def test_first_column_first_row_empty(self):
        self.maxDiff = None
        rows = (
            ['', 1.0],
            ['Aldebaran', 1.0],
            ['Algol', 1.0],
            ['Allosimanius Syneca', 1.0],
            ['Alpha Centauri', 1.0],
            ['Argabuthon', 1.0],
            ['Arkintoofle Minor', 1.0],
            ['Galactic Sector QQ7 Active J Gamma', 1.0],
            ['North West Ripple', 1.0],
            ['Outer Eastern Rim', 1.0],
            ['NULL', 1.0]
        )
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

        with CrateShell() as cmd:
            with patch('sys.stdout', new_callable=StringIO) as output:
                cmd.pprint(rows, cols=['name', '_score'])
                self.assertEqual(expected, output.getvalue())

    def test_error_exit_code(self):
        """Test returns an error exit code"""
        stmt = u"select * from invalid sql statement"
        sys.argv = [
            "testcrash",
            "--command", stmt,
            '--hosts', node.http_url
        ]
        try:
            main()
        except SystemExit as e:
            self.assertEqual(e.code, 1)

    def test_verbose_with_error_trace(self):
        with CrateShell(error_trace=True) as cmd:
            cmd.logger = Mock()
            cmd.cursor.execute = Mock(side_effect=ProgrammingError(msg="the error message",
                                                                       error_trace="error trace"))
            cmd._exec_and_print("select invalid statement")
            cmd.logger.critical.assert_any_call("the error message")
            cmd.logger.critical.assert_called_with("\nerror trace")

    def test_verbose_no_error_trace(self):
        with CrateShell(error_trace=True) as cmd:
            cmd.logger = Mock()
            cmd.cursor.execute = Mock(side_effect=ProgrammingError(msg="the error message",
                                                                       error_trace=None))
            cmd._exec_and_print("select invalid statement")
            # only the message is logged
            cmd.logger.critical.assert_called_once_with("the error message")

    def test_rendering_object(self):
        """Test rendering an object"""
        user = {'name': 'Arthur', 'age': 42}
        expected = "\n".join(['+-------------------------------+',
                              '| user                          |',
                              '+-------------------------------+',
                              '| {"age": 42, "name": "Arthur"} |',
                              '+-------------------------------+\n'])
        with CrateShell() as cmd:
            with patch('sys.stdout', new_callable=StringIO) as output:
                cmd.pprint([[user]], ['user'])
                self.assertEqual(expected, output.getvalue())

    def test_rendering_array(self):
        """Test rendering an array"""
        names = ['Arthur', 'Ford']
        expected = "\n".join(['+--------------------+',
                              '| names              |',
                              '+--------------------+',
                              '| ["Arthur", "Ford"] |',
                              '+--------------------+\n'])
        with CrateShell() as cmd:
            with patch('sys.stdout', new_callable=StringIO) as output:
                cmd.pprint([[names]], ['names'])
                self.assertEqual(expected, output.getvalue())

    def test_rendering_float(self):
        """Test rendering an array"""
        expected = "\n".join(['+---------------+',
                              '|        number |',
                              '+---------------+',
                              '|  3.1415926535 |',
                              '| 42.0          |',
                              '+---------------+\n'])
        with CrateShell() as cmd:
            with patch('sys.stdout', new_callable=StringIO) as output:
                cmd.pprint([[3.1415926535], [42.0]], ['number'])
                self.assertEqual(expected, output.getvalue())

    def test_help_command(self):
        """Test output of help command"""
        command = CrateShell(is_tty=False)
        expected = "\n".join([
            '\\?                              print this help',
            '\\autocapitalize                 toggle automatic capitalization of SQL keywords',
            '\\autocomplete                   toggle autocomplete',
            '\\c                              connect to the given server, e.g.: \\connect localhost:4200',
            '\\check                          print failed cluster and/or node checks, e.g. \\check nodes',
            '\\connect                        connect to the given server, e.g.: \\connect localhost:4200',
            '\\dt                             print the existing tables within the \'doc\' schema',
            '\\format                         switch output format',
            '\\pager                          set an external pager. Use without argument to reset to internal paging',
            '\\q                              quit crash',
            '\\r                              read and execute statements from a file',
            '\\sysinfo                        print system and cluster info',
            '\\verbose                        toggle verbose mode',
        ])

        help_ = command.commands['?']
        self.assertTrue(isinstance(help_, Command))
        self.assertEqual(expected, help_(command))
        with CrateShell(is_tty=False) as cmd:
            output = StringIO()
            cmd.logger = ColorPrinter(False, stream=output)
            text = help_(cmd, 'arg1', 'arg2')
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
        parser = get_parser()
        args = parser.parse_args([
            "--hosts", "localhost:12AB"
        ])

        crate_hosts = [host_and_port(h) for h in args.hosts]

        with self.assertRaises(LocationParseError):
            _create_shell(crate_hosts, False, None, False, args)

    def test_command_timeout(self):
        with CrateShell(node.http_url) as crash:
            crash.process("""
    CREATE FUNCTION fib(long)
    RETURNS LONG
    LANGUAGE javascript AS '
        function fib(n) {
          if (n < 2) return 1;
          return fib(n - 1) + fib(n - 2);
        }'
            """)

        timeout = 0.1
        slow_query = "SELECT fib(35)"

        # without verbose
        with CrateShell(node.http_url,
                        error_trace=False,
                        timeout=timeout) as crash:
            crash.logger = Mock()
            crash.process(slow_query)
            crash.logger.warn.assert_any_call("Use \\connect <server> to connect to one or more servers first.")

        # with verbose
        with CrateShell(node.http_url,
                        error_trace=True,
                        timeout=timeout) as crash:
            crash.logger = Mock()
            crash.process(slow_query)
            crash.logger.warn.assert_any_call("No more Servers available, exception from last server: HTTPConnectionPool(host='127.0.0.1', port=44209): Read timed out. (read timeout=0.1)")
            crash.logger.warn.assert_any_call("Use \\connect <server> to connect to one or more servers first.")

    def test_username_param(self):
        with CrateShell(node.http_url,
                        username='crate') as crash:
            self.assertEqual(crash.username, "crate")
            self.assertEqual(crash.connection.client.username, "crate")

    def test_ssl_params(self):
        tmpdirname = tempfile.mkdtemp()
        cert_filename = os.path.join(tmpdirname, "cert_file")
        key_filename = os.path.join(tmpdirname, "key_file")
        ca_cert_filename = os.path.join(tmpdirname, "ca_cert_file")

        ftouch(cert_filename)
        ftouch(key_filename)
        ftouch(ca_cert_filename)

        with CrateShell(node.http_url,
                        verify_ssl=False,
                        cert_file=cert_filename,
                        key_file=key_filename,
                        ca_cert_file=ca_cert_filename) as crash:
            self.assertEqual(crash.verify_ssl, False)
            self.assertEqual(crash.connection.client._pool_kw['cert_reqs'], ssl.CERT_NONE)

            self.assertEqual(crash.cert_file, cert_filename)
            self.assertEqual(crash.connection.client._pool_kw['cert_file'], cert_filename)

            self.assertEqual(crash.key_file, key_filename)
            self.assertEqual(crash.connection.client._pool_kw['key_file'], key_filename)

            self.assertEqual(crash.ca_cert_file, ca_cert_filename)
            self.assertEqual(crash.connection.client._pool_kw['ca_certs'], ca_cert_filename)

    def test_ssl_params_missing_file(self):
        argv = [
            "--hosts", node.http_url,
            "--verify-ssl", "false",
            "--key-file", "wrong_file",
            "--ca-cert-file", "ca_cert_file"
        ]
        parser = get_parser()
        with self.assertRaises(FileNotFoundError):
            parser.parse_args(argv)

    def test_ssl_params_wrong_permision_file(self):
        tmpdirname = tempfile.mkdtemp()
        ca_cert_filename = os.path.join(tmpdirname, "ca_cert_file")
        ftouch(ca_cert_filename)
        os.chmod(ca_cert_filename, 0000)

        argv = [
            "--hosts", node.http_url,
            "--verify-ssl", "false",
            "--ca-cert-file", ca_cert_filename
        ]
        parser = get_parser()
        with self.assertRaises(PermissionError):
            parser.parse_args(argv)

    def test_close_shell(self):
        crash = CrateShell(node.http_url)
        self.assertFalse(crash.is_closed())
        self.assertTrue(crash.is_conn_available())

        crash.close()
        self.assertTrue(crash.is_closed())
        self.assertFalse(crash.is_conn_available())

        with self.assertRaises(ProgrammingError) as ctx:
            crash.close()

        self.assertEqual('CrateShell is already closed',
                         ctx.exception.message)

    def test_connect_info(self):
        with CrateShell(node.http_url,
                        username='crate',
                        schema='test') as crash:
            self.assertEqual(crash.connect_info.user, "crate")
            self.assertEqual(crash.connect_info.schema, "test")
            self.assertEqual(crash.connect_info.cluster, "Testing44209")

            with patch.object(
                crash.cursor,
                "execute",
                side_effect=RaiseOnceSideEffect(
                    ProgrammingError("SQLActionException[UnsupportedFeatureException]"),
                    crash.cursor.execute,
                )
            ):
                crash._fetch_session_info()
                self.assertEqual(crash.connect_info.user, None)
                self.assertEqual(crash.connect_info.schema, "test")
                self.assertEqual(crash.connect_info.cluster, "Testing44209")

            with patch.object(
                crash.cursor,
                "execute",
                side_effect=RaiseOnceSideEffect(
                    ProgrammingError("SQLActionException[SchemaUnknownException]"),
                    crash.cursor.execute,
                )
            ):
                crash._fetch_session_info()
                self.assertEqual(crash.connect_info.user, "crate")
                self.assertEqual(crash.connect_info.schema, "test")
                self.assertEqual(crash.connect_info.cluster, None)

            with patch.object(
                crash.cursor,
                "execute",
                side_effect=RaiseOnceSideEffect(
                    ProgrammingError("SQLActionException"),
                    crash.cursor.execute,
                )
            ):
                crash._fetch_session_info()
                self.assertEqual(crash.connect_info.user, None)
                self.assertEqual(crash.connect_info.schema, None)
                self.assertEqual(crash.connect_info.cluster, None)

    @patch.object(CrateShell, "is_conn_available")
    def test_connect_info_not_available(self, is_conn_available):
        is_conn_available.return_value = False
        with CrateShell(node.http_url,
                        username='crate',
                        schema='test') as crash:
            self.assertEqual(crash.connect_info.user, None)
            self.assertEqual(crash.connect_info.schema, None)
