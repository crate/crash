import sys
import os
from unittest import TestCase
from six import PY2, StringIO
import tempfile
from io import TextIOWrapper
from mock import patch

from .command import CrateCmd, main


def fake_stdin(data):
    if PY2:
        stdin = tempfile.TemporaryFile()
    else:
        stdin = TextIOWrapper(tempfile.TemporaryFile())
    stdin.write(data)
    stdin.flush()
    stdin.seek(0)
    return stdin


class CommandTest(TestCase):

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

    def test_rendering_object(self):
        """Test rendering an object"""
        name = {'name': 'Arthur'}
        expected = "\n".join(["+--------------------+",
                              "| name               |",
                              "+--------------------+",
                              "| {'name': 'Arthur'} |",
                              "+--------------------+\n"])
        command = CrateCmd()
        with patch('sys.stdout', new_callable=StringIO) as output:
            command.pprint([[name]], ['name'])
            self.assertEqual(expected, output.getvalue())

    def test_rendering_array(self):
        """Test rendering an array"""
        names = ['Arthur', 'Ford']
        expected = "\n".join(["+--------------------+",
                              "| names              |",
                              "+--------------------+",
                              "| ['Arthur', 'Ford'] |",
                              "+--------------------+\n"])
        command = CrateCmd()
        with patch('sys.stdout', new_callable=StringIO) as output:
            command.pprint([[names]], ['names'])
            self.assertEqual(expected, output.getvalue())
