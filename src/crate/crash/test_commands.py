# -*- coding: utf-8; -*-
# vi: set encoding=utf-8
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
import shutil
import tempfile
from unittest import TestCase
from mock import patch
from .commands import ReadFileCommand, ToggleAutocompleteCommand


class ReadFileCommandTest(TestCase):

    def setUp(self):
        self.tmp_dir = tempfile.mkdtemp()

    def tearDown(self):
        if os.path.exists(self.tmp_dir):
            shutil.rmtree(self.tmp_dir)

    @patch('glob.glob')
    def test_complete(self, fake_glob):
        fake_glob.return_value = ['foo', 'foobar']

        cmd = ReadFileCommand()
        results = cmd.complete(None, 'fo')

        self.assertEqual(results, ['foo', 'foobar'])
        fake_glob.assert_called_with('fo*.sql')

    @patch('crate.crash.command.CrateCmd')
    def test_call(self, fake_cmd):
        path = os.path.join(self.tmp_dir, 'foo.sql')
        with open(path, 'w') as fp:
            fp.write('SELECT * FROM sys.nodes')
        command = ReadFileCommand()
        command(fake_cmd, path)
        fake_cmd.process.assert_called_with('SELECT * FROM sys.nodes')


class ToggleAutocompleteCommandTest(TestCase):

    @patch('crate.crash.command.CrateCmd')
    def test_toggle_output(self, fake_cmd):
        fake_cmd._autocomplete = True
        command = ToggleAutocompleteCommand()
        output = command(fake_cmd)
        self.assertEqual(output, 'Autocomplete OFF')
        output = command(fake_cmd)
        self.assertEqual(output, 'Autocomplete ON')


