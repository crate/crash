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

from pygments.lexers.sql import SqlLexer
from pygments.style import Style
from pygments.token import (Keyword,
                            Comment,
                            Operator,
                            Number,
                            Literal,
                            String,
                            Error,
                            Token)

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
from prompt_toolkit.shortcuts import (create_output,
                                      create_eventloop)

from .commands import Command
from .layout import create_layout
from .keybinding import bind_keys

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
        Token.Toolbar.Status.Key: '#4b95a3',
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
        "abs", "absolute", "action", "add", "after", "alias", "all", "allocate",
        "alter", "always", "analyzer", "and", "any", "are", "array", "array_agg",
        "array_max_cardinality", "as", "asc", "asensitive", "assertion",
        "asymmetric", "at", "atomic", "authorization", "avg", "before", "begin",
        "begin_frame", "begin_partition", "between", "bigint", "binary", "bit",
        "bit_length", "blob", "boolean", "both", "breadth", "by", "byte", "call",
        "called", "cardinality", "cascade", "cascaded", "case", "cast",
        "catalog", "catalogs", "ceil", "ceiling", "char", "char_filters",
        "char_length", "character", "character_length", "check", "clob", "close",
        "clustered", "coalesce", "collate", "collation", "collect", "column",
        "columns", "commit", "condition", "connect", "connection", "constraint",
        "constraints", "constructor", "contains", "continue", "convert", "copy",
        "corr", "corresponding", "count", "covar_pop", "covar_samp", "create",
        "cross", "cube", "cume_dist", "current", "current_catalog",
        "current_date", "current_path", "current_role", "current_row",
        "current_schema", "current_time", "current_timestamp", "current_user",
        "cursor", "cycle", "data", "date", "day", "deallocate", "dec", "decimal",
        "declare", "default", "deferrable", "deferred", "delete", "deny", "dense_rank",
        "depth", "deref", "desc", "describe", "descriptor", "deterministic",
        "diagnostics", "directory", "disconnect", "distinct", "distributed",
        "do", "domain", "double", "drop", "duplicate", "dynamic", "each",
        "element", "else", "elseif", "end", "end_exec", "end_frame",
        "end_partition", "equals", "escape", "every", "except", "exception",
        "exec", "execute", "exists", "exit", "explain", "extends", "external",
        "extract", "false", "fetch", "filter", "first", "first_value", "float",
        "for", "foreign", "format", "found", "frame_row", "free", "from", "full",
        "fulltext", "function", "functions", "fusion", "general", "generated",
        "geo_point", "geo_shape", "get", "global", "go", "goto", "grant",
        "group", "grouping", "groups", "handler", "having", "hold", "hour",
        "identity", "if", "ignored", "immediate", "in", "index", "indicator",
        "initially", "inner", "inout", "input", "insensitive", "insert", "int",
        "integer", "intersect", "intersection", "interval", "into", "ip", "is",
        "isolation", "iterate", "join", "key", "kill", "language", "large",
        "last", "last_value", "lateral", "lead", "leading", "leave", "left",
        "level", "like", "like_regex", "limit", "ln", "local", "localtime",
        "localtimestamp", "locator", "long", "loop", "lower", "map", "match",
        "max", "member", "merge", "method", "min", "minute", "mod", "modifies",
        "module", "month", "multiset", "names", "national", "natural", "nchar",
        "nclob", "new", "next", "no", "none", "normalize", "not", "nth_value",
        "ntile", "null", "nullif", "nulls", "numeric", "object", "octet_length",
        "of", "off", "offset", "old", "on", "only", "open", "optimize", "option",
        "or", "order", "ordinality", "out", "outer", "output", "over",
        "overlaps", "overlay", "pad", "parameter", "partial", "partition",
        "partitioned", "partitions", "path", "percent", "percent_rank",
        "percentile_cont", "percentile_disc", "period", "persistent", "plain",
        "portion", "position", "position_regex", "power", "precedes",
        "preceding", "precision", "prepare", "preserve", "primary",
        "primary key", "prior", "privileges", "procedure", "public", "range",
        "rank", "read", "reads", "real", "recursive", "ref", "references",
        "referencing", "refresh", "regr_avgx", "regr_avgy", "regr_count",
        "regr_intercept", "regr_r2", "regr_slope", "regr_sxx",
        "regr_sxyregr_syy", "relative", "release", "rename", "repeat", "repository",
        "reset", "resignal", "restore", "restrict", "result", "return",
        "returns", "revoke", "right", "role", "rollback", "rollup", "routine",
        "row", "row_number", "rows", "savepoint", "schema", "schemas", "scope",
        "scroll", "search", "second", "section", "select", "sensitive",
        "session", "session_user", "set", "sets", "shards", "short", "show",
        "signal", "similar", "size", "smallint", "snapshot", "some", "space",
        "specific", "specifictype", "sql", "sqlcode", "sqlerror", "sqlexception",
        "sqlstate", "sqlwarning", "sqrt", "start", "state", "static",
        "stddev_pop", "stddev_samp", "stratify", "stratify", "strict", "string",
        "submultiset", "substring", "substring_regex", "succeedsblob", "sum",
        "symmetric", "system", "system_time", "system_user", "table", "tables",
        "tablesample", "temporary", "text", "then", "time", "timestamp",
        "timezone_hour", "timezone_minute", "to", "token_filters", "tokenizer",
        "trailing", "transaction", "transient", "translate", "translate_regex",
        "translation", "treat", "trigger", "trim", "trim_array", "true",
        "truncate", "try_cast", "type", "uescape", "unbounded", "under", "undo",
        "union", "unique", "unknown", "unnest", "until", "update", "upper",
        "usage", "user", "using", "value", "value_of", "values", "var_pop",
        "var_samp", "varbinary", "varchar", "varying", "versioning", "view",
        "when", "whenever", "where", "while", "width_bucket", "window", "with",
        "within", "without", "work", "write", "year", "zone"]

    def __init__(self, cmd):
        self.cmd = cmd

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

        super(self.__class__, self).__init__(
            *args, is_multiline=is_multiline, **kwargs)


