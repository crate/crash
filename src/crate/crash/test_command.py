import sys
from unittest import TestCase
from six import StringIO

from .command import CrateCmd
from contextlib import contextmanager


@contextmanager
def capture(command, *args, **kwargs):
    stdout = StringIO()
    orig_out, sys.stdout = sys.stdout, stdout
    command(*args, **kwargs)
    sys.stdout = orig_out
    stdout.seek(0)
    yield stdout.read()


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
