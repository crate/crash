# vim: set fileencodings=utf-8
# -*- coding: utf-8; -*-
# PYTHON_ARGCOMPLETE_OK
#
# Licensed to CRATE Technology GmbH ("Crate") under one or more contributor
# license agreements.  See the NOTICE file distributed with this work for
# additional information regarding copyright ownership.  Crate licenses
# this file to you under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.  You may
# obtain a copy of the License at
#
#   http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS, WITHOUT
# WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.  See the
# License for the specific language governing permissions and limitations
# under the License.
#
# However, if you have executed another commercial license agreement
# with Crate these terms will supersede the license and you may use the
# software solely pursuant to the terms of the relevant commercial agreement.


from __future__ import print_function

import os
import sys
import select
import logging

from argparse import ArgumentParser
from collections import namedtuple

from prompt_toolkit.completion import Completer, Completion
from prompt_toolkit.history import FileHistory
from prompt_toolkit.buffer import Buffer
from prompt_toolkit.filters import Condition, IsDone, HasFocus, Always

from ..crash import __version__ as crash_version
from crate.client import connect
from crate.client.exceptions import ConnectionError, ProgrammingError

from pygments.lexers.sql import SqlLexer
from pygments.style import Style as PygmentsStyle
from pygments.token import (Keyword,
                            Comment,
                            Operator,
                            Number,
                            Literal,
                            String,
                            Error)

from .printer import ColorPrinter, PrintWrapper
from .outputs import OutputWriter
from .sysinfo import SysInfoCommand

from appdirs import user_data_dir

from distutils.version import StrictVersion

CHECK_MIN_VERSION = StrictVersion("0.52.0")

try:
    from logging import NullHandler
except ImportError:
    from logging import Handler

    class NullHandler(Handler):
        def emit(self, record):
            pass

logging.getLogger('crate').addHandler(NullHandler())

USER_DATA_DIR = user_data_dir("Crate", "Crate")
HISTORY_FILE_NAME = 'crash_history'
HISTORY_PATH = os.path.join(USER_DATA_DIR, HISTORY_FILE_NAME)
MAX_HISTORY_LENGTH = 10000

Result = namedtuple('Result', ['cols',
                               'rows',
                               'rowcount',
                               'duration',
                               'output_width'])


def parse_args(output_formats):
    parser = ArgumentParser(description='crate shell')
    parser.add_argument('-v', '--verbose', action='count',
                        dest='verbose', default=0,
                        help='use -v to get debug output')
    parser.add_argument('--history',
                        type=str,
                        help='the history file to use', default=HISTORY_PATH)

    group = parser.add_mutually_exclusive_group()
    group.add_argument('-c', '--command', type=str,
                        help='execute sql statement')
    group.add_argument('--sysinfo', action='store_true', default=False,
                        help='show system information')

    parser.add_argument('--hosts', type=str, nargs='*',
                        help='the crate hosts to connect to', metavar='HOST')
    parser.add_argument('--format', type=str, default='tabular', choices=output_formats,
                        help='output format of the sql response', metavar='FORMAT')
    parser.add_argument('--version', action='store_true', default=False,
                        help='show crash version and exit')
    try:
        import argcomplete
        argcomplete.autocomplete(parser)
    except ImportError:
        pass
    args = parser.parse_args()
    return args


class TruncatedFileHistory(FileHistory):

    def __init__(self, filename, max_length=1000):
        super(TruncatedFileHistory, self).__init__(filename)
        base = os.path.dirname(filename)
        if not os.path.exists(base):
            os.makedirs(base)
        if not os.path.exists(filename):
            with open(filename, 'a'):
                os.utime(filename, None)
        self.max_length = max_length

    def append(self, string):
        self.strings = self.strings[:max(0, self.max_length-1)]
        super(TruncatedFileHistory, self).append(string)


