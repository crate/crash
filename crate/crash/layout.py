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

from prompt_toolkit.application import get_app
from prompt_toolkit.enums import DEFAULT_BUFFER, SEARCH_BUFFER
from prompt_toolkit.filters import has_focus, is_done, renderer_height_is_known
from prompt_toolkit.layout import Float, HSplit, Layout, VSplit, Window, WindowAlign
from prompt_toolkit.layout.containers import ConditionalContainer, FloatContainer
from prompt_toolkit.layout.controls import BufferControl, FormattedTextControl
from prompt_toolkit.layout.dimension import Dimension
from prompt_toolkit.layout.margins import ConditionalMargin, PromptMargin
from prompt_toolkit.layout.menus import CompletionsMenu
from prompt_toolkit.layout.processors import (
    ConditionalProcessor,
    HighlightSearchProcessor,
)
from prompt_toolkit.lexers import PygmentsLexer
from prompt_toolkit.widgets import SearchToolbar


def create_layout(buffer,
                  lexer=None,
                  reserve_space_for_menu=8,
                  get_prompt_tokens=None,
                  get_bottom_toolbar_tokens=None,
                  extra_input_processors=None,
                  multiline=False,
                  wrap_lines=True):
    """
    Creates a custom `Layout` for the Crash input REPL

    This layout includes:
        * a bottom left-aligned session toolbar container
        * a bottom right-aligned side-bar container

    +-------------------------------------------+
    | cr> select 1;                             |
    |                                           |
    |                                           |
    +-------------------------------------------+
    | bottom_toolbar_tokens      sidebar_tokens |
    +-------------------------------------------+
    """

    input_processors = [
        ConditionalProcessor(
            # Highlight the reverse-i-search buffer
            HighlightSearchProcessor(),
            has_focus(SEARCH_BUFFER)),
    ] + (extra_input_processors or [])
    lexer = PygmentsLexer(lexer, sync_from_start=True)
    sidebar_token = [
        ('class:status-toolbar', "[ctrl+d]"),
        ('class:status-toolbar.text', " Exit")
    ]

    def _get_buffer_control_height(buf):
        # If there is an autocompletion menu to be shown, make sure that our
        # layout has at least a minimal height in order to display it.
        if reserve_space_for_menu and not get_app().is_done:
            buff = buffer
            # Reserve the space, either when there are completions, or when
            # `complete_while_typing` is true and we expect completions very
            # soon.
            if buff.complete_while_typing() or buff.complete_state is not None:
                return Dimension(min=reserve_space_for_menu)

        return Dimension()

    search_toolbar = SearchToolbar()
    buf_ctrl_window = Window(
        BufferControl(
            buffer=buffer,
            search_buffer_control=search_toolbar.control,
            input_processors=input_processors,
            lexer=lexer,
            preview_search=True
        ),
        height=lambda: _get_buffer_control_height(buffer),
        wrap_lines=wrap_lines,
        left_margins=[
            ConditionalMargin(
                PromptMargin(get_prompt_tokens),
                filter=multiline
            )
        ]
    )
    in_out_area = VSplit([
        HSplit([
            FloatContainer(
                HSplit([buf_ctrl_window]),
                [
                    Float(
                        xcursor=True,
                        ycursor=True,
                        content=CompletionsMenu(
                            max_height=16,
                            scroll_offset=1,
                            extra_filter=has_focus(DEFAULT_BUFFER)
                        )
                    ),
                ]
            ),
            # reverse-i-search toolbar (ctrl+r)
            search_toolbar,
        ])
    ])
    bottom_toolbar = VSplit([
        ConditionalContainer(
            Window(
                FormattedTextControl(get_bottom_toolbar_tokens),
                height=Dimension.exact(1)
            ),
            filter=~is_done & renderer_height_is_known
        ),
        ConditionalContainer(
            Window(
                FormattedTextControl(lambda: sidebar_token),
                height=Dimension.exact(1),
                align=WindowAlign.RIGHT
            ),
            filter=~is_done & renderer_height_is_known
        )
    ])
    return Layout(HSplit([in_out_area, bottom_toolbar]))