class Capitalizer:

    KEYWORD_RE = r'(?:"\w+)|(?:\'\w+)|\w+'

    def __init__(self, cmd):
        self.cmd = cmd
        self.last_changed = None

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
        if match.group(0).lower() in SQLCompleter.keywords:
            return match.group(0).upper()
        else:
            return match.group(0)

    def is_prefix(self, string, prefix):
        return string.startswith(prefix) and string != prefix


def create_buffer(cmd, history_file):
    buffer = CrashBuffer(
        history=TruncatedFileHistory(history_file, max_length=MAX_HISTORY_LENGTH),
        accept_action=AcceptAction.RETURN_DOCUMENT,
        completer=SQLCompleter(cmd),
        on_text_insert=Capitalizer(cmd).apply_capitalization
    )
    buffer.complete_while_typing = lambda cli=None: cmd.should_autocomplete()
    return buffer

def _get_toolbar_tokens(is_conn_available, username, active_servers):
        tokens = []
        if is_conn_available():
            active_servers = active_servers
            hosts = ', '.join(
                (n.replace('http://', '').replace('https://', '') for n in active_servers))
            tokens.extend([(Token.Toolbar.Status.Key, 'USER: '),
                           (Token.Toolbar.Status, '{}'.format(username)),
                           (Token.Toolbar.Status, ' | '),
                           (Token.Toolbar.Status.Key, 'HOSTS: '),
                           (Token.Toolbar.Status, hosts)])
        else:
            tokens.extend([(Token.Toolbar.Status, 'not connected')])
        return tokens


def loop(cmd, history_file):

    def session_toolbar(cli):
        return _get_toolbar_tokens(cmd.is_conn_available, cmd.username, cmd.connection.client.active_servers)

    key_binding_manager = KeyBindingManager(
        enable_search=True,
        enable_abort_and_exit_bindings=True,
        enable_system_bindings=True,
        enable_open_in_editor=True
    )
    bind_keys(key_binding_manager.registry)
    layout = create_layout(
        message=u'cr> ',
        multiline=True,
        lexer=SqlLexer,
        extra_input_processors=[
            ConditionalProcessor(
                processor=HighlightMatchingBracketProcessor(chars='[](){}'),
                filter=HasFocus(DEFAULT_BUFFER) & ~IsDone())
        ],
        get_bottom_toolbar_tokens=session_toolbar
    )
    application = Application(
        layout=layout,
        buffer=create_buffer(cmd, history_file),
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