class SQLCompleter(Completer):
    keywords = [
        "select", "insert", "update", "delete",
        "table", "index", "from", "into", "where", "values", "and", "or",
        "set", "with", "by", "using", "like",
        "boolean", "integer", "string", "float", "double", "short", "long",
        "byte", "timestamp", "ip", "object", "dynamic", "strict", "ignored",
        "array", "blob", "primary key",
        "analyzer", "extends", "tokenizer", "char_filters", "token_filters",
        "number_of_replicas", "clustered",
        "refresh", "alter",
        "sys", "doc", "blob",
    ]

    def __init__(self, conn, lines):
        self.client = conn.client
        self.lines = lines
        self.keywords += [kw.upper() for kw in self.keywords]

    def get_completions(self, document, complete_event):
        line = document.text
        if line.startswith('\\'):
            return
        word_before_cursor = document.get_word_before_cursor()
        for keyword in self.keywords:
            if keyword.startswith(word_before_cursor):
                yield Completion(keyword, -len(word_before_cursor))


def noargs_command(fn):
    def inner_fn(self, *args):
        if len(args):
            self.logger.critical("Command does not take any arguments.")
            return
        return fn(self, *args)
    inner_fn.__doc__ = fn.__doc__
    return inner_fn


class CrateStyle(PygmentsStyle):
    default_style = "noinherit"
    styles = {
        Keyword: 'bold #4b95a3',
        Comment: '#757265',
        Operator: '#e83131',
        Number: '#be61ff',
        Literal: '#ae81ff',
        String: '#f4a33d',
        Error: '#ff3300',
    }


