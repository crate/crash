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


from unittest import TestCase
from mock import patch
from mock import MagicMock, PropertyMock

from .command import CrateCmd
from .sysinfo import SysInfoCommand, Result as Res


class SysInfoTest(TestCase):

    NODES_FIELDS_FETCHED = ((u'crate_version', None), (u'total_heap_mb', None))
    NODES_INFO = [[u'0.54.0', 16301], [u'0.54.0', 16301]]
    NODES_FIELDS = [u'crate_version', u'total_heap_mb']
    
    CLUSTER_FIELDS_FETCHED = \
        ((u'number_of_shards', None), (u'number_of_records', None))
    CLUSTER_INFO = [[128, 664755863]]
    CLUSTER_FIELDS = [u'number_of_shards', u'number_of_records']

    def setUp(self):
        self.patcher = patch(__name__+'.CrateCmd')
        self.cmd = self.patcher.start()
        self.sys_info = SysInfoCommand(self.cmd)

        # composing return values for multiple calls of cmd.cursor.fetchall method
        # the number of valuses in the list is equal to the number of queries in
        # SysInfoCommand.CLUSTER_INFO and NODES_INFO
        self.fetch_all = [SysInfoTest.CLUSTER_INFO] * len(SysInfoCommand.CLUSTER_INFO)
        self.fetch_all.append(SysInfoTest.NODES_INFO)
        self.desc = [SysInfoTest.CLUSTER_FIELDS_FETCHED] * len(SysInfoCommand.CLUSTER_INFO)
        self.desc.append(SysInfoTest.NODES_FIELDS_FETCHED)

    
    def tearDown(self):
        self.patcher.stop()

    def test_nodes_info(self):
        self.cmd._execute.return_value = True
        self.cmd.cursor.fetchall.return_value = SysInfoTest.NODES_INFO
        type(self.cmd.cursor).description = \
            PropertyMock(return_value=SysInfoTest.NODES_FIELDS_FETCHED)
        result = []
        succcess = self.sys_info._nodes_info(result)
        expected = Res(SysInfoTest.NODES_INFO, SysInfoTest.NODES_FIELDS)
        self.assertEqual(succcess, True)
        self.assertEqual(expected, result[0])

    def test_sys_info(self):
        self.cmd.cursor.fetchall.side_effect = self.fetch_all
        self.cmd._execute.return_value = True
        type(self.cmd.cursor).description = PropertyMock(side_effect=self.desc)

        succcess, result = self.sys_info._sys_info()
        self.assertEqual(succcess, True)
        expected_nodes = Res(SysInfoTest.NODES_INFO, SysInfoTest.NODES_FIELDS)
        # test only the second part of result
        self.assertEqual(expected_nodes, result[1])

    def test_sys_info_fails(self):
        self.cmd.cursor.fetchall.side_effect = self.fetch_all
        succcess_ = [True] * len(SysInfoCommand.CLUSTER_INFO)
        succcess_.append(False)
        self.cmd._execute.side_effect = succcess_
        type(self.cmd.cursor).description = PropertyMock(side_effect=self.desc)

        succcess, result = self.sys_info._sys_info()
        self.assertEqual(succcess, False)
        expected_nodes = Res(SysInfoTest.NODES_INFO, SysInfoTest.NODES_FIELDS)
        # must not contain any partial result from first successful calls
        self.assertEqual([], result)

    def test_cluster_info(self):
        self.cmd._execute.return_value = True
        self.cmd.cursor.fetchall.return_value = SysInfoTest.CLUSTER_INFO
        type(self.cmd.cursor).description = \
            PropertyMock(return_value=SysInfoTest.CLUSTER_FIELDS_FETCHED)
        result = []
        succcess = self.sys_info._nodes_info(result)
        self.assertEqual(succcess, True)
        expected = Res(SysInfoTest.CLUSTER_INFO, SysInfoTest.CLUSTER_FIELDS)
        self.assertEqual(expected, result[0])

    def test_execute_when_nodes_info_fails(self):
        self.cmd._execute.return_value = False
        self.cmd.cursor.fetchall.return_value = SysInfoTest.NODES_INFO
        type(self.cmd.cursor).description = \
            PropertyMock(return_value=SysInfoTest.NODES_FIELDS_FETCHED)
        result = []
        succcess = self.sys_info._nodes_info(result)
        self.assertEqual(succcess, False)
        self.assertEqual([], result)

    def test_exceute_when_nodes_cluster_infos_fails(self):
        self.cmd._execute.return_value = False
        self.cmd.cursor.fetchall.return_value = SysInfoTest.CLUSTER_INFO
        type(self.cmd.cursor).description = \
            PropertyMock(return_value=SysInfoTest.CLUSTER_FIELDS_FETCHED)
        result = []
        succcess = self.sys_info._nodes_info(result)
        self.assertEqual(succcess, False)
        self.assertEqual([], result)
