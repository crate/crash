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

import functools
import glob

from distutils.version import StrictVersion
from collections import OrderedDict


class Command(object):
    def complete(self, cmd, text):
        return []

    def __call__(self, cmd, *args, **kwargs):
        pass


def noargs_command(func):
    @functools.wraps(func)
    def wrapper(self, cmd, *args, **kwargs):
        if len(args):
            cmd.logger.critical('Command does not take any arguments.')
            return
        return func(self, cmd, *args, **kwargs)
    return wrapper


class HelpCommand(Command):
    """ print this help """

    @noargs_command
    def __call__(self, cmd, *args, **kwargs):
        out = []
        for k, v in sorted(cmd.commands.items()):
            doc = v.__doc__ and v.__doc__.strip()
            out.append('\{0:<30} {1}'.format(k, doc))
        return '\n'.join(out)


class ReadFileCommand(Command):
    """ read and execute statements from a file """

    def complete(self, cmd, text):
        if text.endswith('.sql'):
            return []
        return glob.glob(text + '*.sql')

    def __call__(self, cmd, filename, *args, **kwargs):
        with open(filename, 'rb') as f:
            for line in f:
                cmd.process(line.decode('utf-8'))


class SwitchFormatCommand(Command):
    """ switch output format """

    def complete(self, cmd, text):
        return (i for i in cmd.output_writer.formats if i.startswith(text))

    def __call__(self, cmd, fmt=None):
        if fmt and fmt in cmd.output_writer.formats:
            cmd.output_writer.output_format = fmt
            return u'changed output format to {0}'.format(fmt)
        return u'{0} is not a valid output format.\nUse one of: {1}'.format(
            fmt, ', '.join(cmd.output_writer.formats))


class ToggleAutocompleteCommand(Command):
    """ toggle autocomplete """

    @noargs_command
    def __call__(self, cmd, *args, **kwargs):
        cmd._autocomplete = not cmd._autocomplete
        return 'Autocomplete {0}'.format(
            cmd._autocomplete and 'ON' or 'OFF'
        )


class CheckBaseCommand(Command):

    check_name = None

    def execute(self, cmd, stmt):
        success = cmd._execute(stmt)
        cmd.exit_code = cmd.exit_code or int(not success)
        if not success:
            return False
        cur = cmd.cursor
        assert self.check_name
        print_vars = {
            's': 'S'[cur.rowcount == 1:],
            'rowcount': cur.rowcount,
            'check_name': self.check_name,
        }
        checks = cur.fetchall()
        if len(checks):
            cmd.pprint(checks, [c[0] for c in cur.description])
            tmpl = '{rowcount} {check_name}{s} FAILED'
            cmd.logger.critical(tmpl.format(**print_vars))
        else:
            cmd.logger.info('{} OK'.format(self.check_name))
        return True


class NodeCheckCommand(CheckBaseCommand):
    """ print failed node checks """

    DEFAULT_STMT = """
        SELECT n.name AS "Node Name",
               n.hostname AS "Host Name",
               c.description AS "Failed Check"
        FROM sys.node_checks c, sys.nodes n
        WHERE c.passed = false
          AND c.acknowledged = false
          AND c.node_id = n.id
        ORDER BY c.id, severity asc"""

    STARTUP_STMT = """
        SELECT description as "Failed Check", count(*) as "Number of Nodes"
        FROM sys.node_checks
        WHERE passed = false
          AND acknowledged = false
        GROUP BY description
        ORDER BY description asc"""

    check_name = None

    def __call__(self, cmd, **kwargs):
        if cmd.connection.lowest_server_version >= StrictVersion("0.56.0"):
            startup = kwargs.get('startup', False)
            stmt = startup and self.STARTUP_STMT or self.DEFAULT_STMT
            self.check_name = startup and "TYPES OF NODE CHECK" or "NODE CHECK"

            self.execute(cmd, stmt)
        else:
            tmpl = 'Crate {version} does not support the "\check nodes" command.'
            cmd.logger.warn(tmpl.format(version=cmd.connection.lowest_server_version))


class ClusterCheckCommand(CheckBaseCommand):
    """ print failed cluster checks """

    STMT = """
        SELECT description AS "Failed Check"
        FROM sys.checks
        WHERE passed = false
        ORDER BY id ASC"""

    check_name = "CLUSTER CHECK"

    def __call__(self, cmd, **kwargs):
        if cmd.connection.lowest_server_version >= StrictVersion("0.52.0"):
            self.execute(cmd, self.STMT)
        else:
            tmpl = 'Crate {version} does not support the cluster "check" command.'
            cmd.logger.warn(tmpl.format(version=cmd.connection.lowest_server_version))


class CheckCommand(Command):
    """ print failed cluster and/or node checks, e.g. \check nodes """

    CHECKS = OrderedDict([
                ('cluster', ClusterCheckCommand()),
                ('nodes', NodeCheckCommand())
            ])

    def complete(self, cmd, text):
        return (i for i in self.CHECKS if i.startswith(text))

    def __call__(self, cmd, check_name=None, **kwargs):
        if not check_name:
            [check(cmd, **kwargs) for check in self.CHECKS.values()]
        elif check_name and check_name in self.CHECKS:
            self.CHECKS[check_name](cmd, **kwargs)
        else:
            cmd.logger.warn('No check for {}'.format(check_name))


built_in_commands = {
    '?': HelpCommand(),
    'r': ReadFileCommand(),
    'format': SwitchFormatCommand(),
    'autocomplete': ToggleAutocompleteCommand(),
    'check': CheckCommand(),
}
