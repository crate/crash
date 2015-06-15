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
import csv
import json
import select
import logging

from argparse import ArgumentParser
from colorama import Fore, Style

from prompt_toolkit.completion import Completer, Completion
from prompt_toolkit.history import FileHistory
from prompt_toolkit.layout.prompt import DefaultPrompt

from ..crash import __version__ as crash_version
from crate.client import connect
from crate.client.exceptions import ConnectionError, ProgrammingError

from pygments import highlight
from pygments.formatters import TerminalFormatter
from pygments.lexers.data import JsonLexer
from pygments.lexers.sql import SqlLexer
from pygments.style import Style as PygmentsStyle
from pygments.token import Keyword, Comment, Operator, Number, Literal, String, Error

from .tabulate import TableFormat, Line as TabulateLine, DataRow, tabulate
from .printer import ColorPrinter, PrintWrapper

from appdirs import user_data_dir

try:
    from logging import NullHandler
except ImportError:
    from logging import Handler

    class NullHandler(Handler):
        def emit(self, record):
            pass

logging.getLogger('crate').addHandler(NullHandler())

_json_lexer = JsonLexer()
_formatter = TerminalFormatter()

NULL = u'NULL'
TRUE = u'TRUE'
FALSE = u'FALSE'

USER_DATA_DIR = user_data_dir("Crate", "Crate")
HISTORY_FILE_NAME = 'crash_history'
HISTORY_PATH = os.path.join(USER_DATA_DIR, HISTORY_FILE_NAME)
MAX_HISTORY_LENGTH = 10000

crate_fmt = TableFormat(lineabove=TabulateLine("+", "-", "+", "+"),
                        linebelowheader=TabulateLine("+", "-", "+", "+"),
                        linebetweenrows=None,
                        linebelow=TabulateLine("+", "-", "+", "+"),
                        headerrow=DataRow("|", "|", "|"),
                        datarow=DataRow("|", "|", "|"),
                        padding=1, with_header_hide=None)

def parse_args(output_formats):
    parser = ArgumentParser(description='crate shell')
    parser.add_argument('-v', '--verbose', action='count',
                        dest='verbose', default=0,
                        help='use -v to get debug output')
    parser.add_argument('--history',
                        type=str,
                        help='the history file to use', default=HISTORY_PATH)
    parser.add_argument('-c', '--command', type=str,
                        help='execute sql statement')
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


def _transform_field(field):
    """transform field for displaying"""
    if isinstance(field, bool):
        return TRUE if field else FALSE
    elif isinstance(field, (list, dict)):
        return json.dumps(field, sort_keys=True, ensure_ascii=False)
    else:
        return field


def get_num_columns():
    return 80


class CrashPrompt(DefaultPrompt):
    def __init__(self, lines):
        self.lines = lines

    @property
    def prompt(self):
        if self.lines:
            return '... '
        else:
            return 'cr> '


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


def val_len(v):
    if not v:
        return 4  # will be displayed as NULL
    if isinstance(v, (list, dict)):
        return len(json.dumps(v))
    if hasattr(v, '__len__'):
        return len(v)
    return len(str(v))


