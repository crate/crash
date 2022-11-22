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

import configparser
import os
import tempfile
from unittest import TestCase

from crate.crash.command import CONFIG_PATH, parse_config_path
from crate.crash.config import Configuration, ConfigurationError


class ConfigurationTest(TestCase):

    def setUp(self):
        self.tmp_dir = tempfile.mkdtemp()

    def test_parse_config_path(self):
        # no --config argument
        argv = ['crash']
        config = parse_config_path(argv)
        self.assertEqual(CONFIG_PATH, config)
        self.assertEqual(['crash'], argv)
        # --config with no value
        argv = ['crash', '--config']
        config = parse_config_path(argv)
        self.assertEqual(CONFIG_PATH, config)
        self.assertEqual(['crash'], argv)
        # --config argument with value
        path = '/path/to/config/cfg'
        argv = ['crash', '--config', path]
        config = parse_config_path(argv)
        self.assertEqual(path, config)
        self.assertEqual(['crash'], argv)

    def test_invalid_config(self):
        with self.assertRaises(ConfigurationError) as cm:
            path = os.path.join(self.tmp_dir, 'invalid')
            Configuration(path)  # noqa: F841 - creating instance fails
        self.assertEqual(str(cm.exception),
                         'Path to configuration file needs to end with .cfg')

    def test_create_config(self):
        path = os.path.join(self.tmp_dir, 'foo.cfg')
        self.assertFalse(os.path.exists(path))
        conf = Configuration(path)
        self.assertTrue(os.path.exists(path))
        self.assertTrue(os.path.exists(conf.path))
        self.assertIn('crash', conf.cfg.sections())

    def test_init_doesnt_override(self):
        path = os.path.join(self.tmp_dir, 'bar.cfg')
        conf_a = Configuration(path)
        conf_a.save()
        with open(conf_a.path, 'a+') as fp:
            fp.write('key = value')

        conf_b = Configuration(path)
        with open(conf_a.path) as fp_a:
            with open(conf_b.path) as fp_b:
                self.assertEqual(fp_a.read(), fp_b.read())

    def test_read_values(self):
        path = os.path.join(self.tmp_dir, 'foobar.cfg')
        config = configparser.ConfigParser()
        config.add_section('crash')
        config.set('crash', 'my_option', 'value')
        with open(path, 'w') as fp:
            config.write(fp)

        conf = Configuration(path)
        self.assertEqual('value',
                         conf.get_or_set('my_option', None))
        self.assertEqual(None,
                         conf.get_or_set('my_other_option', None))
        self.assertEqual('value',
                         conf.get_or_set('my_other_option', 'value'))

    def test_get_and_set(self):
        path = os.path.join(self.tmp_dir, 'crash.cfg')

        conf = Configuration(path)
        conf.get_or_set('format', 'json')
        conf.get_or_set('verbosity', 3)
        conf.get_or_set('autocomplete', False)
        conf.get_or_set('hosts', ['c1', 'c2'])
        conf.get_or_set('force_passwd_prompt', 0)
        conf.save()

        # Reading raw values
        config = configparser.ConfigParser()
        config.read([path])
        self.assertEqual(config.get('crash', 'format'), 'json')
        self.assertEqual(config.get('crash', 'verbosity'), '3')
        self.assertEqual(config.get('crash', 'autocomplete'), '0')
        self.assertEqual(config.get('crash', 'hosts'), 'c1\nc2')
        self.assertEqual(config.get('crash', 'force_passwd_prompt'), '0')

        # Reading transformed values
        conf = Configuration(path)
        self.assertEqual(conf.get_or_set('format', 'mixed'), 'json')
        self.assertEqual(conf.get_or_set('verbosity', 0), 3)
        self.assertEqual(conf.get_or_set('autocomplete', True), False)
        self.assertEqual(conf.get_or_set('hosts', ['localhost']), ['c1', 'c2'])
        self.assertEqual(conf.get_or_set('force_passwd_prompt', True), False)

        # Reading section header
        with open(path) as fp:
            self.assertTrue(fp.read().startswith('[crash]'))

    def test_read_boolean(self):
        path = os.path.join(self.tmp_dir, 'bwc.cfg')

        conf = Configuration(path)
        conf.get_or_set('bwc_true', 'True')
        conf.get_or_set('bwc_false', 'False')
        conf.save()

        conf = Configuration(path)
        self.assertEqual(conf.get_or_set('bwc_true', True), True)
        self.assertEqual(conf.get_or_set('bwc_false', False), False)
