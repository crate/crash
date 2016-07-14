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

from __future__ import absolute_import

import os
import unittest
import doctest
import zc.customdoctests
from crate.testing.layer import CrateLayer
from .command import CrateCmd
from .printer import ColorPrinter, PrintWrapper
from .test_command import CommandTest, OutputWriterTest
from .test_commands import ReadFileCommandTest, ToggleAutocompleteCommandTest, \
    ChecksCommandTest
from .test_sysinfo import SysInfoTest
from .test_repl import SQLCompleterTest
from .test_config import ConfigurationTest


class CrateTestCmd(CrateCmd):

    def __init__(self, **kwargs):
        super(CrateTestCmd, self).__init__(**kwargs)
        doctest_print = PrintWrapper()
        self.logger = ColorPrinter(False, stream=doctest_print, line_end='')


def project_path(*parts):
    return os.path.join(
        os.path.dirname(os.path.dirname(__file__)),
        '..', '..', *parts)


def crate_path(*parts):
    return project_path('parts', 'crate', *parts)


def crash_transform(txt):
    return u'cmd.process({0})'.format(repr(txt.strip()))


crash_parser = zc.customdoctests.DocTestParser(
    ps1='cr>', comment_prefix='#', transform=crash_transform)


crate_port = 44209
crate_transport_port = 44309
crate_layer = CrateLayer('crate',
                         crate_home=crate_path(),
                         crate_exec=crate_path('bin', 'crate'),
                         port=crate_port,
                         transport_port=crate_transport_port)

crate_host = "127.0.0.1:{port}".format(port=crate_port)
crate_uri = "http://%s" % crate_host


def setUp(test):
    test.globs['cmd'] = CrateTestCmd(error_trace=True, is_tty=False)


def test_suite():
    suite = unittest.TestSuite()
    flags = (doctest.NORMALIZE_WHITESPACE | doctest.ELLIPSIS)
    s = doctest.DocFileSuite(
        'usage.txt', 'output.txt',
        setUp=setUp,
        optionflags=flags,
        parser=crash_parser,
        encoding='utf-8'
    )
    s.layer = crate_layer
    suite.addTest(s)
    CommandTest.layer = crate_layer
    CommandTest.crate_host = crate_host
    suite.addTest(unittest.makeSuite(CommandTest))
    suite.addTest(unittest.makeSuite(OutputWriterTest))
    suite.addTest(unittest.makeSuite(SysInfoTest))
    suite.addTest(unittest.makeSuite(ReadFileCommandTest))
    suite.addTest(unittest.makeSuite(ToggleAutocompleteCommandTest))
    suite.addTest(unittest.makeSuite(ChecksCommandTest))
    suite.addTest(unittest.makeSuite(SQLCompleterTest))
    suite.addTest(unittest.makeSuite(ConfigurationTest))

    return suite
