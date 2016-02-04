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
from .repl import SQLCompleter
from .command import CrateCmd


class SQLCompleterTest(TestCase):
    def setUp(self):
        self.cmd = CrateCmd()
        self.completer = SQLCompleter(self.cmd)

    def test_get_builtin_command_completions(self):
        c = self.completer
        result = sorted(list(c.get_command_completions('\\c')))
        self.assertEqual(result, ['c', 'check', 'connect'])

    def test_get_command_completions_format(self):
        cmd = CrateCmd()
        completer = SQLCompleter(cmd)
        result = list(completer.get_command_completions(r'\format dyn'))
        self.assertEqual(result, ['dynamic'])
