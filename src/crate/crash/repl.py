import os

from pygments.lexers.sql import SqlLexer
from pygments.style import Style
from pygments.token import (Keyword,
                            Comment,
                            Operator,
                            Number,
                            Literal,
                            String,
                            Error)

from prompt_toolkit.completion import Completer, Completion
from prompt_toolkit.history import FileHistory
from prompt_toolkit.buffer import Buffer
from prompt_toolkit.filters import Condition, IsDone, HasFocus, Always
from prompt_toolkit import CommandLineInterface, AbortAction, Application
from prompt_toolkit.interface import AcceptAction
from prompt_toolkit.styles import PygmentsStyle
from prompt_toolkit.enums import DEFAULT_BUFFER
from prompt_toolkit.layout.processors import (
    HighlightMatchingBracketProcessor,
    ConditionalProcessor
)
from prompt_toolkit.key_binding.manager import KeyBindingManager
from prompt_toolkit.shortcuts import (create_prompt_layout,
                                      create_output,
                                      create_eventloop)

from .commands import Command


MAX_HISTORY_LENGTH = 10000


def _enable_vi_mode():
    files = ['/etc/inputrc', os.path.expanduser('~/.inputrc')]
    for filepath in files:
        try:
            with open(filepath, 'r') as f:
                for line in f:
                    if line.strip() == 'set editing-mode vi':
                        return True
        except IOError:
            continue
    return False


class CrateStyle(Style):
    default_style = "noinherit"
    styles = {
        Keyword: 'bold #4b95a3',
        Comment: '#757265',
        Operator: '#e83131',
        Number: '#be61ff',
        Literal: '#ae81ff',
        String: '#f4a33d',
        Error: '#ff3300',
    }


class TruncatedFileHistory(FileHistory):

    def __init__(self, filename, max_length=1000):
        super(TruncatedFileHistory, self).__init__(filename)
        base = os.path.dirname(filename)
        if not os.path.exists(base):
            os.makedirs(base)
        if not os.path.exists(filename):
            with open(filename, 'a'):
                os.utime(filename, None)
        self.max_length = max_length

    def append(self, string):
        self.strings = self.strings[:max(0, self.max_length - 1)]
        super(TruncatedFileHistory, self).append(string)


class SQLCompleter(Completer):
    keywords = [
        "select", "insert", "update", "delete",
        "table", "index", "from", "into", "where", "values", "and", "or",
        "set", "with", "by", "using", "like",
        "boolean", "integer", "string", "float", "double", "short", "long",
        "byte", "timestamp", "ip", "object", "dynamic", "strict", "ignored",
        "array", "blob", "primary key",
        "analyzer", "extends", "tokenizer", "char_filters", "token_filters",
        "number_of_replicas", "clustered",
        "refresh", "alter",
        "sys", "doc", "blob",
    ]

    def __init__(self, cmd):
        self.cmd = cmd
        self.keywords += [kw.upper() for kw in self.keywords]

    def get_command_completions(self, line):
        if ' ' not in line:
            cmd = line[1:]
            return (i for i in self.cmd.commands.keys() if i.startswith(cmd))
        parts = line.split(' ', 1)
        cmd = parts[0].lstrip('\\')
        cmd = self.cmd.commands.get(cmd, None)
        if isinstance(cmd, Command):
            return cmd.complete(self.cmd, parts[1])
        return []

    def get_completions(self, document, complete_event):
        line = document.text
        word_before_cursor = document.get_word_before_cursor()
        if line.startswith('\\'):
            for w in self.get_command_completions(line):
                yield Completion(w, -len(word_before_cursor))
            return
        for keyword in self.keywords:
            if keyword.startswith(word_before_cursor):
                yield Completion(keyword, -len(word_before_cursor))


class CrashBuffer(Buffer):
    def __init__(self, *args, **kwargs):

        @Condition
        def is_multiline():
            doc = self.document
            if not doc.text:
                return False
            if doc.text.startswith('\\'):
                return False
            return not doc.text.rstrip().endswith(';')

        super(self.__class__, self).__init__(
            *args, is_multiline=is_multiline, **kwargs)


def loop(cmd, history_file):
    key_binding_manager = KeyBindingManager(
        enable_search=True,
        enable_abort_and_exit_bindings=True,
        enable_vi_mode=Condition(lambda cli: _enable_vi_mode()))

    layout = create_prompt_layout(
        message=u'cr> ',
        multiline=True,
        lexer=SqlLexer,
        extra_input_processors=[
            ConditionalProcessor(
                processor=HighlightMatchingBracketProcessor(chars='[](){}'),
                filter=HasFocus(DEFAULT_BUFFER) & ~IsDone())
        ]
    )
    cli_buffer = CrashBuffer(
        history=TruncatedFileHistory(history_file, max_length=MAX_HISTORY_LENGTH),
        accept_action=AcceptAction.RETURN_DOCUMENT,
        completer=SQLCompleter(cmd),
        complete_while_typing=Always()
    )
    application = Application(
        layout=layout,
        style=PygmentsStyle.from_defaults(pygments_style_cls=CrateStyle),
        buffer=cli_buffer,
        key_bindings_registry=key_binding_manager.registry,
        on_exit=AbortAction.RAISE_EXCEPTION,
        on_abort=AbortAction.RETRY,
    )
    eventloop = create_eventloop()
    output = create_output()
    cli = CommandLineInterface(
        application=application,
        eventloop=eventloop,
        output=output
    )

    def get_num_columns_override():
        return output.get_size().columns
    cmd.get_num_columns = get_num_columns_override

    while True:
        try:
            doc = cli.run()
            if doc:
                cmd.process(doc.text)
        except EOFError:
            cmd.logger.warn(u'Bye!')
            return
