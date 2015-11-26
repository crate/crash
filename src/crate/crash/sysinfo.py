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


import logging
from collections import namedtuple
from distutils.version import StrictVersion

from crate.client.exceptions import ConnectionError, ProgrammingError
from crate.client import connect

from .printer import ColorPrinter


Result = namedtuple('Result', ['rows', 'cols'])
SYSINFO_MIN_VERSION = StrictVersion("0.54.0")


class SysInfoCommand(object):

    CLUSTER_INFO = [ """ select count(distinct(id)) as number_of_shards,
                         cast(sum(num_docs) as integer) as number_of_records
                         from sys.shards """, 

                     """ select count(1) as number_of_nodes
                           from sys.nodes """,

                     """ select count(distinct(table_name))
                                 as number_of_tables
                         from information_schema.tables
                         where schema_name
                         not in ('information_schema', 'sys') """ ]

    NODES_INFO = [ """ select name,
                          hostname,
                          version['number'] as crate_version,
                          round(heap['max'] / 1024.0 / 1024.0)
                                as total_heap_mb,
                          round((mem['free'] + mem['used']) / 1024.0 / 1024.0)
                                as total_memory_mb,
                          os_info['available_processors'] as cpus,
                          os['uptime'] /1000 as uptime_s,
                          format('%s - %s (%s)',
                                os_info['name'],
                                os_info['version'],
                                os_info['arch']) as os_info,
                          format('java version \"%s\" %s %s (build %s)',
                                os_info['jvm']['version'],
                                os_info['jvm']['vm_vendor'],
                                os_info['jvm']['vm_name'],
                                os_info['jvm']['vm_version']) as jvm_info
                          from sys.nodes
                          order by os['uptime'] desc """ ]

    def __init__(self, cmd):
        self.cmd = cmd

    def execute(self):
        """ print system and cluster info """
        if not self.cmd.is_conn_avaliable():
          return
        if self.cmd.connection.lowest_server_version >= SYSINFO_MIN_VERSION:
            success, rows = self._sys_info()
            self.cmd.exit_code = self.cmd.exit_code or int(not success)
            if success:
                for result in rows:
                    self.cmd.pprint(result.rows, result.cols)
                self.cmd.logger.info("For debugging purposes you can send above listed information to support@crate.io")
        else:
            tmpl = 'Crate {version} does not support the cluster "sysinfo" command'
            self.cmd.logger.warn(tmpl
                .format(version=self.cmd.connection.lowest_server_version))

    def _sys_info(self):
        result = []
        success = self._cluster_info(result)
        success &= self._nodes_info(result)
        if success is False:
          result = []
        return (success, result)

    def _cluster_info(self, result):
        rows = []
        cols = []
        for query in SysInfoCommand.CLUSTER_INFO:
            success = self.cmd._execute(query)
            if success is False:
                return success
            rows.extend(self.cmd.cursor.fetchall()[0])
            cols.extend([c[0] for c in self.cmd.cursor.description])
        result.append(Result([rows], cols))
        return True

    def _nodes_info(self, result):
        success = self.cmd._execute(SysInfoCommand.NODES_INFO[0])
        if success:
            result.append(Result(self.cmd.cursor.fetchall(), \
                [c[0] for c in self.cmd.cursor.description]))
        return success
