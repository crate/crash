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
from getpass import getpass
from appdirs import user_data_dir, user_config_dir
from argparse import ArgumentParser
from collections import namedtuple
from crate.client import connect
from crate.client.exceptions import ConnectionError, ProgrammingError
from distutils.version import StrictVersion
from urllib3.exceptions import LocationParseError
from operator import itemgetter

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

ConnectionMeta = namedtuple('ConnectionMeta', ['user', 'schema'])

TABLE_SCHEMA_MIN_VERSION = StrictVersion("0.57.0")
TABLE_TYPE_MIN_VERSION = StrictVersion("2.0.0")


def parse_config_path(args=sys.argv):
    """
    Preprocess sys.argv and extract --config argument.
    """

    config = CONFIG_PATH
    if '--config' in args:
        idx = args.index('--config')
        if len(args) > idx + 1:
            config = args.pop(idx + 1)
        args.pop(idx)
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
                        help='print debug information to STDOUT')
    parser.add_argument('-A', '--no-autocomplete', action='store_false',
                        dest='autocomplete',
                        default=_conf_or_default('autocomplete', True),
                        help='disable SQL keywords autocompletion')
    parser.add_argument('-a', '--autocapitalize', action='store_true',
                        dest='autocapitalize',
                        default=False,
                        help='enable automatic capitalization of SQL keywords while typing')
    parser.add_argument('-U', '--username', type=str, metavar='USERNAME',
                        help='Authenticate as USERNAME.')
    parser.add_argument('-W', '--password', action='store_true',
                        dest='force_passwd_prompt', default=_conf_or_default('force_passwd_prompt', False),
                        help='force a password prompt')
    parser.add_argument('--schema', type=str,
                        help='default schema for statements if schema is not explicitly stated in queries')
    parser.add_argument('--history', type=str, metavar='FILENAME',
                        help='Use FILENAME as a history file', default=HISTORY_PATH)
    parser.add_argument('--config', type=str, metavar='FILENAME',
                        help='use FILENAME as a configuration file', default=CONFIG_PATH)

    group = parser.add_mutually_exclusive_group()
    group.add_argument('-c', '--command', type=str, metavar='STATEMENT',
                       help='Execute the STATEMENT and exit.')
    group.add_argument('--sysinfo', action='store_true', default=False,
                       help='print system and cluster information')

    parser.add_argument('--hosts', type=str, nargs='*',
                        default=_conf_or_default('hosts', ['localhost:4200']),
                        help='connect to HOSTS.', metavar='HOSTS')
    parser.add_argument('--verify-ssl', type=boolean, default=True,
                        help='force the verification of the server SSL certificate')
    parser.add_argument('--cert-file', type=file_with_permissions, metavar='FILENAME',
                        help='use FILENAME as the client certificate file')
    parser.add_argument('--key-file', type=file_with_permissions, metavar='FILENAME',
                        help='Use FILENAME as the client certificate key file')
    parser.add_argument('--ca-cert-file', type=file_with_permissions, metavar='FILENAME',
                        help='use FILENAME as the CA certificate file')
    parser.add_argument('--format', type=str,
                        default=_conf_or_default('format', 'tabular'),
                        choices=output_formats, metavar='FORMAT',
                        help='the output FORMAT of the SQL response')
    parser.add_argument('--version', action='store_true', default=False,
                        help='print the Crash version and exit')

    return parser


def noargs_command(fn):
    def inner_fn(self, *args):
        if len(args):
            self.logger.critical("Command does not take any arguments.")
            return
        return fn(self, *args)
    inner_fn.__doc__ = fn.__doc__
    return inner_fn


def _parse_statements(lines):
    """Return a generator of statements

    Args: A list of strings that can contain one or more statements.
          Statements are separated using ';' at the end of a line
          Everything after the last ';' will be treated as the last statement.

    >>> list(_parse_statements(['select * from ', 't1;', 'select name']))
    ['select * from\\nt1', 'select name']

    >>> list(_parse_statements(['select * from t1;', '  ']))
    ['select * from t1']
    """
    lines = (l.strip() for l in lines if l)
    lines = (l for l in lines if l and not l.startswith('--'))
    parts = []
    for line in lines:
        parts.append(line.rstrip(';'))
        if line.endswith(';'):
            yield '\n'.join(parts)
            parts[:] = []
    if parts:
        yield '\n'.join(parts)


