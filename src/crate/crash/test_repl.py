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
from prompt_toolkit.token import Token
from .repl import SQLCompleter, Capitalizer, create_buffer, _get_toolbar_tokens
from .command import CrateCmd

class SQLCompleterTest(TestCase):

    def setUp(self):
        cmd = CrateCmd()
        self.completer = SQLCompleter(cmd)

    def test_get_builtin_command_completions(self):
        result = sorted(list(self.completer.get_command_completions('\\c')))
        self.assertEqual(result, ['c', 'check', 'connect'])

    def test_get_command_completions_format(self):
        result = list(self.completer.get_command_completions(r'\format dyn'))
        self.assertEqual(result, ['dynamic'])


class CrashBufferTest(TestCase):

    def test_create_buffer(self):
        cmd = CrateCmd()
        buffer = create_buffer(cmd, '/tmp/history')
        self.assertEquals(buffer.on_text_insert.fire(), None)


class AutoCapitalizeTest(TestCase):

    def setUp(self):
        cmd = CrateCmd()
        self.capitalizer = Capitalizer(cmd)

    def test_capitalize(self):
        buffer = Buffer()

        text = u'selec'
        buffer.set_document(Document(text, len(text)))
        self.capitalizer.apply_capitalization(buffer)
        self.assertEqual(u'selec', buffer.text)

        text = u'select'
        buffer.set_document(Document(text, len(text)))
        self.capitalizer.apply_capitalization(buffer)
        self.assertEqual(u'SELECT', buffer.text)

        text = u'CREATE TABLE "select'
        buffer.set_document(Document(text, len(text)))
        self.capitalizer.apply_capitalization(buffer)
        self.assertEqual(u'CREATE TABLE "select', buffer.text)

        text = u'CREATE TABLE \'select\''
        buffer.set_document(Document(text, len(text)))
        self.capitalizer.apply_capitalization(buffer)
        self.assertEqual(u'CREATE TABLE \'select\'', buffer.text)

        text = u'create table test (x int)'
        buffer.set_document(Document(text, len(text)))
        self.capitalizer.apply_capitalization(buffer)
        self.assertEqual(u'CREATE TABLE test (x INT)', buffer.text)

        text = u'create table test (a boolean, b string, c integer)'
        buffer.set_document(Document(text, len(text)))
        self.capitalizer.apply_capitalization(buffer)
        self.assertEqual(u'CREATE TABLE test (a BOOLEAN, b STRING, c INTEGER)', buffer.text)

        text = u'create table test\n(a boolean, b string, c integer)'
        buffer.set_document(Document(text, len(text)))
        self.capitalizer.apply_capitalization(buffer)
        self.assertEqual(u'CREATE TABLE test\n(a BOOLEAN, b STRING, c INTEGER)', buffer.text)

        text = u'\select dynamic'
        buffer.set_document(Document(text, len(text)))
        self.capitalizer.apply_capitalization(buffer)
        self.assertEqual(u'\select dynamic', buffer.text)

    def test_undo_capitalize(self):
        buffer = Buffer()

        text = u'Selec'
        buffer.set_document(Document(text, len(text)))
        self.capitalizer.apply_capitalization(buffer)
        self.assertEqual(u'Selec', buffer.text)

        text = buffer.text + 't'
        buffer.set_document(Document(text, len(text)))
        self.capitalizer.apply_capitalization(buffer)
        self.assertEqual(u'SELECT', buffer.text)

        text = buffer.text + 'i'
        buffer.set_document(Document(text, len(text)))
        self.capitalizer.apply_capitalization(buffer)
        self.assertEqual(u'Selecti', buffer.text)

        text = buffer.text + 'on'
        buffer.set_document(Document(text, len(text)))
        self.capitalizer.apply_capitalization(buffer)
        self.assertEqual(u'Selection', buffer.text)

    def test_keyword_replacer(self):
        KEYWORD_RE = r'\w+'
        text = u'select'
        match = re.match(KEYWORD_RE, text)
        self.assertEqual(u'SELECT', self.capitalizer.keyword_replacer(match))

        text = u'definitelyNotAnSQLKeyword'
        match = re.match(KEYWORD_RE, text)
        self.assertEqual(u'definitelyNotAnSQLKeyword', self.capitalizer.keyword_replacer(match))

    def test_is_prefix(self):
        string = u'SELECT * FROM test'
        prefix = u'SELECT * FROM'
        self.assertTrue(self.capitalizer.is_prefix(string, prefix))

        prefix = u'SELECT testCol FROM'
        self.assertFalse(self.capitalizer.is_prefix(string, prefix))


class ToolbarTest(TestCase):

    def test_get_session_tokens(self):
        result = _get_toolbar_tokens(lambda: True, 'crate', ['http://host1:4200', 'https://host2:4200'])
        self.assertEqual(result, [(Token.Toolbar.Status.Key, 'USER: '),
                           (Token.Toolbar.Status, 'crate'),
                           (Token.Toolbar.Status, ' | '),
                           (Token.Toolbar.Status.Key, 'HOSTS: '),
                           (Token.Toolbar.Status, 'host1:4200, host2:4200')])

    def test_get_not_connected_tokens(self):
        result = _get_toolbar_tokens(lambda: False, 'crate', None)
        self.assertEqual(result, [(Token.Toolbar.Status, 'not connected')])