class CrateCmd(object):

    EXCLUDE_ROWCOUNT = ['create', 'alter', 'drop', 'refresh', 'set', 'reset']

    def __init__(self,
                 output_writer=None,
                 connection=None,
                 error_trace=False,
                 is_tty=True):
        self.error_trace = error_trace
        self.connection = connection or connect(error_trace=error_trace)
        self.cursor = self.connection.cursor()
        self.output_writer = output_writer or OutputWriter(PrintWrapper(), is_tty)
        self.lines = []
        self.exit_code = 0
        self.expanded_mode = False
        self.sys_info_cmd = SysInfoCommand(self)
        self.commands = {
            '?': self._help,
            'q': self._quit,
            'c': self._connect,
            'format': self._switch_format,
            'connect': self._connect,
            'dt': self._show_tables,
            'check': self._check,
            'sysinfo': self.sys_info_cmd.execute,
        }
        self.logger = ColorPrinter(is_tty)

    def get_num_columns(self):
        return 80

    def pprint(self, rows, cols):
        result = Result(cols,
                        rows,
                        self.cursor.rowcount,
                        self.cursor.duration,
                        self.get_num_columns())
        self.output_writer.write(result)

    def process(self, text):
        if text.lstrip().startswith('--'):
            return
        text = text.rstrip()
        if text.startswith('\\') and not self.lines:
            self._try_exec_cmd(text.lstrip('\\'))
        elif text.endswith(';'):
            line = text.rstrip(';')
            if self.lines:
                self.lines.append(line)
                line = ' '.join(self.lines)
                self._exec(line)
                self.lines[:] = []
            else:
                self._exec(line)
        elif text:
            self.lines.append(text)

    def exit(self):
        if self.lines:
            self._exec(' '.join(self.lines))
            self.lines[:] = []


    @noargs_command
    def _help(self, *args):
        """ print this help """
        out = []
        for k, v in sorted(self.commands.items()):
            doc = v.__doc__ and v.__doc__.strip()
            out.append('\{0:<30} {1}'.format(k, doc))
        return '\n'.join(out)

    @noargs_command
    def _show_tables(self, *args):
        """ print the existing tables within the 'doc' schema """
        self._exec("""select format('%s.%s', schema_name, table_name) as name
                      from information_schema.tables
                      where schema_name not in ('sys','information_schema')""")

    def check(self, *args):
        success = self._execute("""select description as "Failed checks"
                                   from sys.checks
                                   where passed=false """)
        self.exit_code = self.exit_code or int(not success)
        if not success:
            return False
        cur = self.cursor
        print_vars = {
            's': 'S'[cur.rowcount == 1:],
            'rowcount': cur.rowcount
        }
        checks = cur.fetchall()
        if len(checks):
            self.pprint(checks, [c[0] for c in cur.description])
            tmpl = '{rowcount} CLUSTER CHECK{s} FAILED'
            self.logger.critical(tmpl.format(**print_vars))
        else:
            self.logger.info('CLUSTER CHECK OK')
        return True

    @noargs_command
    def _check(self, *args):
        """ print failed cluster checks """
        if self.connection.lowest_server_version >= CHECK_MIN_VERSION:
            self.check()
        else:
            tmpl = '\nCrate {version} does not support the cluster "check" command'
            self.logger.warn(tmpl.format(version=self.connection.lowest_server_version))

    @noargs_command
    def _quit(self, *args):
        """ quit crash """
        self.logger.warn(u'Bye!')
        sys.exit(self.exit_code)

    def _switch_format(self, fmt=None):
        """ switch output format """
        if fmt and fmt in self.output_writer.formats:
            self.output_writer.output_format = fmt
            return u'changed output format to {0}'.format(fmt)
        return u'{0} is not a valid output format.\nUse one of: {1}'.format(
            fmt, ', '.join(self.output_writer.formats))

    def is_conn_avaliable(self):
        if self.connection.lowest_server_version == StrictVersion("0.0.0"):
            self.logger.critical(u'CONNECT ERROR')
            return False
        else:
            return True

    def _connect(self, server):
        """ connect to the given server, e.g.: \connect localhost:4200 """
        self.connection = connect(servers=server, error_trace=self.error_trace)
        self.cursor = self.connection.cursor()
        results = []
        failed = 0
        client = self.connection.client
        for server in client.active_servers:
            try:
                infos = client.server_infos(server)
            except ConnectionError as e:
                failed += 1
                results.append([server, None, '0.0.0', False, e.message])
            else:
                results.append(infos + (True, 'OK', ))
        self.pprint(results,
                    ['server_url', 'node_name', 'version', 'connected', 'message'])
        if failed == len(results):
            self.logger.critical('CONNECT ERROR')
        else:
            self.logger.info('CONNECT OK')
            self._check()

    def _try_exec_cmd(self, line):
        words = line.split(' ', 1)
        if not words or not words[0]:
            return False
        cmd = self.commands.get(words[0].lower().rstrip(';'))
        if len(words) > 1:
            words[1] = words[1].rstrip(';')
        if cmd:
            try:
                message = cmd(*words[1:])
            except TypeError as e:
                self.logger.critical(e.message)
                doc = cmd.__doc__
                if doc and not doc.isspace():
                    self.logger.info('help: {0}'.format(words[0].lower()))
                    self.logger.info(cmd.__doc__)
            except Exception as e:
                self.logger.critical(e.message);
            else:
                if message:
                    self.logger.info(message)
            return True
        else:
            self.logger.critical('Unknown command. Type \? for a full list of available commands.')
        return False

    def _exec(self, line):
        success = self.execute(line)
        self.exit_code = self.exit_code or int(not success)

    def _execute(self, statement):
        try:
            self.cursor.execute(statement)
            return True
        except ConnectionError:
            self.logger.warn('Use \connect <server> to connect to one or more servers first.')
        except ProgrammingError as e:
            self.logger.critical(e.message)
            if self.error_trace:
                self.logger.critical('\n' + e.error_trace)
        return False

    def execute(self, statement):
        success = self._execute(statement)
        if not success:
            return False
        cur = self.cursor
        command = statement[:statement.index(' ')].upper()
        duration = ''
        if cur.duration > -1 :
            duration = ' ({0:.3f} sec)'.format(float(cur.duration)/1000.0)
        print_vars = {
            'command': command,
            'rowcount': cur.rowcount,
            's': 's'[cur.rowcount == 1:],
            'duration': duration
        }
        if cur.description:
            self.pprint(cur.fetchall(), [c[0] for c in cur.description])
            tmpl = '{command} {rowcount} row{s} in set{duration}'
        else:
            tmpl = '{command} OK'
            if command.lower() not in self.EXCLUDE_ROWCOUNT:
                tmpl += ', {rowcount} row{s} affected'
            tmpl += '{duration}'
        self.logger.info(tmpl.format(**print_vars))
        return True


