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

from unittest import TestCase
from prompt_toolkit.buffer import Buffer
from prompt_toolkit.document import Document
from .repl import SQLCompleter, Capitalizer
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


class AutoCapitalizeTest(TestCase):

    def setUp(self):
        cmd = CrateCmd()
        self.capitalizer = Capitalizer(cmd)

    def test_capitalize(self):
        buffer = Buffer()

        text = u'selec'
        buffer.set_document(Document(text, len(text)))
        self.capitalizer(buffer)
        self.assertEqual(u'selec', buffer.text)

        text = u'select'
        buffer.set_document(Document(text, len(text)))
        self.capitalizer(buffer)
        self.assertEqual(u'SELECT', buffer.text)

        text = u'CREATE TABLE "select'
        buffer.set_document(Document(text, len(text)))
        self.capitalizer(buffer)
        self.assertEqual(u'CREATE TABLE "select', buffer.text)

    def test_undo_capitalize(self):
        buffer = Buffer()

        text = u'Selec'
        buffer.set_document(Document(text, len(text)))
        self.capitalizer(buffer)
        self.assertEqual(u'Selec', buffer.text)

        text = buffer.text + 't'
        buffer.set_document(Document(text, len(text)))
        self.capitalizer(buffer)
        self.assertEqual(u'SELECT', buffer.text)

        text = buffer.text + 'i'
        buffer.set_document(Document(text, len(text)))
        self.capitalizer(buffer)
        self.assertEqual(u'Selecti', buffer.text)

        text = buffer.text + 'on'
        buffer.set_document(Document(text, len(text)))
        self.capitalizer(buffer)
        self.assertEqual(u'Selection', buffer.text)