class CrateShell:

    def __init__(self,
                 crate_hosts=['localhost:4200'],
                 output_writer=None,
                 error_trace=False,
                 is_tty=True,
                 autocomplete=True,
                 autocapitalize=True,
                 verify_ssl=True,
                 cert_file=None,
                 key_file=None,
                 ca_cert_file=None,
                 username=None,
                 password=None,
                 schema=None,
                 timeout=None):
        self.last_connected_servers = []

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

        self.output_writer = output_writer or OutputWriter(PrintWrapper(), is_tty)
        self.error_trace = error_trace
        self._autocomplete = autocomplete
        self._autocapitalize = autocapitalize
        self.verify_ssl = verify_ssl
        self.cert_file = cert_file
        self.key_file = key_file
        self.ca_cert_file = ca_cert_file
        self.username = username
        self.password = password
        self.schema = schema
        self.timeout = timeout

        # establish connection
        self.cursor = None
        self.connection = None
        self._do_connect(crate_hosts)

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_value, traceback):
        self.exit()

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

    def process_iterable(self, stdin):
        any_statement = False
        for statement in _parse_statements(stdin):
            self._exec(statement)
            any_statement = True
        return any_statement

    def process(self, text):
        if text.startswith('\\'):
            self._try_exec_cmd(text.lstrip('\\'))
        else:
            for statement in _parse_statements([text]):
                self._exec(statement)

    def exit(self):
        self.close()
        return self.exit_code

    def close(self):
        if self.is_closed():
            raise ProgrammingError('CrateShell is already closed')
        if self.cursor:
            self.cursor.close()
        self.cursor = None
        if self.connection:
            self.connection.close()
        self.connection = None

    def is_closed(self):
        return not (self.cursor and self.connection)

    @noargs_command
    def _show_tables(self, *args):
        """ print the existing tables within the 'doc' schema """
        v = self.connection.lowest_server_version
        schema_name = \
            "table_schema" if v >= TABLE_SCHEMA_MIN_VERSION else "schema_name"
        table_filter = \
            " AND table_type = 'BASE TABLE'" if v >= TABLE_TYPE_MIN_VERSION else ""

        self._exec("SELECT format('%s.%s', {schema}, table_name) AS name "
                   "FROM information_schema.tables "
                   "WHERE {schema} NOT IN ('sys','information_schema', 'pg_catalog')"
                   "{table_filter}"
                   .format(schema=schema_name, table_filter=table_filter))

    @noargs_command
    def _quit(self, *args):
        """ quit crash """
        self.logger.warn('Bye!')
        sys.exit(self.exit())

    def is_conn_available(self):
        return self.connection and \
            self.connection.lowest_server_version != StrictVersion("0.0.0")

    def _do_connect(self, servers):
        self.last_connected_servers = servers
        if self.cursor or self.connection:
            self.close()  # reset open cursor and connection
        self.connection = connect(servers,
                                  error_trace=self.error_trace,
                                  verify_ssl_cert=self.verify_ssl,
                                  cert_file=self.cert_file,
                                  key_file=self.key_file,
                                  ca_cert=self.ca_cert_file,
                                  username=self.username,
                                  password=self.password,
                                  schema=self.schema,
                                  timeout=self.timeout)
        self.cursor = self.connection.cursor()
        self._fetch_session_info()

    def _connect(self, servers):
        """ connect to the given server, e.g.: \\connect localhost:4200 """
        self._do_connect(servers.split(' '))
        self._verify_connection(verbose=True)

    def reconnect(self):
        """Connect with same configuration and to last connected servers"""
        self._do_connect(self.last_connected_servers)

    def _verify_connection(self, verbose=False):
        results = []
        failed = 0
        client = self.connection.client
        for server in client.server_pool.keys():
            try:
                infos = client.server_infos(server)
            except ConnectionError as e:
                failed += 1
                results.append([server, None, '0.0.0', False, e.message])
            else:
                results.append(infos + (True, 'OK', ))

        # sort by CONNECTED DESC, SERVER_URL
        results.sort(key=itemgetter(3), reverse=True)
        results.sort(key=itemgetter(0))

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

    def _fetch_session_info(self):
        if self.is_conn_available() \
                and self.connection.lowest_server_version >= StrictVersion("2.0"):
            user, schema = self._user_and_schema()
            self.connect_info = ConnectionMeta(user, schema)
        else:
            self.connect_info = ConnectionMeta(None, None)

    def _user_and_schema(self):
        try:
            # CURRENT_USER function is only available in Enterprise Edition.
            self.cursor.execute("""
                SELECT
                current_user AS "user",
                current_schema AS "schema";
            """)
        except ProgrammingError:
            self.cursor.execute("""
                SELECT
                NULL AS "user",
                current_schema AS "schema";
            """)
        return self.cursor.fetchone()

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
            except ProgrammingError as e:
                # repl needs to handle 401 authorization errors
                raise e
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
                'Unknown command. Type \\? for a full list of available commands.')
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
                'Use \\connect <server> to connect to one or more servers first.')
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
    return re.findall(r'[\w]+', statement)[0].upper()


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

    force_passwd_prompt = args.force_passwd_prompt
    password = None

    # If password prompt is not forced try to get it from env. variable.
    if not force_passwd_prompt:
        password = os.environ.get('CRATEPW', None)

    # Prompt for password immediately to avoid that the first time trying to
    # connect to the server runs into an `Unauthorized` excpetion
    # is_tty = False
    if force_passwd_prompt and not password and is_tty:
        password = getpass()

    # Tries to create a connection to the server.
    # Prompts for the password automatically if the server only accepts
    # password authentication.
    cmd = None
    try:
        cmd = _create_shell(crate_hosts, error_trace, output_writer, is_tty,
                            args, password=password)
    except (ProgrammingError, LocationParseError) as e:
        if '401' in e.message and not force_passwd_prompt:
            if is_tty:
                password = getpass()
            try:
                cmd = _create_shell(crate_hosts, error_trace, output_writer,
                                    is_tty, args, password=password)
            except (ProgrammingError, LocationParseError) as ex:
                printer.warn(str(ex))
                sys.exit(1)
        else:
            raise e
    except Exception as e:
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
        if cmd.process_iterable(stdin_data):
            done = True
    if not done:
        from .repl import loop
        loop(cmd, args.history)
    conf.save()
    sys.exit(cmd.exit())


def _create_shell(crate_hosts, error_trace, output_writer, is_tty, args,
                  timeout=None, password=None):
    return CrateShell(crate_hosts,
                      error_trace=error_trace,
                      output_writer=output_writer,
                      is_tty=is_tty,
                      autocomplete=args.autocomplete,
                      autocapitalize=args.autocapitalize,
                      verify_ssl=args.verify_ssl,
                      cert_file=args.cert_file,
                      key_file=args.key_file,
                      ca_cert_file=args.ca_cert_file,
                      username=args.username,
                      password=password,
                      schema=args.schema,
                      timeout=timeout)


def file_with_permissions(path):
    open(path, 'r').close()
    return path


if __name__ == '__main__':
    main()