def get_stdin():
    """
    Get data from stdin, if any
    """
    # use select.select to check if input is available
    # otherwise sys.stdin would block
    while sys.stdin in select.select([sys.stdin], [], [], 0)[0]:
        line = sys.stdin.readline()
        if line:
            yield line
        else:
            break
    return

def _enable_vi_mode():
    files = ['/etc/inputrc', os.path.expanduser('~/.inputrc')]
    for filepath in files:
        try:
            with open(filepath, 'r') as f:
                for line in f:
                    if line.strip() == 'set editing-mode vi':
                        return True
        except IOError:
            continue
    return False


class CrashBuffer(Buffer):
    def __init__(self, *args, **kwargs):

        @Condition
        def is_multiline():
            doc = self.document
            if not doc.text:
                return False
            if doc.text.startswith('\\'):
                return False
            return not doc.text.rstrip().endswith(';')

        super(self.__class__, self).__init__(
            *args, is_multiline=is_multiline, **kwargs)


def loop(cmd, history_file):
    from prompt_toolkit import CommandLineInterface, AbortAction, Application
    from prompt_toolkit.interface import AcceptAction
    from prompt_toolkit.enums import DEFAULT_BUFFER
    from prompt_toolkit.layout.processors import (
        HighlightMatchingBracketProcessor,
        ConditionalProcessor
    )
    from prompt_toolkit.key_binding.manager import KeyBindingManager
    from prompt_toolkit.shortcuts import (create_default_layout,
                                          create_default_output,
                                          create_eventloop)

    key_binding_manager = KeyBindingManager(
        enable_search=True,
        enable_abort_and_exit_bindings=True,
        enable_vi_mode=Condition(lambda cli: _enable_vi_mode()))

    layout = create_default_layout(
        message=u'cr> ',
        multiline=True,
        lexer=SqlLexer,
        extra_input_processors=[
            ConditionalProcessor(
                processor=HighlightMatchingBracketProcessor(chars='[](){}'),
                filter=HasFocus(DEFAULT_BUFFER) & ~IsDone())
        ]
    )
    cli_buffer = CrashBuffer(
        history=TruncatedFileHistory(history_file, max_length=MAX_HISTORY_LENGTH),
        accept_action=AcceptAction.RETURN_DOCUMENT,
        completer=SQLCompleter(cmd.connection, cmd.lines),
        complete_while_typing=Always()
    )
    application = Application(
        layout=layout,
        style=CrateStyle,
        buffer=cli_buffer,
        key_bindings_registry=key_binding_manager.registry,
        on_exit=AbortAction.RAISE_EXCEPTION,
        on_abort=AbortAction.RETRY,
    )
    eventloop = create_eventloop()
    output = create_default_output()
    cli = CommandLineInterface(
        application=application,
        eventloop=eventloop,
        output=output
    )

    def get_num_columns_override():
        return output.get_size().columns
    cmd.get_num_columns = get_num_columns_override

    while True:
        try:
            doc = cli.run()
            if doc:
                cmd.process(doc.text)
        except EOFError:
            cmd.logger.warn(u'Bye!')
            return


def main():
    is_tty = sys.stdout.isatty()
    output_writer = OutputWriter(PrintWrapper(), is_tty)
    args = parse_args(output_writer.formats)
    output_writer.output_format = args.format

    if args.version:
        print(crash_version)
        sys.exit(0)
    error_trace = args.verbose > 0
    conn = connect(args.hosts)
    cmd = CrateCmd(connection=conn,
                   error_trace=error_trace,
                   output_writer=output_writer,
                   is_tty=is_tty)
    if error_trace:
        # log CONNECT command only in verbose mode
        cmd._connect(args.hosts)
    done = False
    stdin_data = None
    if os.name == 'posix':
        stdin_data = get_stdin()
    if args.sysinfo:
        prev_format = cmd.output_writer.output_format
        cmd._switch_format('mixed')
        cmd.sys_info_cmd.execute()
        cmd._switch_format(prev_format)
        done = True
    if args.command:
        cmd.process(args.command)
        done = True
    elif stdin_data:
        for data in stdin_data:
            cmd.process(data)
            done = True
    if not done:
        loop(cmd, args.history)
    cmd.exit()
    sys.exit(cmd.exit_code)


if __name__ == '__main__':
    main()
