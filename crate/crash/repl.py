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
import re
from getpass import getpass

from prompt_toolkit import Application
from prompt_toolkit.application import get_app
from prompt_toolkit.buffer import Buffer
from prompt_toolkit.completion import Completer, Completion
from prompt_toolkit.enums import DEFAULT_BUFFER, EditingMode
from prompt_toolkit.filters import Condition, HasFocus, IsDone
from prompt_toolkit.formatted_text import PygmentsTokens
from prompt_toolkit.history import FileHistory
from prompt_toolkit.key_binding import KeyBindings, merge_key_bindings
from prompt_toolkit.key_binding.bindings.open_in_editor import (
    load_open_in_editor_bindings,
)
from prompt_toolkit.layout.controls import SearchBufferControl
from prompt_toolkit.layout.processors import (
    ConditionalProcessor,
    HighlightMatchingBracketProcessor,
)
from prompt_toolkit.output.defaults import get_default_output
from prompt_toolkit.styles.pygments import style_from_pygments_cls
from pygments.lexers.sql import PostgresLexer
from pygments.style import Style
from pygments.token import (
    Comment,
    Error,
    Keyword,
    Name,
    Number,
    Operator,
    String,
    Token,
)

from crate.client.exceptions import ConnectionError, ProgrammingError

from .commands import Command
from .keybinding import bind_keys
from .layout import create_layout

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
    default_style = ""
    styles = {
        Keyword: 'bold ansibrightblue',
        Comment: 'ansigray',
        Operator: 'ansibrightred',
        Name.Builtin: 'ansiblue',
        Number: 'ansimagenta',
        String: 'ansiyellow',
        String.Single: 'ansibrightgreen',
        Error: 'bold ansired',
        Token.Toolbar.Status.Key: 'ansiblue',
    }


class TruncatedFileHistory(FileHistory):

    def __init__(self, filename, max_length=1000):
        super().__init__(filename)
        base = os.path.dirname(filename)
        if not os.path.exists(base):
            os.makedirs(base)
        if not os.path.exists(filename):
            with open(filename, 'a'):
                os.utime(filename, None)
        self.max_length = max_length

    def append(self, string):
        self.strings = self.strings[:max(0, self.max_length - 1)]
        super().append(string)


class SQLCompleter(Completer):

    fallback_keywords = [
        "add", "alias", "all", "allocate", "alter", "always", "analyze",
        "analyzer", "and", "any", "array", "artifacts", "as", "asc", "at",
        "begin", "bernoulli", "between", "blob", "boolean", "both", "by",
        "byte", "called", "cancel", "case", "cast", "catalogs", "char_filters",
        "characteristics", "close", "cluster", "clustered", "column", "columns",
        "commit", "committed", "conflict", "constraint", "copy", "create",
        "cross", "current", "current_date", "current_schema", "current_time",
        "current_timestamp", "current_user", "dangling", "day", "deallocate",
        "decommission", "default", "deferrable", "delete", "deny", "desc",
        "describe", "directory", "distinct", "distributed", "do", "double",
        "drop", "duplicate", "dynamic", "else", "end", "escape", "except",
        "exists", "explain", "extends", "extract", "failed", "false", "filter",
        "first", "float", "following", "for", "format", "from", "full",
        "fulltext", "function", "functions", "gc", "generated", "geo_point",
        "geo_shape", "global", "grant", "graphviz", "group", "having", "hour",
        "if", "ignored", "ilike", "in", "index", "inner", "input", "insert",
        "int", "integer", "intersect", "interval", "into", "ip", "is",
        "isolation", "join", "key", "kill", "language", "last", "leading",
        "left", "level", "license", "like", "limit", "local", "logical",
        "long", "match", "materialized", "minute", "month", "move", "natural",
        "not", "nothing", "null", "nulls", "object", "off", "offset", "on",
        "only", "open", "optimize", "or", "order", "outer", "over", "partition",
        "partitioned", "partitions", "persistent", "plain", "preceding", "precision",
        "prepare", "privileges", "promote", "range", "read", "recursive", "refresh",
        "rename", "repeatable", "replace", "replica", "repository", "reroute",
        "reset", "restore", "retry", "return", "returns", "revoke", "right",
        "row", "rows", "schema", "schemas", "second", "select", "serializable",
        "session", "session_user", "set", "shard", "shards", "short", "show",
        "snapshot", "some", "storage", "stratify", "strict", "string",
        "substring", "summary", "swap", "system", "table", "tables",
        "tablesample", "text", "then", "time", "timestamp", "to",
        "token_filters", "tokenizer", "trailing", "transaction",
        "transaction_isolation", "transient", "trim", "true", "try_cast",
        "type", "unbounded", "uncommitted", "union", "update", "user", "using",
        "values", "view", "when", "where", "window", "with", "without", "work",
        "write", "year", "zone"]

    def __init__(self, cmd):
        self.cmd = cmd
        self.keywords = self._populate_keywords()

    def _populate_keywords(self):
        try:
            self.cmd.cursor.execute("SELECT word FROM pg_catalog.pg_get_keywords()")
            return [i[0] for i in self.cmd.cursor.fetchall()]
        except (ProgrammingError, ConnectionError):
            return self.fallback_keywords

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
        # start autocomplete on 3rd character for non-command keys
        if len(word_before_cursor) >= 3:
            for keyword in self.keywords:
                if keyword.startswith(word_before_cursor.lower()):
                    yield Completion(keyword.upper(), -len(word_before_cursor))


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

        super().__init__(*args, multiline=is_multiline, **kwargs)


