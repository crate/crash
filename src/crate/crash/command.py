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


from .config import Configuration, ConfigurationError
from .printer import ColorPrinter, PrintWrapper
from .outputs import OutputWriter
from .sysinfo import SysInfoCommand
from .commands import built_in_commands, Command

from distutils.version import StrictVersion

from appdirs import user_data_dir, user_config_dir

import urllib3
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)


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

USER_CONFIG_DIR = user_config_dir("Crate", "Crate")
CONFIG_FILE_NAME = 'crash.cfg'
CONFIG_PATH = os.path.join(USER_CONFIG_DIR, CONFIG_FILE_NAME)

Result = namedtuple('Result', ['cols',
                               'rows',
                               'rowcount',
                               'duration',
                               'output_width'])

def parse_config_path(args=sys.argv):
    """
    Preprocess sys.argv and extract --config argument.
    """

    config = CONFIG_PATH
    if '--config' in args:
        idx = args.index('--config')
        if len(args) > idx + 1:
            config = args.pop(idx + 1)
        _ = args.pop(idx)
    return config


def parse_args(parser):
    """
    Parse sys.argv arguments with given parser
    """
    try:
        import argcomplete
        argcomplete.autocomplete(parser)
    except ImportError:
        pass
    args = parser.parse_args()
    return args

def boolean(v):
    if str(v).lower() in ("yes", "true", "t", "1"):
        return True
    elif str(v).lower() in ("no", "false", "f", "0"):
        return False
    else:
        raise ValueError('not a boolean value')

def get_parser(output_formats=[], conf=None):
    """
    Create an argument parser that reads default values from a
    configuration file if provided.
    """

    def _conf_or_default(key, value):
        return conf and conf.get_or_set(key, value) or value

    parser = ArgumentParser(description='crate shell')
    parser.add_argument('-v', '--verbose', action='count',
                        dest='verbose', default=int(_conf_or_default('verbosity', 0)),
                        help='use -v to get debug output')
    parser.add_argument('-A', '--no-autocomplete', action='store_false',
                        dest='autocomplete',
                        default=_conf_or_default('autocomplete', True),
                        help='use -A to disable SQL autocompletion')

    parser.add_argument('--history', type=str,
                        help='the history file to use', default=HISTORY_PATH)
    parser.add_argument('--config', type=str,
                        help='the configuration file to use', default=CONFIG_PATH)

    group = parser.add_mutually_exclusive_group()
    group.add_argument('-c', '--command', type=str,
                       help='execute sql statement')
    group.add_argument('--sysinfo', action='store_true', default=False,
                       help='show system information')

    parser.add_argument('--hosts', type=str, nargs='*',
                        default=_conf_or_default('hosts', 'localhost:4200'),
                        help='the crate hosts to connect to', metavar='HOST')
    parser.add_argument('--verify-ssl', type=boolean, default=True)
    parser.add_argument('--cert-file', type=str,
                        help='path to client certificate')
    parser.add_argument('--key-file', type=str,
                        help='path to the key file for the client certificate')
    parser.add_argument('--format', type=str,
                        default=_conf_or_default('format', 'tabular'),
                        choices=output_formats,
                        help='output format of the sql response', metavar='FORMAT')
    parser.add_argument('--version', action='store_true', default=False,
                        help='show crash version and exit')

    return parser


def noargs_command(fn):
    def inner_fn(self, *args):
        if len(args):
            self.logger.critical("Command does not take any arguments.")
            return
        return fn(self, *args)
    inner_fn.__doc__ = fn.__doc__
    return inner_fn


class CrateCmd(object):

    def __init__(self,
                 output_writer=None,
                 connection=None,
                 error_trace=False,
                 is_tty=True,
                 autocomplete=True):
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
            'sysinfo': self.sys_info_cmd.execute,
        }
        self.commands.update(built_in_commands)
        self.logger = ColorPrinter(is_tty)
        self._autocomplete = autocomplete

    def get_num_columns(self):
        return 80

    def should_autocomplete(self):
        return self._autocomplete

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
                      where schema_name not in ('sys','information_schema', 'pg_catalog')""")

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

            # check for failing node and cluster checks
            built_in_commands['check'](self, startup=True)

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
        except ProgrammingError as e:
            self.logger.critical(e.message)
            if self.error_trace and e.error_trace:
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
            tmpl = '{command} OK, {rowcount} row{s} affected {duration}'
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
    printer = ColorPrinter(is_tty)
    output_writer = OutputWriter(PrintWrapper(), is_tty)

    config = parse_config_path()
    conf = None
    try:
        conf = Configuration(config)
    except ConfigurationError as e:
        printer.warn(str(e))
        parser = get_parser(output_writer.formats)
        parser.print_usage()
        sys.exit(1)
    parser = get_parser(output_writer.formats, conf=conf)
    args = parse_args(parser)
    output_writer.output_format = args.format

    if args.version:
        printer.info(crash_version)
        sys.exit(0)
    error_trace = args.verbose > 0
    conn = connect(args.hosts,
                   verify_ssl_cert=args.verify_ssl,
                   cert_file=args.cert_file,
                   key_file=args.key_file)
    cmd = CrateCmd(connection=conn,
                   error_trace=error_trace,
                   output_writer=output_writer,
                   is_tty=is_tty,
                   autocomplete=args.autocomplete)
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
    conf.save()
    cmd.exit()
    sys.exit(cmd.exit_code)


if __name__ == '__main__':
    main()
