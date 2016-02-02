
from unittest import TestCase
from mock import patch
from .commands import ReadFileCommand


class ReadFileCommandTest(TestCase):

    @patch('glob.glob')
    def test_complete(self, fake_glob):
        fake_glob.return_value = ['foo', 'foobar']

        cmd = ReadFileCommand()
        results = cmd.complete('fo')

        self.assertEqual(results, ['foo', 'foobar'])
        fake_glob.assert_called_with('fo*.sql')
