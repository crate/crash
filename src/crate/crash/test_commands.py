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
from unittest.mock import patch, MagicMock
from .commands import ReadFileCommand, \
    ToggleAutocompleteCommand, ToggleAutoCapitalizeCommand, ToggleVerboseCommand, \
    NodeCheckCommand, ClusterCheckCommand, CheckCommand

from .command import CrateShell
from distutils.version import StrictVersion


class ReadFileCommandTest(TestCase):

    def setUp(self):
        self.tmp_dir = tempfile.mkdtemp()
        self.cmd = ReadFileCommand()
        self.dummy_file = os.path.join(self.tmp_dir, 'dummy.sql')
        self.dummy_dir = os.path.join(self.tmp_dir, 'dummy_folder')
        self.dummy_file_in_dir = os.path.join(self.dummy_dir, 'dummy2.sql')
        os.mkdir(self.dummy_dir)
        with open(self.dummy_file, 'w') as f:
            f.write('')
        with open(self.dummy_file_in_dir, 'w') as f:
            f.write('')

    def tearDown(self):
        if os.path.exists(self.tmp_dir):
            shutil.rmtree(self.tmp_dir)

    def test_complete_correct_filename(self):
        results = sorted(list(
            self.cmd.complete(None, os.path.join(self.tmp_dir, 'dummy.sql'))))
        self.assertEqual(results, [])

    def test_complete_shows_folder_and_sql_files(self):
        results = sorted(list(
            self.cmd.complete(None, os.path.join(self.tmp_dir, 'dum'))))
        self.assertEqual(results, ['dummy.sql', 'dummy_folder/'])

    def test_complete_shows_only_folder(self):
        results = sorted(list(
            self.cmd.complete(None, os.path.join(self.tmp_dir, 'dummy_'))))
        self.assertEqual(results, ['dummy_folder/'])

    def test_complete_shows_only_file_within_folder(self):
        results = sorted(list(self.cmd.complete(
            None, os.path.join(self.tmp_dir, 'dummy_folder/'))))
        self.assertEqual(results, ['dummy2.sql'])

    @patch('crate.crash.command.CrateShell')
    def test_call(self, fake_cmd):
        path = os.path.join(self.tmp_dir, 'foo.sql')
        with open(path, 'w') as fp:
            fp.write('SELECT * FROM sys.nodes')
        command = ReadFileCommand()
        command(fake_cmd, path)
        self.assertEqual(fake_cmd.process_iterable.call_count, 1)


class ToggleAutocompleteCommandTest(TestCase):

    @patch('crate.crash.command.CrateShell')
    def test_toggle_output(self, fake_cmd):
        fake_cmd._autocomplete = True
        command = ToggleAutocompleteCommand()
        output = command(fake_cmd)
        self.assertEqual(output, 'Autocomplete OFF')
        output = command(fake_cmd)
        self.assertEqual(output, 'Autocomplete ON')


class ToggleAutoCapitalizeCommandTest(TestCase):

    @patch('crate.crash.command.CrateShell')
    def test_toggle_output(self, fake_cmd):
        fake_cmd._autocapitalization = True
        command = ToggleAutoCapitalizeCommand()
        output = command(fake_cmd)
        self.assertEqual(output, 'Auto-capitalization OFF')
        output = command(fake_cmd)
        self.assertEqual(output, 'Auto-capitalization ON')


class ToggleVerboseCommandTest(TestCase):

    @patch('crate.crash.command.CrateShell')
    def test_toggle_output(self, fake_cmd):
        fake_cmd.error_trace = True
        command = ToggleVerboseCommand()
        output = command(fake_cmd)
        self.assertEqual(output, 'Verbose OFF')
        self.assertEqual(fake_cmd.reconnect.call_count, 1)

        fake_cmd.reset_mock()
        output = command(fake_cmd)
        self.assertEqual(output, 'Verbose ON')
        self.assertEqual(fake_cmd.reconnect.call_count, 1)


