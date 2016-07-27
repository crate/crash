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

from six import StringIO
from unittest import TestCase
from mock import patch
from .commands import ReadFileCommand, ToggleAutocompleteCommand, \
    NodeCheckCommand, ClusterCheckCommand, CheckCommand

from .command import CrateCmd
from distutils.version import StrictVersion
from .printer import PrintWrapper
from .outputs import OutputWriter


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


class ChecksCommandTest(TestCase):

    @patch('crate.crash.command.CrateCmd')
    def test_node_check(self, cmd):
        rows = [
                    [u'local1', u'check1'],
                    [u'local2', u'check2'],
                    [u'loca1', u'check2']
                ]
        cols = [(u'Failed Check', ), (u'Number of Nodes', )]
        cmd._execute.return_value = True
        cmd.cursor.fetchall.return_value = rows
        cmd.cursor.description = cols
        cmd.connection.lowest_server_version = StrictVersion("0.56.4")

        NodeCheckCommand()(cmd)
        cmd.pprint.assert_called_with(rows, [c[0] for c in cols])

    @patch('crate.crash.command.CrateCmd')
    def test_node_check_for_not_supported_version(self, cmd):
        cmd.connection.lowest_server_version = StrictVersion("0.52.3")
        NodeCheckCommand()(cmd)
        excepted = 'Crate 0.52.3 does not support the "\check nodes" command.'
        cmd.logger.warn.assert_called_with(excepted)

    @patch('crate.crash.command.CrateCmd')
    def test_cluster_check(self, cmd):
        rows = [
                    [u'local1', u'check1'],
                    [u'local2', u'check2'],
                    [u'loca1', u'check2']
                ]
        cols = [(u'Failed Check', ), (u'Number of Nodes', )]
        cmd._execute.return_value = True
        cmd.cursor.fetchall.return_value = rows
        cmd.cursor.description = cols
        cmd.connection.lowest_server_version = StrictVersion("0.53.1")

        ClusterCheckCommand()(cmd)
        cmd.pprint.assert_called_with(rows, [c[0] for c in cols])

    @patch('crate.crash.command.CrateCmd')
    def test_cluster_check_for_not_supported_version(self, cmd):
        cmd.connection.lowest_server_version = StrictVersion("0.49.4")
        ClusterCheckCommand()(cmd)
        excepted = 'Crate 0.49.4 does not support the cluster "check" command.'
        cmd.logger.warn.assert_called_with(excepted)

    @patch('crate.crash.command.CrateCmd')
    def test_check_command_with_cluster_check(self, cmd):
        command = CheckCommand()
        cmd._execute.return_value = True
        cmd.cursor.fetchall.return_value = []
        cmd.connection.lowest_server_version = StrictVersion("0.56.1")

        command(cmd, 'cluster')
        cmd.logger.info.assert_called_with('CLUSTER CHECK OK')

    @patch('crate.crash.command.CrateCmd')
    def test_check_command_with_node_check(self, cmd):
        command = CheckCommand()
        cmd._execute.return_value = True
        cmd.cursor.fetchall.return_value = []
        cmd.connection.lowest_server_version = StrictVersion("0.56.1")

        command(cmd, 'nodes')
        cmd.logger.info.assert_called_with('NODE CHECK OK')
