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
from argparse import ArgumentParser, ArgumentTypeError
from collections import namedtuple
from getpass import getpass
from operator import itemgetter

import sqlparse
import urllib3
from platformdirs import user_config_dir, user_data_dir
from urllib3.exceptions import LocationParseError
from verlib2 import Version

from crate.client import connect
from crate.client.exceptions import ConnectionError, ProgrammingError

from ..crash import __version__ as crash_version
from .commands import Command, built_in_commands
from .config import Configuration, ConfigurationError
from .outputs import OutputWriter
from .printer import ColorPrinter, PrintWrapper
from .sysinfo import SysInfoCommand

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
logging.getLogger('crate').addHandler(logging.NullHandler())

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

ConnectionMeta = namedtuple('ConnectionMeta', ['user', 'schema', 'cluster'])

TABLE_SCHEMA_MIN_VERSION = Version("0.57.0")
TABLE_TYPE_MIN_VERSION = Version("2.0.0")


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


def boolean(v):
    v = str(v).lower()
    if v in ("yes", "true", "t", "1"):
        return True
    elif v in ("no", "false", "f", "0"):
        return False
    else:
        raise ArgumentTypeError(
            'Invalid choice `{v}`, expected one of: [yes, true, t, 1, no, false, f, 0]'.format(v=v))


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
    parser.add_argument('--timeout', type=str, metavar='TIMEOUT',
                        help='Configure network timeout in "<connect_sec>" or "<connect_sec>,<read_sec>" format. '
                             'Defaults to "5,-1" where "-1" means infinite timeout.', default="5")
    parser.add_argument(
        '--verify-ssl',
        choices=(True, False),
        type=boolean,
        default=True,
        help='Enable or disable the verification of the server SSL certificate'
    )
    parser.add_argument('--cert-file', type=file_with_permissions, metavar='FILENAME',
                        help='use FILENAME as the client certificate file')
    parser.add_argument('--key-file', type=file_with_permissions, metavar='FILENAME',
                        help='Use FILENAME as the client certificate key file')
    parser.add_argument('--ca-cert-file', type=file_with_permissions, metavar='FILENAME',
                        help='use FILENAME as the CA certificate file')
    parser.add_argument('--format', type=str,
                        default=_conf_or_default('format', 'tabular'),
                        choices=output_formats, metavar='FORMAT',
                        help=f'the output FORMAT of the SQL response.\n'
                             f'choose one of: {", ".join(output_formats)}')
    parser.add_argument('--version', action='store_true', default=False,
                        help='print the Crash version and exit')

    try:
        import argcomplete
        argcomplete.autocomplete(parser)
    except ImportError:
        pass
    return parser


def noargs_command(fn):
    def inner_fn(self, *args):
        if len(args):
            self.logger.critical("Command does not take any arguments.")
            return
        return fn(self, *args)
    inner_fn.__doc__ = fn.__doc__
    return inner_fn


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
            'c': self._connect_and_print_result,
            'connect': self._connect_and_print_result,
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
        self._connect(crate_hosts)

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

    def process_iterable(self, iterable):
        self._process_lines([line for text in iterable for line in text.split('\n')])

    def process(self, text):
        self._process_lines(text.split('\n'))

    def _process_lines(self, lines):
        sql_lines = []
        for line in lines:
            line = line.strip()
            if line.startswith('\\'):
                self._process_sql('\n'.join(sql_lines))
                self._try_exec_cmd(line.lstrip('\\'))
                sql_lines = []
            else:
                sql_lines.append(line)
        self._process_sql('\n'.join(sql_lines))

    def _process_sql(self, text):
        sql = sqlparse.format(text, strip_comments=False)
        for statement in sqlparse.split(sql):
            self._exec_and_print(statement)

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

        self._exec_and_print(
            "SELECT format('%s.%s', {schema}, table_name) AS name "
            "FROM information_schema.tables "
            "WHERE {schema} NOT IN ('sys','information_schema', 'pg_catalog')"
            "{table_filter} "
            "ORDER BY 1".format(schema=schema_name, table_filter=table_filter))

    @noargs_command
    def _quit(self, *args):
        """ quit crash """
        self.logger.warn('Bye!')
        sys.exit(self.exit())

    def is_conn_available(self):
        return self.connection and \
            self.connection.lowest_server_version != Version("0.0.0")

    def _connect(self, servers):
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
                                  timeout=self.timeout,
                                  socket_keepalive=True,
                                  socket_tcp_keepidle=120,
                                  socket_tcp_keepintvl=30,
                                  socket_tcp_keepcnt=8)
        self.cursor = self.connection.cursor()
        self._fetch_session_info()

    def _connect_and_print_result(self, servers):
        """ connect to the given server, e.g.: \\connect localhost:4200 """
        self._connect(servers.split(' '))
        self._print_connect_result(verbose=True)

    def reconnect(self):
        """Connect with same configuration and to last connected servers."""
        self._connect(self.last_connected_servers)

    def _get_server_information(self):
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
        return results, failed

    def _print_connect_result(self, verbose=False):
        results, failed = self._get_server_information()
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
                and self.connection.lowest_server_version >= Version("2.0"):

            try:
                self.cursor.execute('SELECT current_user, current_schema, name FROM sys.cluster')
            except ProgrammingError as e:
                message = str(e)
                if "UnsupportedFeatureException" in message:
                    # `current_user` is only available in the enterprise edition
                    self.cursor.execute('SELECT NULL, current_schema, name FROM sys.cluster')
                elif "SchemaUnknownException" in message:
                    # `name FROM sys.cluster` may faild due to insufficient permissions
                    self.cursor.execute('SELECT current_user, current_schema, NULL')
                else:
                    self.logger.warn("Could not load cluster information: " + message)
                    self.connect_info = ConnectionMeta(None, None, None)
                    return

            self.connect_info = ConnectionMeta(*self.cursor.fetchone())
        else:
            self.connect_info = ConnectionMeta(None, None, None)

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

    def _exec(self, statement: str) -> bool:
        """Execute the statement, prints errors if any occurr but no results."""
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

    def _exec_and_print(self, statement: str) -> bool:
        """Execute the statement and print the output."""
        success = self._exec(statement)
        self.exit_code = self.exit_code or int(not success)
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
            tmpl = '{command} OK, {rowcount} row{s} affected{duration}'
        self.logger.info(tmpl.format(**print_vars))
        return True


