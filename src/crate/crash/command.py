# -*- coding: utf-8; -*-
# vim: set fileencodings=utf-8
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

import re
import os
import sys
import csv
import json
import select

from argparse import ArgumentParser
from colorama import Fore, Style
from functools import partial
from six import PY2, StringIO

from prompt_toolkit.completion import Completer, Completion
from prompt_toolkit.history import FileHistory
from prompt_toolkit.layout.prompt import DefaultPrompt

from crate.client import connect
from crate.client.exceptions import ConnectionError, ProgrammingError

from pygments import highlight
from pygments.formatters import TerminalFormatter
from pygments.lexers.data import JsonLexer
from pygments.lexers.sql import SqlLexer
from pygments.token import Token
from pygments.styles.monokai import MonokaiStyle

from .tabulate import TableFormat, Line as TabulateLine, DataRow, tabulate
from .printer import ColorPrinter, PrintWrapper

from appdirs import user_data_dir

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

    def get_completions(self, document):
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

    def tokens(self, cli):
        if self.lines:
            prompt = '... '
        else:
            prompt = 'cr> '
        return [(Token.Prompt, prompt)]


class CrateCmd(object):

    OUTPUT_FORMATS = ['tabular', 'json', 'csv', 'raw', 'mixed']
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
        try:
            if self.output_format == 'raw':
                self.pprint_raw(rows, cols, writer=self.print)
            elif self.output_format == 'json':
                self.pprint_json(rows, cols, writer=self.print)
            elif self.output_format == 'csv':
                self.pprint_csv(rows, cols, writer=self.print)
            elif self.output_format == 'mixed':
                self.pprint_mixed(rows, cols, writer=self.print)
            else:
                self.pprint_tabular(rows, cols, writer=self.print)
            self.print.write('\n')
        except UnicodeEncodeError:
            try:
                print(out.encode('utf-8').decode('ascii', 'replace'))
            except UnicodeEncodeError:
                print(out.encode('utf-8').decode('ascii', 'ignore'))
            self.logger.warn('WARNING: Unicode characters found that cannot be displayed. Check your system locale.')

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
            duration=duration > -1 and float(duration/1000.0) or duration,
        ), writer=writer)

    def pprint_json(self, rows, cols, writer=sys.stdout):
        obj = [dict(zip(cols, x)) for x in rows]
        self._json_format(obj, writer=writer)

    def pprint_csv(self, rows, cols, writer=sys.stdout):
        wr = csv.writer(writer, doublequote=False, escapechar='\\')
        wr.writerow(cols)
        for row in rows:
            wr.writerow(row)

    def pprint_mixed(self, rows, cols, writer=sys.stdout):
        padding = max_col_len = max(len(c) for c in cols)
        if self.is_tty:
            max_col_len += len(Fore.YELLOW + Style.RESET_ALL)
        tmpl = '{0:<'+str(max_col_len)+'} | {1}'
        row_delimiter = '-' * get_num_columns()
        out = []
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
        except TypeError as e:
            pass
        else:
            if self.is_tty:
                json_str = highlight(json_str, _json_lexer, _formatter).rstrip('\n')
            writer.write(json_str)

    def _mixed_format(self, value, max_col_len, padding):
        if isinstance(value, dict) or isinstance(value, list):
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

    def _help(self, *args):
        """ print this help """
        out = []
        for k, v in sorted(self.commands.items()):
            doc = v.__doc__ and v.__doc__.strip()
            out.append('\{:<30} {}'.format(k, doc))
        return '\n'.join(out)

    def _show_tables(self, *args):
        """ print the existing tables within the 'doc' schema """
        self._exec("""select format('%s.%s', schema_name, table_name) as name
                      from information_schema.tables
                      where schema_name not in ('sys','information_schema')""")

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
        """ connect to the given server """
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
            message = cmd(' '.join(words[1:]))
            if message:
                self.logger.info(message)
            return True
        return False

    def _exec(self, line):
        success = self.execute(line)
        self.exit_code = self.exit_code or int(not success)

    def _execute(self, statement):
        try:
            self.cursor.execute(statement)
            return True
        except ConnectionError:
            self.logger.warn('Use \connect <server> to connect to one or more server first.')
        except ProgrammingError as e:
            self.logger.critical(e.message)
        return False

    def execute(self, statement):
        success = self._execute(statement)
        if not success:
            return False
        cur = self.cursor
        command = statement[:statement.index(' ')].upper()
        duration = ''
        if cur.duration > -1 :
            duration = ' ({0:.3f} sec)'.format(float(cur.duration / 1000))
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

def _detect_key_bindings():
    from prompt_toolkit.key_bindings.vi import vi_bindings
    files = ['/etc/inputrc', os.path.expanduser('~/.inputrc')]
    for filepath in files:
        try:
            with open(filepath, 'r') as f:
                for line in f:
                    if line.strip() == 'set editing-mode vi':
                        return [vi_bindings]
        except IOError:
            continue
    return None

def loop(cmd, history_file):
    from prompt_toolkit import CommandLineInterface, AbortAction
    from prompt_toolkit import Exit
    from prompt_toolkit.layout import Layout
    from prompt_toolkit.line import Line
    from prompt_toolkit.renderer import Output

    cli_line = Line(
        completer=SQLCompleter(cmd.connection, cmd.lines),
        history=TruncatedFileHistory(history_file, max_length=MAX_HISTORY_LENGTH)
    )
    layout = Layout(
        before_input=CrashPrompt(cmd.lines),
        menus=[],
        lexer=SqlLexer,
        bottom_toolbars=[],
        show_tildes=False,
    )
    key_binding_factories = _detect_key_bindings()
    cli = CommandLineInterface(
        style=MonokaiStyle,
        layout=layout,
        line=cli_line,
        key_binding_factories=key_binding_factories
    )
    output = Output(cli.renderer.stdout)
    global get_num_columns
    def get_num_columns():
        return output.get_size().columns
    try:
        while True:
            doc = cli.read_input(on_exit=AbortAction.RAISE_EXCEPTION)
            cmd.process(doc.text)
    except Exit: # Quit on Ctrl-D keypress
        cmd.logger.warn(u'Bye!')
        return

def main():
    args = parse_args(CrateCmd.OUTPUT_FORMATS)
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
