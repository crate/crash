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


import re

from prompt_toolkit.filters import Condition
from prompt_toolkit.keys import Keys

TAB_WIDTH = 4
WHITESPACE_RE = re.compile(r'\s+$')


def mk_filter(buf, fn):
    @Condition
    def call_fn():
        return fn(buf.document)

    return call_fn


def _is_start_of_multiline(doc):
    return doc.text and not doc.get_word_before_cursor()


def _line_ends_with_tab(doc):
    trailing_ws = WHITESPACE_RE.findall(doc.current_line_before_cursor)
    return (
        not doc.get_word_before_cursor()
        and trailing_ws
        and len(trailing_ws[0]) % TAB_WIDTH == 0
    )


def bind_keys(buf, key_bindings):

    handle = key_bindings.add

    @handle('c-d')
    def exit_(event):
        event.app.exit(exception=EOFError, style='class:exiting')

    @handle('c-c')
    def interrupt_(event):
        event.app.exit(exception=KeyboardInterrupt, style='class:aborting')

    @handle('c-z')
    def suspend_(event):
        event.app.suspend_to_background()

    @handle(Keys.Tab, filter=mk_filter(buf, _is_start_of_multiline))
    def on_tab(event):
        event.cli.current_buffer.insert_text(' ' * TAB_WIDTH)

    @handle(Keys.Backspace, filter=mk_filter(buf, _line_ends_with_tab))
    def on_backspace(event):
        event.cli.current_buffer.delete_before_cursor(TAB_WIDTH)
