# vim: set fileencodings=utf-8
# -*- coding: utf-8; -*-
# PYTHON_ARGCOMPLETE_OK
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


import os
try:
    import configparser
except ImportError:
    import ConfigParser as configparser


class ConfigurationError(Exception):
    pass


class Configuration(object):
    """
    Model that reads default values for the CLI argument parser
    from a configuration file.
    """

    def __init__(self, path):
        if not path.endswith('.cfg'):
            raise ConfigurationError('Path to configuration file needs to end with .cfg')
        self.path = path
        self.cfg = configparser.ConfigParser()
        self.read_and_create_if_necessary()
        self.add_crash_section_if_necessary()

    def read_and_create_if_necessary(self):
        dir = os.path.dirname(self.path)
        if dir and not os.path.exists(dir):
            os.makedirs(dir)
        if not os.path.exists(self.path):
            self.save()
        self.cfg.read(self.path)

    def add_crash_section_if_necessary(self):
        if 'crash' not in self.cfg.sections():
            self.cfg.add_section('crash')

    def get_or_set(self, key, default_value=None):
        assert 'crash' in self.cfg.sections()
        value = None
        try:
            value = self.cfg.get('crash', str(key))
        except configparser.NoOptionError:
            if default_value is not None:
                self.cfg.set('crash', key, str(default_value))
        return value or default_value

    def save(self):
        with open(self.path, 'w') as fp:
            self.cfg.write(fp)

