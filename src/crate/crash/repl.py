# vim: set fileencodings=utf-8
# -*- coding: utf-8; -*-
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

import os

from pygments.lexers.sql import SqlLexer
from pygments.style import Style
from pygments.token import (Keyword,
                            Comment,
                            Operator,
                            Number,
                            Literal,
                            String,
                            Error)

from prompt_toolkit.completion import Completer, Completion
from prompt_toolkit.history import FileHistory
from prompt_toolkit.buffer import Buffer
from prompt_toolkit.filters import Condition, IsDone, HasFocus
from prompt_toolkit import CommandLineInterface, AbortAction, Application
from prompt_toolkit.interface import AcceptAction
from prompt_toolkit.styles import PygmentsStyle
from prompt_toolkit.enums import DEFAULT_BUFFER, EditingMode
from prompt_toolkit.layout.processors import (
    HighlightMatchingBracketProcessor,
    ConditionalProcessor
)
from prompt_toolkit.key_binding.manager import KeyBindingManager
from prompt_toolkit.shortcuts import (create_prompt_layout,
                                      create_output,
                                      create_eventloop)

from .commands import Command


MAX_HISTORY_LENGTH = 10000


def _get_editing_mode():
    files = ['/etc/inputrc', os.path.expanduser('~/.inputrc')]
    for filepath in files:
        try:
            with open(filepath, 'r') as f:
                for line in f:
                    if line.strip() == 'set editing-mode vi':
                        return EditingMode.VI
        except IOError:
            continue
    return EditingMode.EMACS


class CrateStyle(Style):
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
        self.strings = self.strings[:max(0, self.max_length - 1)]
        super(TruncatedFileHistory, self).append(string)


class SQLCompleter(Completer):
    keywords = [
        "select", "from", "to", "as", "all", "any", "some",
        "directory", "distinct", "where", "group", "by", "order", "having",
        "limit", "offset", "or", "and", "in", "not", "exists", "between",
        "like", "is", "null", "true", "false", "nulls", "first", "last",
        "escape", "asc", "desc", "substring", "for", "date", "time",
        "year", "month", "day", "hour", "minute", "second", "current_date",
        "current_time", "current_timestamp", "extract", "case", "when",
        "join", "cross", "outer", "inner", "left", "right", "full",
        "natural", "using", "on", "over", "partition", "range", "rows",
        "unbounded", "preceding", "row", "with", "create",
        "blob", "table", "repository", "snapshot", "alter", "kill",
        "add", "column", "boolean", "byte", "short", "integer", "int",
        "long", "float", "double", "timestamp", "ip", "object", "string",
        "geo_point", "geo_shape", "global", "constraint", "describe", "explain",
        "format", "type", "text", "distributed", "cast", "try_cast", "show",
        "tables", "schemas", "catalogs", "columns", "partitions", "functions",
        "view", "refresh", "restore", "drop", "alias", "union",
        "except", "intersect", "system", "insert", "into", "values",
        "delete", "update", "key", "duplicate", "set", "reset", "copy",
        "clustered", "shards", "primary key", "off", "fulltext", "plain",
        "index", "dynamic", "strict", "ignored", "array", "analyzer", "extends",
        "tokenizer", "token_filters", "char_filters", "partitioned", "transient",
        "persistent", "match", "generated", "always"
    ]

    def __init__(self, cmd):
        self.cmd = cmd
        self.keywords += [kw.upper() for kw in self.keywords]

    def get_command_completions(self, line):
        if ' ' not in line:
            cmd = line[1:]
            return (i for i in self.cmd.commands.keys() if i.startswith(cmd))
        parts = line.split(' ', 1)
        cmd = parts[0].lstrip('\\')
        cmd = self.cmd.commands.get(cmd, None)
        if isinstance(cmd, Command):
            return cmd.complete(self.cmd, parts[1])
        return []

    def get_completions(self, document, complete_event):
        if not self.cmd.should_autocomplete():
            return
        line = document.text
        word_before_cursor = document.get_word_before_cursor()
        if line.startswith('\\'):
            for w in self.get_command_completions(line):
                yield Completion(w, -len(word_before_cursor))
            return
        for keyword in self.keywords:
            if keyword.startswith(word_before_cursor):
                yield Completion(keyword, -len(word_before_cursor))


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
    key_binding_manager = KeyBindingManager(
        enable_search=True,
        enable_abort_and_exit_bindings=True
    )
    layout = create_prompt_layout(
        message=u'cr> ',
        multiline=True,
        lexer=SqlLexer,
        extra_input_processors=[
            ConditionalProcessor(
                processor=HighlightMatchingBracketProcessor(chars='[](){}'),
                filter=HasFocus(DEFAULT_BUFFER) & ~IsDone())
        ]
    )
    buffer = CrashBuffer(
        history=TruncatedFileHistory(history_file, max_length=MAX_HISTORY_LENGTH),
        accept_action=AcceptAction.RETURN_DOCUMENT,
        completer=SQLCompleter(cmd)
    )
    buffer.complete_while_typing = lambda cli=None: cmd.should_autocomplete()
    application = Application(
        layout=layout,
        buffer=buffer,
        style=PygmentsStyle.from_defaults(pygments_style_cls=CrateStyle),
        key_bindings_registry=key_binding_manager.registry,
        editing_mode=_get_editing_mode(),
        on_exit=AbortAction.RAISE_EXCEPTION,
        on_abort=AbortAction.RETRY,
    )
    eventloop = create_eventloop()
    output = create_output()
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
            doc = cli.run(reset_current_buffer=True)
            if doc:
                cmd.process(doc.text)
        except KeyboardInterrupt:
            cmd.logger.warn("Query not cancelled. Run KILL <jobId> to cancel it")
        except EOFError:
            cmd.logger.warn(u'Bye!')
            return
