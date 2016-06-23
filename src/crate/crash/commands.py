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


built_in_commands = {
    '?': HelpCommand(),
    'r': ReadFileCommand(),
    'format': SwitchFormatCommand(),
    'autocomplete': ToggleAutocompleteCommand(),
}
