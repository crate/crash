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
from prompt_toolkit.document import Document
from prompt_toolkit.keys import Keys
from prompt_toolkit.key_binding.manager import KeyBindingManager
from .keybinding import bind_keys, _is_start_of_multiline, _line_ends_with_tab


doc = lambda t: Document(t, len(t))
is_start_of_multiline = lambda t: _is_start_of_multiline(doc(t))
line_ends_with_tab = lambda t: _line_ends_with_tab(doc(t))


def bindings_for_key(mngr, key):
    return mngr.registry.get_bindings_for_keys((key,))


def handlers_for_key(mngr, key):
    return [b.handler.__name__ for b in bindings_for_key(mngr, key)]


class TabIndentTest(TestCase):

    def test_indent(self):
        self.assertFalse(is_start_of_multiline(''))
        self.assertFalse(is_start_of_multiline('SELECT'))
        self.assertFalse(is_start_of_multiline('SELECT\n*'))
        self.assertTrue(is_start_of_multiline('SELECT\n'))
        self.assertTrue(is_start_of_multiline('SELECT\n '))
        self.assertTrue(is_start_of_multiline('\n'))

    def test_deindent(self):
        self.assertFalse(line_ends_with_tab(''))
        self.assertFalse(line_ends_with_tab('SELECT'))
        self.assertFalse(line_ends_with_tab('SELECT  '))
        self.assertFalse(line_ends_with_tab('SELECT  \n'))
        self.assertTrue(line_ends_with_tab('SELECT    '))
        self.assertTrue(line_ends_with_tab('SELECT\n    '))

    def test_bindings(self):
        mngr = KeyBindingManager(
            enable_search=True,
            enable_abort_and_exit_bindings=True,
            enable_system_bindings=True,
            enable_open_in_editor=True
        )
        bind_keys(mngr.registry)

        self.assertTrue('on_backspace' in handlers_for_key(mngr, Keys.Backspace))
        self.assertTrue('on_tab' in handlers_for_key(mngr, Keys.Tab))
