import sys
import os
from unittest import TestCase
from six import StringIO
import tempfile

import command
from .command import CrateCmd, main
from contextlib import contextmanager


@contextmanager
def capture(command, *args, **kwargs):
    stdout = StringIO()
    orig_out, sys.stdout = sys.stdout, stdout
    sys.stderr = orig_out
    command(*args, **kwargs)
    sys.stdout = orig_out
    stdout.seek(0)
    yield stdout.read()


def mock_stdin(data):
    "Setup a fake stdin file"
    # need a real file for select() in command.get_stdin()
    stdin = tempfile.TemporaryFile()
    stdin.write(data)
    stdin.flush()
    stdin.seek(0)
    orig_in, sys.stdin = sys.stdin, stdin
    return orig_in


class CommandTest(TestCase):

    def test_pprint_duplicate_keys(self):
        "Output: table with duplicate keys"
        expected = "\n".join(["+------+------+",
                              "| name | name |",
                              "+------+------+",
                              "+------+------+\n"])
        command = CrateCmd()
        with capture(command.pprint, [], ['name', 'name']) as output:
            self.assertEqual(expected, output)

    def test_stdin_cmd(self):
        "Test passing in SQL via stdin"
        stmt = "select 'via-stdin' from information_schema.tables limit 1"
        orig_argv = sys.argv[:]
        sys.argv = ['testcrash',
                    '--hosts', self.crate_host]
        orig_in = mock_stdin(stmt)
        with capture(main) as output:
            self.assert_(output.find('via-stdin') != -1)
        sys.stdin.close()
        sys.stdin = orig_in
        sys.argv = orig_argv

    def test_cmd_precedence(self):
        """Test precedence of SQL passed in via -c vs. stdin
        SQL passed in via --command should take precedence
        over stdin
        """
        stmt = "select '%s' from information_schema.tables limit 1"
        orig_argv = sys.argv[:]
        sys.argv = ['testcrash',
                    "--command", stmt % 'via-command',
                    '--hosts', self.crate_host]
        orig_in = mock_stdin(stmt % 'via-stdin')
        with capture(main) as output:
            self.assert_(output.find('via-command') != -1)
            self.assert_(output.find('via-stdin') == -1)
        sys.stdin.close()
        sys.stdin = orig_in
        sys.argv = orig_argv