class CrateCmd(object):

    OUTPUT_FORMATS = ['tabular', 'json', 'csv', 'raw', 'mixed', 'dynamic']
    EXCLUDE_ROWCOUNT = ['create', 'alter', 'drop', 'refresh', 'set', 'reset']

    def __init__(self, connection=None, error_trace=False,
                 output_format=None, is_tty=True):
        self.error_trace = error_trace
        self.is_tty = is_tty
        self.output_format = output_format
        self.connection = connection or connect(error_trace=error_trace)
        self.cursor = self.connection.cursor()
        self.lines = []
        self.exit_code = 0
        self.expanded_mode = False
        self.commands = {
            '?': self._help,
            'q': self._quit,
            'c': self._connect,
            'format': self._switch_format,
            'connect': self._connect,
            'dt': self._show_tables
        }
        self.logger = ColorPrinter(is_tty)
        self.print = PrintWrapper()

    def pprint(self, rows, cols):
        if self.output_format == 'raw':
            self.pprint_raw(rows, cols, writer=self.print)
        elif self.output_format == 'json':
            self.pprint_json(rows, cols, writer=self.print)
        elif self.output_format == 'csv':
            self.pprint_csv(rows, cols, writer=self.print)
        elif self.output_format == 'mixed':
            self.pprint_mixed(rows, cols, writer=self.print)
        elif self.output_format == 'dynamic':
            self.pprint_dynamic(rows, cols, writer=self.print)
        else:
            self.pprint_tabular(rows, cols, writer=self.print)
        self.print.write('\n')

    def pprint_tabular(self, rows, cols, writer=sys.stdout):
        rows = [list(map(_transform_field, row)) for row in rows]
        out = tabulate(rows, headers=cols, tablefmt=crate_fmt, floatfmt="", missingval=NULL)
        writer.write(out)

    def pprint_raw(self, rows, cols, writer=sys.stdout):
        duration = self.cursor.duration
        self._json_format(dict(
            rows=rows,
            cols=cols,
            rowcount=self.cursor.rowcount,
            duration=duration > -1 and float(duration)/1000.0 or duration,
        ), writer=writer)

    def pprint_json(self, rows, cols, writer=sys.stdout):
        obj = [dict(zip(cols, x)) for x in rows]
        self._json_format(obj, writer=writer)

    def pprint_csv(self, rows, cols, writer=sys.stdout):
        wr = csv.writer(writer, doublequote=False, escapechar='\\')
        wr.writerow(cols)
        for row in rows:
            wr.writerow(row)

    def pprint_dynamic(self, rows, cols, writer=sys.stdout):
        max_cols_required = sum(len(c) + 4 for c in cols) + 1
        for row in rows:
            cols_required = sum(val_len(v) + 4 for v in row) + 1
            if cols_required > max_cols_required:
                max_cols_required = cols_required
        if max_cols_required > get_num_columns():
            self.pprint_mixed(rows, cols, writer)
        else:
            self.pprint_tabular(rows, cols, writer)

    def pprint_mixed(self, rows, cols, writer=sys.stdout):
        padding = max_col_len = max(len(c) for c in cols)
        if self.is_tty:
            max_col_len += len(Fore.YELLOW + Style.RESET_ALL)
        tmpl = '{0:<'+str(max_col_len)+'} | {1}'
        row_delimiter = '-' * get_num_columns()
        for row in rows:
            for i, c in enumerate(cols):
                val = self._mixed_format(row[i], max_col_len, padding)
                if self.is_tty:
                    c = Fore.YELLOW + c + Style.RESET_ALL
                writer.write(tmpl.format(c, val))
            writer.write(row_delimiter + '\n')

    def _json_format(self, obj, writer=sys.stdout):
        try:
            json_str = json.dumps(obj, indent=2)
        except TypeError:
            pass
        else:
            if self.is_tty:
                json_str = highlight(json_str, _json_lexer, _formatter).rstrip('\n')
            writer.write(json_str)

    def _mixed_format(self, value, max_col_len, padding):
        if value is None:
            value = 'NULL'
        if isinstance(value, (list, dict)):
            json_str = json.dumps(value, indent=2, sort_keys=True)
            if self.is_tty:
                json_str = highlight(json_str, _json_lexer, _formatter).rstrip('\n')
            lines = json_str.split('\n')
            lines[-1] = ' ' + lines[-1]
            lines = [lines[0]] + [' ' * padding + ' |' + l for l in lines[1:]]
            value = '\n'.join(lines)
        return '{0}\n'.format(value)

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

    @noargs_command
    def _quit(self, *args):
        """ quit crash """
        self.logger.warn(u'Bye!')
        sys.exit(self.exit_code)

    def _switch_format(self, fmt=None):
        """ switch output format """
        if fmt and fmt in self.OUTPUT_FORMATS:
            self.output_format = fmt
            return u'changed output format to {0}'.format(fmt)
        return u'{0} is not a valid output format.\nUse one of: {1}'.format(fmt, ', '.join(self.OUTPUT_FORMATS))

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

    def _try_exec_cmd(self, line):
        words = line.split(' ', 1)
        if not words or not words[0]:
            return False
        cmd = self.commands.get(words[0].lower())
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
                self.print.write('\n' + e.error_trace)
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


def _create_default_layout(lines_ref):
    from prompt_toolkit.layout.dimension import LayoutDimension
    from prompt_toolkit.layout import HSplit, Window, FloatContainer, Float
    from prompt_toolkit.layout.controls import BufferControl
    from prompt_toolkit.layout.menus import CompletionsMenu
    from prompt_toolkit.filters import HasFocus

    input_processors = [CrashPrompt(lines_ref)]
    return HSplit([FloatContainer(
        Window(
            BufferControl(input_processors, lexer=SqlLexer),
            LayoutDimension(min=8)
        ),
        [
            Float(xcursor=True,
                  ycursor=True,
                  content=CompletionsMenu(max_height=16,
                                          extra_filter=HasFocus('default')))
        ]
    )])


def is_multiline(doc):
    if not doc.text:
        return False
    if doc.text.startswith('\\'):
        return False
    return not doc.text.rstrip().endswith(';')

def loop(cmd, history_file):
    from prompt_toolkit import CommandLineInterface, AbortAction
    from prompt_toolkit import Exit
    from prompt_toolkit.buffer import Buffer
    from prompt_toolkit.renderer import Output
    from prompt_toolkit.key_binding.manager import KeyBindingManager

    key_binding_manager = KeyBindingManager(enable_vi_mode=_enable_vi_mode())
    buffer = Buffer(
        history=TruncatedFileHistory(history_file, max_length=MAX_HISTORY_LENGTH),
        completer=SQLCompleter(cmd.connection, cmd.lines),
        is_multiline=is_multiline
    )
    cli = CommandLineInterface(
        style=CrateStyle,
        layout=_create_default_layout(cmd.lines),
        buffer=buffer,
        key_bindings_registry=key_binding_manager.registry
    )
    output = Output(cli.renderer.stdout)
    global get_num_columns

    def get_num_columns_override():
        return output.get_size().columns
    get_num_columns = get_num_columns_override

    try:
        while True:
            doc = cli.read_input(on_exit=AbortAction.RAISE_EXCEPTION)
            if doc:
                cmd.process(doc.text)
    except Exit:  # Quit on Ctrl-D keypress
        cmd.logger.warn(u'Bye!')
        return


def main():
    args = parse_args(CrateCmd.OUTPUT_FORMATS)
    if args.version:
        print(crash_version)
        sys.exit(0)
    error_trace = args.verbose > 0
    conn = connect(args.hosts)
    cmd = CrateCmd(connection=conn, error_trace=error_trace,
                   output_format=args.format, is_tty=sys.stdout.isatty())
    if error_trace:
        # log CONNECT command only in verbose mode
        cmd._connect(args.hosts)
    done = False
    stdin_data = None
    if os.name == 'posix':
        stdin_data = get_stdin()
    if args.command:
        cmd.process(args.command)
        done = True
    elif stdin_data:
        for data in stdin_data:
            cmd.process(data)
            done = True
    if not done:
        loop(cmd,args.history)
    cmd.exit()
    sys.exit(cmd.exit_code)


if __name__ == '__main__':
    main()
