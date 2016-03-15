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
import re
import logging

from argparse import ArgumentParser
from collections import namedtuple

from ..crash import __version__ as crash_version
from crate.client import connect
from crate.client.exceptions import ConnectionError, ProgrammingError


from .printer import ColorPrinter, PrintWrapper
from .outputs import OutputWriter
from .sysinfo import SysInfoCommand
from .commands import built_in_commands, Command

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


def noargs_command(fn):
    def inner_fn(self, *args):
        if len(args):
            self.logger.critical("Command does not take any arguments.")
            return
        return fn(self, *args)
    inner_fn.__doc__ = fn.__doc__
    return inner_fn


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
            'q': self._quit,
            'c': self._connect,
            'connect': self._connect,
            'dt': self._show_tables,
            'check': self._check,
            'sysinfo': self.sys_info_cmd.execute,
        }
        self.commands.update(built_in_commands)
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
                if isinstance(cmd, Command):
                    message = cmd(self, *words[1:])
                else:
                    message = cmd(*words[1:])
            except TypeError as e:
                self.logger.critical(getattr(e, 'message', None) or repr(e))
                doc = cmd.__doc__
                if doc and not doc.isspace():
                    self.logger.info('help: {0}'.format(words[0].lower()))
                    self.logger.info(cmd.__doc__)
            except Exception as e:
                self.logger.critical(getattr(e, 'message', None) or repr(e))
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
        except KeyboardInterrupt:
            self.logger.warn("Query not cancelled. Run KILL <jobId> to cancel it")
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
        command = statement[:re.search("\s", statement).start()].upper()
        duration = ''
        if cur.duration > -1:
            duration = ' ({0:.3f} sec)'.format(float(cur.duration) / 1000.0)
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
    if not sys.stdin.isatty():
        for line in sys.stdin:
            yield line
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
    stdin_data = get_stdin()
    if args.sysinfo:
        cmd.output_writer.output_format = 'mixed'
        cmd.sys_info_cmd.execute()
        done = True
    if args.command:
        cmd.process(args.command)
        done = True
    elif stdin_data:
        for data in stdin_data:
            cmd.process(data)
            done = True
    if not done:
        from .repl import loop
        loop(cmd, args.history)
    cmd.exit()
    sys.exit(cmd.exit_code)


if __name__ == '__main__':
    main()
