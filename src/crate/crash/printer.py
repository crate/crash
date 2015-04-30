# -*- coding: utf-8 -*-
# vim: set fileencodings=utf-8
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

from __future__ import print_function

import sys
from colorama import init, Fore, Style

init(autoreset=True)


class PrintWrapper(object):
    """
    Wraps the ``print`` function into a write method,
    so it can be used as a file-like write-only object.
    """

    def open(self):
        pass

    def write(self, line, end=''):
        try:
            print(line, end=end)
        except UnicodeEncodeError:
            try:
                print(line.encode('utf-8').decode('ascii', 'replace'), end=end)
            except UnicodeEncodeError:
                print(line.encode('utf-8').decode('ascii', 'ignore'), end=end)
            print('WARNING: Unicode characters found that cannot be displayed. Check your system locale.')

    def close(self):
        pass

    def isatty(self):
        return False


class ColorPrinter(object):
    """
    Print in color if interactive tty
    """

    def __init__(self, is_tty=None, stream=sys.stderr, line_end='\n'):
        self.stream = stream
        self.pretty = is_tty is None and stream.isatty() or is_tty
        self.line_end = line_end

    def log(self, content, color, style=''):
        if self.pretty:
            self.stream.write(color + style + content + self.line_end)
        else:
            self.stream.write(content + self.line_end)

    def info(self, content):
        self.log(content, Fore.GREEN)

    def warn(self, content):
        self.log(content, Fore.YELLOW)

    def critical(self, content):
        self.log(content, Fore.RED, style=Style.BRIGHT)