class Capitalizer:

    KEYWORD_RE = r'(?:"\w+)|(?:\'\w+)|\w+'

    def __init__(self, cmd, completer):
        self.cmd = cmd
        self.last_changed = None
        self.completer = completer

    def apply_capitalization(self, buffer):
        if not self.cmd.should_autocapitalize():
            return

        current_line = buffer.document.text

        if current_line.startswith('\\'):
            return

        cursor_position = buffer.document.cursor_position

        if self.last_changed and self.is_prefix(current_line[:cursor_position].lower(), self.last_changed.lower()):
            diff = len(self.last_changed) - len(current_line)
            current_line = self.last_changed + current_line[diff:]

        new_line = re.sub(self.KEYWORD_RE, self.keyword_replacer, current_line[:cursor_position])

        if new_line != buffer.document.text:
            buffer.delete_before_cursor(cursor_position)
            buffer.delete(len(new_line) - cursor_position)
            buffer.insert_text(new_line, overwrite=False, move_cursor=True, fire_event=False)
            self.last_changed = current_line[:cursor_position]

    def keyword_replacer(self, match):
        if match.group(0).lower() in self.completer.keywords:
            return match.group(0).upper()
        else:
            return match.group(0)

    def is_prefix(self, string, prefix):
        return string.startswith(prefix) and string != prefix


def create_buffer(cmd, history_file):
    def accept(buff):
        get_app().exit(result=buff.document.text)
        return True

    history = TruncatedFileHistory(history_file, max_length=MAX_HISTORY_LENGTH)
    completer = SQLCompleter(cmd)
    buffer = CrashBuffer(
        name=DEFAULT_BUFFER,
        history=history,
        completer=completer,
        enable_history_search=True,
        accept_handler=accept,
        on_text_insert=Capitalizer(cmd, completer).apply_capitalization,
        tempfile_suffix=lambda: '.sql'
    )
    buffer.complete_while_typing = lambda cli=None: cmd.should_autocomplete()
    return buffer


def get_toolbar_tokens(cmd):
    return _get_toolbar_tokens(cmd.is_conn_available(),
                               cmd.connection.client.active_servers,
                               cmd.connect_info)


def _get_toolbar_tokens(is_connected, servers, info):
    if is_connected:
        hosts = ', '.join(re.sub(r'^https?:\/\/', '', a) for a in servers)
        return PygmentsTokens([
            (Token.Toolbar.Status.Key, 'USER: '),
            (Token.Toolbar.Status, info.user or '--'),
            (Token.Toolbar.Status, ' | '),
            (Token.Toolbar.Status.Key, 'SCHEMA: '),
            (Token.Toolbar.Status, info.schema or 'doc'),
            (Token.Toolbar.Status, ' | '),
            (Token.Toolbar.Status.Key, 'CLUSTER: '),
            (Token.Toolbar.Status, info.cluster or '--'),
            (Token.Toolbar.Status, ' | '),
            (Token.Toolbar.Status.Key, 'HOSTS: '),
            (Token.Toolbar.Status, hosts)
        ])
    else:
        return PygmentsTokens([(Token.Toolbar.Status, 'not connected')])


def loop(cmd, history_file):
    buf = create_buffer(cmd, history_file)
    key_bindings = KeyBindings()
    bind_keys(buf, key_bindings)
    layout = create_layout(
        buffer=buf,
        multiline=True,
        lexer=PostgresLexer,
        extra_input_processors=[
            ConditionalProcessor(
                processor=HighlightMatchingBracketProcessor(chars='[](){}'),
                filter=HasFocus(DEFAULT_BUFFER) & ~IsDone())
        ],
        get_bottom_toolbar_tokens=lambda: get_toolbar_tokens(cmd),
        get_prompt_tokens=lambda: [('class:prompt', 'cr> ')]
    )
    output = get_default_output()
    app = Application(
        layout=layout,
        style=style_from_pygments_cls(CrateStyle),
        key_bindings=merge_key_bindings([
            key_bindings,
            load_open_in_editor_bindings()
        ]),
        editing_mode=_get_editing_mode(),
        output=output
    )
    cmd.get_num_columns = lambda: output.get_size().columns

    while True:
        try:
            text = app.run()
            if text:
                cmd.process(text)
            buf.reset()
        except ProgrammingError as e:
            if '401' in e.message:
                username = cmd.username
                password = cmd.password
                cmd.username = input('Username: ')
                cmd.password = getpass()
                try:
                    cmd.process(text)
                except ProgrammingError as ex:
                    # fallback to existing user/pw
                    cmd.username = username
                    cmd.password = password
                    cmd.logger.warn(str(ex))
            else:
                cmd.logger.warn(str(e))
        except KeyboardInterrupt:
            if isinstance(app.layout.current_control, SearchBufferControl):
                app.layout.current_control = app.layout.previous_control
            else:
                cmd.logger.warn("Query not cancelled. Run KILL <jobId> to cancel it")
                buf.reset()
        except EOFError:
            cmd.logger.warn('Bye!')
            return