class ShowTablesCommandTest(TestCase):

    def test_post_2_0(self):
        cmd = CrateShell()
        cmd._exec = MagicMock()
        cmd.connection.lowest_server_version = StrictVersion("2.0.0")
        cmd._show_tables()
        cmd._exec.assert_called_with("SELECT format('%s.%s', table_schema, table_name) AS name FROM information_schema.tables WHERE table_schema NOT IN ('sys','information_schema', 'pg_catalog') AND table_type = 'BASE TABLE'")

    def test_post_0_57(self):
        cmd = CrateShell()
        cmd._exec = MagicMock()
        cmd.connection.lowest_server_version = StrictVersion("0.57.0")
        cmd._show_tables()
        cmd._exec.assert_called_with("SELECT format('%s.%s', table_schema, table_name) AS name FROM information_schema.tables WHERE table_schema NOT IN ('sys','information_schema', 'pg_catalog')")

    def test_pre_0_57(self):
        cmd = CrateShell()
        cmd._exec = MagicMock()
        cmd.connection.lowest_server_version = StrictVersion("0.56.4")
        cmd._show_tables()
        cmd._exec.assert_called_with("SELECT format('%s.%s', schema_name, table_name) AS name FROM information_schema.tables WHERE schema_name NOT IN ('sys','information_schema', 'pg_catalog')")


class ChecksCommandTest(TestCase):

    @patch('crate.crash.command.CrateShell')
    def test_node_check(self, cmd):
        rows = [
            ['local1', 'check1'],
            ['local2', 'check2'],
            ['loca1', 'check2'],
        ]
        cols = [('Failed Check', ), ('Number of Nodes', )]
        cmd._execute.return_value = True
        cmd.cursor.fetchall.return_value = rows
        cmd.cursor.description = cols
        cmd.connection.lowest_server_version = StrictVersion("0.56.4")

        NodeCheckCommand()(cmd)
        cmd.pprint.assert_called_with(rows, [c[0] for c in cols])

    @patch('crate.crash.command.CrateShell')
    def test_node_check_for_not_supported_version(self, cmd):
        cmd.connection.lowest_server_version = StrictVersion("0.52.3")
        NodeCheckCommand()(cmd)
        excepted = 'Crate 0.52.3 does not support the "\check nodes" command.'
        cmd.logger.warn.assert_called_with(excepted)

    @patch('crate.crash.command.CrateShell')
    def test_cluster_check(self, cmd):
        rows = [
            ['local1', 'check1'],
            ['local2', 'check2'],
            ['loca1', 'check2'],
        ]
        cols = [('Failed Check', ), ('Number of Nodes', )]
        cmd._execute.return_value = True
        cmd.cursor.fetchall.return_value = rows
        cmd.cursor.description = cols
        cmd.connection.lowest_server_version = StrictVersion("0.53.1")

        ClusterCheckCommand()(cmd)
        cmd.pprint.assert_called_with(rows, [c[0] for c in cols])

    @patch('crate.crash.command.CrateShell')
    def test_cluster_check_for_not_supported_version(self, cmd):
        cmd.connection.lowest_server_version = StrictVersion("0.49.4")
        ClusterCheckCommand()(cmd)
        excepted = 'Crate 0.49.4 does not support the cluster "check" command.'
        cmd.logger.warn.assert_called_with(excepted)

    @patch('crate.crash.command.CrateShell')
    def test_check_command_with_cluster_check(self, cmd):
        command = CheckCommand()
        cmd._execute.return_value = True
        cmd.cursor.fetchall.return_value = []
        cmd.connection.lowest_server_version = StrictVersion("0.56.1")

        command(cmd, 'cluster')
        cmd.logger.info.assert_called_with('CLUSTER CHECK OK')

    @patch('crate.crash.command.CrateShell')
    def test_check_command_with_node_check(self, cmd):
        command = CheckCommand()
        cmd._execute.return_value = True
        cmd.cursor.fetchall.return_value = []
        cmd.connection.lowest_server_version = StrictVersion("0.56.1")

        command(cmd, 'nodes')
        cmd.logger.info.assert_called_with('NODE CHECK OK')
