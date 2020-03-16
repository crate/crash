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

import re
from unittest import TestCase

from prompt_toolkit.buffer import Buffer
from prompt_toolkit.document import Document
from pygments.token import Token

from crate.crash.command import ConnectionMeta, CrateShell
from crate.crash.repl import (
    Capitalizer,
    SQLCompleter,
    _get_toolbar_tokens,
    create_buffer,
)


class SQLCompleterTest(TestCase):

    def setUp(self):
        cmd = CrateShell()
        self.completer = SQLCompleter(cmd)

    def test_get_builtin_command_completions(self):
        result = sorted(list(self.completer.get_command_completions('\\c')))
        self.assertEqual(result, ['c', 'check', 'connect'])

    def test_get_command_completions_format(self):
        result = list(self.completer.get_command_completions('\\format dyn'))
        self.assertEqual(result, ['dynamic'])


class CrashBufferTest(TestCase):

    def test_create_buffer(self):
        cmd = CrateShell()
        buffer = create_buffer(cmd, '/tmp/history')
        self.assertEqual(buffer.on_text_insert.fire(), None)


class AutoCapitalizeTest(TestCase):

    def setUp(self):
        cmd = CrateShell()
        self.capitalizer = Capitalizer(cmd, SQLCompleter(cmd))

    def test_capitalize(self):
        buffer = Buffer()

        text = 'selec'
        buffer.set_document(Document(text, len(text)))
        self.capitalizer.apply_capitalization(buffer)
        self.assertEqual('selec', buffer.text)

        text = 'select'
        buffer.set_document(Document(text, len(text)))
        self.capitalizer.apply_capitalization(buffer)
        self.assertEqual('SELECT', buffer.text)

        text = 'CREATE TABLE "select'
        buffer.set_document(Document(text, len(text)))
        self.capitalizer.apply_capitalization(buffer)
        self.assertEqual('CREATE TABLE "select', buffer.text)

        text = 'CREATE TABLE \'select\''
        buffer.set_document(Document(text, len(text)))
        self.capitalizer.apply_capitalization(buffer)
        self.assertEqual('CREATE TABLE \'select\'', buffer.text)

        text = 'create table test (x int)'
        buffer.set_document(Document(text, len(text)))
        self.capitalizer.apply_capitalization(buffer)
        self.assertEqual('CREATE TABLE test (x INT)', buffer.text)

        text = 'create table test (a boolean, b string, c integer)'
        buffer.set_document(Document(text, len(text)))
        self.capitalizer.apply_capitalization(buffer)
        self.assertEqual('CREATE TABLE test (a BOOLEAN, b STRING, c INTEGER)', buffer.text)

        text = 'create table test\n(a boolean, b string, c integer)'
        buffer.set_document(Document(text, len(text)))
        self.capitalizer.apply_capitalization(buffer)
        self.assertEqual('CREATE TABLE test\n(a BOOLEAN, b STRING, c INTEGER)', buffer.text)

        text = '\\select dynamic'
        buffer.set_document(Document(text, len(text)))
        self.capitalizer.apply_capitalization(buffer)
        self.assertEqual('\\select dynamic', buffer.text)

    def test_undo_capitalize(self):
        buffer = Buffer()

        text = 'Selec'
        buffer.set_document(Document(text, len(text)))
        self.capitalizer.apply_capitalization(buffer)
        self.assertEqual('Selec', buffer.text)

        text = buffer.text + 't'
        buffer.set_document(Document(text, len(text)))
        self.capitalizer.apply_capitalization(buffer)
        self.assertEqual('SELECT', buffer.text)

        text = buffer.text + 'i'
        buffer.set_document(Document(text, len(text)))
        self.capitalizer.apply_capitalization(buffer)
        self.assertEqual('Selecti', buffer.text)

        text = buffer.text + 'on'
        buffer.set_document(Document(text, len(text)))
        self.capitalizer.apply_capitalization(buffer)
        self.assertEqual('Selection', buffer.text)

    def test_keyword_replacer(self):
        KEYWORD_RE = r'\w+'
        text = 'select'
        match = re.match(KEYWORD_RE, text)
        self.assertEqual('SELECT', self.capitalizer.keyword_replacer(match))

        text = 'definitelyNotAnSQLKeyword'
        match = re.match(KEYWORD_RE, text)
        self.assertEqual('definitelyNotAnSQLKeyword', self.capitalizer.keyword_replacer(match))

    def test_is_prefix(self):
        string = 'SELECT * FROM test'
        prefix = 'SELECT * FROM'
        self.assertTrue(self.capitalizer.is_prefix(string, prefix))

        prefix = 'SELECT testCol FROM'
        self.assertFalse(self.capitalizer.is_prefix(string, prefix))


class ToolbarTest(TestCase):

    def test_get_session_tokens(self):
        result = _get_toolbar_tokens(
            True,
            ['http://host1:4200', 'https://host2:4200'],
            ConnectionMeta('crate', 'my_schema', 'cr8'),
        )
        self.assertEqual(
            result.token_list,
            [(Token.Toolbar.Status.Key, 'USER: '),
             (Token.Toolbar.Status, 'crate'),
             (Token.Toolbar.Status, ' | '),
             (Token.Toolbar.Status.Key, 'SCHEMA: '),
             (Token.Toolbar.Status, 'my_schema'),
             (Token.Toolbar.Status, ' | '),
             (Token.Toolbar.Status.Key, 'CLUSTER: '),
             (Token.Toolbar.Status, 'cr8'),
             (Token.Toolbar.Status, ' | '),
             (Token.Toolbar.Status.Key, 'HOSTS: '),
             (Token.Toolbar.Status, 'host1:4200, host2:4200')])

    def test_get_session_tokens_no_info(self):
        result = _get_toolbar_tokens(
            True,
            ['http://localhost:4200'],
            ConnectionMeta(None, None, None),
        )
        self.assertEqual(
            result.token_list,
            [(Token.Toolbar.Status.Key, 'USER: '),
             (Token.Toolbar.Status, '--'),
             (Token.Toolbar.Status, ' | '),
             (Token.Toolbar.Status.Key, 'SCHEMA: '),
             (Token.Toolbar.Status, 'doc'),
             (Token.Toolbar.Status, ' | '),
             (Token.Toolbar.Status.Key, 'CLUSTER: '),
             (Token.Toolbar.Status, '--'),
             (Token.Toolbar.Status, ' | '),
             (Token.Toolbar.Status.Key, 'HOSTS: '),
             (Token.Toolbar.Status, 'localhost:4200')])

    def test_get_not_connected_tokens(self):
        result = _get_toolbar_tokens(
            False,
            [],
            ConnectionMeta(None, None, None)
        )
        self.assertEqual(
            result.token_list,
            [(Token.Toolbar.Status, 'not connected')]
        )