def stmt_type(statement):
    """Extract type of statement, e.g. SELECT, INSERT, UPDATE, DELETE, ..."""
    return re.findall(r'[\w]+', statement)[0].upper()


def get_lines_from_stdin():
    """
    Get data line by line from stdin, if any
    """
    if sys.stdin.isatty():
        return

    for line in sys.stdin:
        yield line


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


def _load_conf(printer, formats) -> Configuration:
    config = parse_config_path()
    try:
        return Configuration(config)
    except ConfigurationError as e:
        printer.warn(str(e))
        parser = get_parser(formats)
        parser.print_usage()
        sys.exit(1)


def _resolve_password(is_tty, force_passwd_prompt):
    if force_passwd_prompt and is_tty:
        return getpass()
    elif not force_passwd_prompt:
        return os.environ.get('CRATEPW', None)


def main():
    is_tty = sys.stdout.isatty()
    printer = ColorPrinter(is_tty)
    output_writer = OutputWriter(PrintWrapper(), is_tty)

    conf = _load_conf(printer, output_writer.formats)
    parser = get_parser(output_writer.formats, conf=conf)
    try:
        args = parser.parse_args()
    except Exception as e:
        printer.warn(str(e))
        sys.exit(1)
    output_writer.output_format = args.format

    if args.version:
        printer.info(crash_version)
        sys.exit(0)

    crate_hosts = [host_and_port(h) for h in args.hosts]
    error_trace = args.verbose > 0

    password = _resolve_password(is_tty, args.force_passwd_prompt)

    # Tries to create a connection to the server.
    # Prompts for the password automatically if the server only accepts
    # password authentication.
    cmd = None
    try:
        cmd = _create_shell(crate_hosts, error_trace, output_writer, is_tty,
                            args, password=password)
    except (ProgrammingError, LocationParseError) as e:
        msg = getattr(e, 'message', str(e))
        if '401' in msg and not args.force_passwd_prompt and is_tty:
            password = getpass()
            try:
                cmd = _create_shell(crate_hosts, error_trace, output_writer,
                                    is_tty, args, password=password)
            except (ProgrammingError, LocationParseError) as ex:
                printer.warn(str(ex))
                sys.exit(1)
        else:
            printer.warn(str(e))
            sys.exit(1)
    except Exception as e:
        printer.warn(str(e))
        sys.exit(1)

    cmd._print_connect_result(verbose=error_trace)
    if not cmd.is_conn_available():
        sys.exit(1)

    def save_and_exit():
        conf.save()
        sys.exit(cmd.exit())

    if args.sysinfo:
        cmd.output_writer.output_format = 'mixed'
        cmd.sys_info_cmd.execute()
        save_and_exit()

    if args.command:
        cmd.process(args.command)
        save_and_exit()

    if not sys.stdin.isatty():
        cmd.process_iterable(get_lines_from_stdin())
        save_and_exit()

    from .repl import loop
    loop(cmd, args.history)
    save_and_exit()


INFINITE_TIMEOUT = -1
INFINITE_TIMEOUTS = [None, INFINITE_TIMEOUT, str(INFINITE_TIMEOUT)]


def _decode_timeout(value):
    """
    Decode single timeout value, respecting the `INFINITE_TIMEOUT` surrogate.
    """
    if value in INFINITE_TIMEOUTS:
        return None
    else:
        return float(value)


def _decode_timeouts(timeout):
    """
    Decode connect/read timeout values from tuple or string.

    Variant 1: (connect, read)
    Variant 2: connect,read
    """

    if timeout is None:
        timeouts = (INFINITE_TIMEOUT, INFINITE_TIMEOUT)
    elif isinstance(timeout, (int, float)):
        timeouts = (timeout, INFINITE_TIMEOUT)
    elif isinstance(timeout, str):
        timeouts = timeout.split(",")
    elif isinstance(timeout, (list, tuple)):
        timeouts = timeout
    else:
        raise TypeError(f"Cannot decode timeout value from type `{type(timeout)}`, "
                        f"expected format `<connect_sec>,<read_sec>`")

    if len(timeouts) == 1:
        connect_timeout, read_timeout = timeouts[0], INFINITE_TIMEOUT
    elif len(timeouts) == 2:
        connect_timeout, read_timeout = timeouts[0], timeouts[1]
    else:
        raise ValueError(f"Cannot decode timeout `{timeout}`, "
                         f"expected format `<connect_sec>,<read_sec>`")

    return urllib3.Timeout(connect=_decode_timeout(connect_timeout), read=_decode_timeout(read_timeout))


def _create_shell(crate_hosts, error_trace, output_writer, is_tty, args,
                  timeout=None, password=None):

    # Explicit "timeout" function argument takes precedence.
    if timeout is not None:
        timeout = _decode_timeouts(timeout)

    # Probe `--timeout`` command line argument second.
    elif args.timeout is not None:
        timeout = _decode_timeouts(args.timeout)

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
    f = open(path, 'r')
    f.close()
    return path


if __name__ == '__main__':
    main()
