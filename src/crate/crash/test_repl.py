
from unittest import TestCase
from .repl import SQLCompleter
from .command import CrateCmd


class SQLCompleterTest(TestCase):
    def setUp(self):
        self.cmd = CrateCmd()
        self.completer = SQLCompleter(self.cmd)

    def test_get_builtin_command_completions(self):
        c = self.completer
        result = sorted(list(c.get_command_completions('\\c')))
        self.assertEqual(result, ['c', 'check', 'connect'])

    def test_get_command_completions_format(self):
        cmd = CrateCmd()
        completer = SQLCompleter(cmd)
        result = list(completer.get_command_completions(r'\format dyn'))
        self.assertEqual(result, ['dynamic'])
