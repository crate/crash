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

from prompt_toolkit.filters import IsDone, HasFocus, RendererHeightIsKnown, to_cli_filter, Condition
from prompt_toolkit.enums import DEFAULT_BUFFER, SEARCH_BUFFER
from prompt_toolkit.token import Token
from prompt_toolkit.layout import Window, HSplit, VSplit, Float
from prompt_toolkit.layout.containers import ConditionalContainer, FloatContainer
from prompt_toolkit.layout.dimension import LayoutDimension
from prompt_toolkit.layout.controls import TokenListControl, BufferControl, FillControl
from prompt_toolkit.layout.lexers import PygmentsLexer
from prompt_toolkit.layout.screen import Char
from prompt_toolkit.layout.menus import CompletionsMenu
from prompt_toolkit.layout.processors import ConditionalProcessor, HighlightSearchProcessor
from prompt_toolkit.layout.toolbars import TokenListToolbar, SearchToolbar
from prompt_toolkit.layout.margins import PromptMargin, ConditionalMargin
from prompt_toolkit.layout.utils import token_list_width

""" Creates a custom `Layout` for the Crash input REPL

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
def create_layout(message='', lexer=None,
                  reserve_space_for_menu=8,
                  get_prompt_tokens=None,
                  get_bottom_toolbar_tokens=None,
                  extra_input_processors=None, multiline=False,
                  wrap_lines=True):

    # Create processors list.
    input_processors = [
        ConditionalProcessor(
            # Highlight the reverse-i-search buffer
            HighlightSearchProcessor(preview_search=True),
            HasFocus(SEARCH_BUFFER)),
    ]

    if extra_input_processors:
        input_processors.extend(extra_input_processors)

    lexer = PygmentsLexer(lexer, sync_from_start=True)
    multiline = to_cli_filter(multiline)

    sidebar_token = [
        (Token.Toolbar.Status.Key, "[ctrl+d]"),
        (Token.Toolbar.Status, " Exit")
    ]
    sidebar_width = token_list_width(sidebar_token)

    get_prompt_tokens = lambda _: [(Token.Prompt, message)]
    get_sidebar_tokens = lambda _: sidebar_token

    def get_height(cli):
        # If there is an autocompletion menu to be shown, make sure that our
        # layout has at least a minimal height in order to display it.
        if reserve_space_for_menu and not cli.is_done:
            buff = cli.current_buffer

            # Reserve the space, either when there are completions, or when
            # `complete_while_typing` is true and we expect completions very
            # soon.
            if buff.complete_while_typing() or buff.complete_state is not None:
                return LayoutDimension(min=reserve_space_for_menu)

        return LayoutDimension()

    # Create and return Container instance.
    return HSplit([
        VSplit([
            HSplit([
                # The main input, with completion menus floating on top of it.
                FloatContainer(
                    HSplit([
                        Window(
                            BufferControl(
                                input_processors=input_processors,
                                lexer=lexer,
                                # enable preview search for reverse-i-search
                                preview_search=True),
                            get_height=get_height,
                            wrap_lines=wrap_lines,
                            left_margins=[
                                # In multiline mode, use the window margin to display
                                # the prompt and continuation tokens.
                                ConditionalMargin(
                                    PromptMargin(get_prompt_tokens),
                                    filter=multiline
                                )
                            ],
                        ),
                    ]),
                    [
                        # Completion menu
                        Float(xcursor=True,
                            ycursor=True,
                            content=CompletionsMenu(
                                max_height=16,
                                scroll_offset=1,
                                extra_filter=HasFocus(DEFAULT_BUFFER))),
                    ]
                ),

                # reverse-i-search toolbar (ctrl+r)
                ConditionalContainer(SearchToolbar(), multiline),
            ])
        ]),
    ] + [
        VSplit([
            # Left-Aligned Session Toolbar
            ConditionalContainer(
                Window(
                    TokenListControl(get_bottom_toolbar_tokens),
                    height=LayoutDimension.exact(1)
                ),
                filter=~IsDone() & RendererHeightIsKnown()),

            # Right-Aligned Container
            ConditionalContainer(
                Window(
                    TokenListControl(get_sidebar_tokens),
                    height=LayoutDimension.exact(1),
                    width=LayoutDimension.exact(sidebar_width)
                ),
                filter=~IsDone() & RendererHeightIsKnown())
        ])
    ])
