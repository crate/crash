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

import logging
import os
import re
import sys
import urllib3
from appdirs import user_data_dir, user_config_dir
from argparse import ArgumentParser
from collections import namedtuple
from crate.client import connect
from crate.client.exceptions import ConnectionError, ProgrammingError
from distutils.version import StrictVersion
from urllib3.exceptions import LocationParseError

from .commands import built_in_commands, Command
from .config import Configuration, ConfigurationError
from .outputs import OutputWriter
from .printer import ColorPrinter, PrintWrapper
from .sysinfo import SysInfoCommand
from ..crash import __version__ as crash_version

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

TABLE_SCHEMA_MIN_VERSION = StrictVersion("0.57.0")


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

    return parser.parse_args()


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
        return value if conf is None else conf.get_or_set(key, value)

    parser = ArgumentParser(description='crate shell')
    parser.add_argument('-v', '--verbose', action='count',
                        dest='verbose', default=_conf_or_default('verbosity', 0),
                        help='use -v to get debug output')
    parser.add_argument('-A', '--no-autocomplete', action='store_false',
                        dest='autocomplete',
                        default=_conf_or_default('autocomplete', True),
                        help='use -A to disable SQL autocompletion')
    parser.add_argument('-a', '--autocapitalize', action='store_true',
                        dest='autocapitalize',
                        default=False,
                        help='use -a to enable experimental auto-capitalization of SQL keywords')
    parser.add_argument('-U', '--username', type=str,
                        help='the username to authenticate in the database')
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
                        default=_conf_or_default('hosts', ['localhost:4200']),
                        help='the crate hosts to connect to', metavar='HOST')
    parser.add_argument('--verify-ssl', type=boolean, default=True,
                        help='force verification of the SSL certificate of the server')
    parser.add_argument('--cert-file', type=file_with_permissions,
                        help='path to the client certificate file')
    parser.add_argument('--key-file', type=file_with_permissions,
                        help='path to the key file of the client certificate')
    parser.add_argument('--ca-cert-file', type=file_with_permissions,
                        help='path to the CA certificate file')
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
                 autocomplete=True,
                 autocapitalize=True,
                 verify_ssl=True,
                 cert_file=None,
                 key_file=None,
                 ca_cert_file=None,
                 username=None):
        self.error_trace = error_trace
        self.connection = connection or connect(error_trace=error_trace)
        self.cursor = self.connection.cursor()
        self.output_writer = output_writer or OutputWriter(
            PrintWrapper(), is_tty)
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
        self._autocapitalize = autocapitalize
        self.username = username
        self.verify_ssl = verify_ssl
        self.cert_file = cert_file
        self.key_file = key_file
        self.ca_cert_file = ca_cert_file
        self.last_connected_servers = None

    def get_num_columns(self):
        return 80

    def should_autocomplete(self):
        return self._autocomplete

    def should_autocapitalize(self):
        return self._autocapitalize

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
        self.cursor.close()
        self.connection.close()
        return self.exit_code

    @noargs_command
    def _show_tables(self, *args):
        """ print the existing tables within the 'doc' schema """
        schema_name = \
            "table_schema" if self.connection.lowest_server_version \
            >= TABLE_SCHEMA_MIN_VERSION else "schema_name"

        self._exec("select format('%s.%s', {schema}, table_name) as name "
                   "from information_schema.tables "
                   "where {schema} not in ('sys','information_schema', 'pg_catalog')"
                   .format(schema=schema_name))

    @noargs_command
    def _quit(self, *args):
        """ quit crash """
        self.logger.warn(u'Bye!')
        sys.exit(self.exit())

    def is_conn_available(self):
        if self.connection.lowest_server_version == StrictVersion("0.0.0"):
            return False
        else:
            return True

    def _do_connect(self):
        self.connection = connect(servers=self.last_connected_servers,
                                  error_trace=self.error_trace,
                                  verify_ssl_cert=self.verify_ssl,
                                  cert_file=self.cert_file,
                                  key_file=self.key_file,
                                  ca_cert=self.ca_cert_file,
                                  username=self.username)
        self.cursor = self.connection.cursor()

    def _connect(self, server):
        """ connect to the given server, e.g.: \connect localhost:4200 """
        self.last_connected_servers = server
        self._do_connect()
        self._verify_connection(verbose=True)

    def _verify_connection(self, verbose=False):
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

        if verbose:
            cols = ['server_url', 'node_name', 'version', 'connected', 'message']
            self.pprint(results, cols)

        if failed == len(results):
            self.logger.critical('CONNECT ERROR')
        else:
            self.logger.info('CONNECT OK')
            # Execute cluster/node checks only in verbose mode
            if verbose:
                SysInfoCommand.CLUSTER_INFO['information_schema_query'] = \
                get_information_schema_query(self.connection.lowest_server_version)
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
            self.logger.critical(
                'Unknown command. Type \? for a full list of available commands.')
        return False

    def _exec(self, line):
        success = self.execute(line)
        self.exit_code = self.exit_code or int(not success)

    def _execute(self, statement):
        try:
            self.cursor.execute(statement)
            return True
        except ConnectionError as e:
            if self.error_trace:
                self.logger.warn(str(e))
            self.logger.warn(
                'Use \connect <server> to connect to one or more servers first.')
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
        duration = ''
        if cur.duration > -1:
            duration = ' ({0:.3f} sec)'.format(float(cur.duration) / 1000.0)
        print_vars = {
            'command': stmt_type(statement),
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


def stmt_type(statement):
    """
    Extract type of statement, e.g. SELECT, INSERT, UPDATE, DELETE, ...
    """
    return re.findall('[\w]+', statement)[0].upper()


def get_stdin():
    """
    Get data from stdin, if any
    """
    if not sys.stdin.isatty():
        for line in sys.stdin:
            yield line
    return


def host_and_port(host_or_port):
    """
    Return full hostname/IP + port, possible input formats are:
      * host:port  -> host:port
      * :          -> localhost:4200
      * :port      -> localhost:port
      * host       -> host:4200
    """
    if ':' in host_or_port:
        if len(host_or_port) == 1:
            return 'localhost:4200'
        elif host_or_port.startswith(':'):
            return 'localhost' + host_or_port
        return host_or_port
    return host_or_port + ':4200'

def get_information_schema_query(lowest_server_version):
    schema_name = \
        "table_schema" if lowest_server_version >= \
        TABLE_SCHEMA_MIN_VERSION else "schema_name"

    information_schema_query = \
        """ select count(distinct(table_name))
                as number_of_tables
            from information_schema.tables
            where {schema}
            not in ('information_schema', 'sys', 'pg_catalog') """

    return information_schema_query.format(schema=schema_name)

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
    try:
        args = parse_args(parser)
    except Exception as e:
        printer.warn(str(e))
        sys.exit(1)
    output_writer.output_format = args.format

    if args.version:
        printer.info(crash_version)
        sys.exit(0)

    crate_hosts = [host_and_port(h) for h in args.hosts]
    error_trace = args.verbose > 0
    try:
        cmd = _create_cmd(crate_hosts, error_trace, output_writer, is_tty, args)
    except (ProgrammingError, LocationParseError) as e:
        printer.warn(str(e))
        sys.exit(1)

    cmd._verify_connection(verbose=error_trace)
    if not cmd.is_conn_available():
        sys.exit(1)

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
    sys.exit(cmd.exit())

def _create_cmd(crate_hosts, error_trace, output_writer, is_tty, args, timeout=None):
    conn = connect(crate_hosts,
                   verify_ssl_cert=args.verify_ssl,
                   cert_file=args.cert_file,
                   key_file=args.key_file,
                   ca_cert=args.ca_cert_file,
                   username=args.username,
                   timeout=timeout)
    return CrateCmd(connection=conn,
                    error_trace=error_trace,
                    output_writer=output_writer,
                    is_tty=is_tty,
                    autocomplete=args.autocomplete,
                    autocapitalize=args.autocapitalize,
                    verify_ssl=args.verify_ssl,
                    cert_file=args.cert_file,
                    key_file=args.key_file,
                    ca_cert_file=args.ca_cert_file,
                    username=args.username)

def file_with_permissions(path):
    open(path, 'r').close()
    return path

if __name__ == '__main__':
    main()
