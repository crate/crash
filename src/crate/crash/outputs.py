import csv
import json
import sys

from pygments import highlight
from pygments.lexers.data import JsonLexer
from pygments.formatters import TerminalFormatter
from colorama import Fore, Style

from .tabulate import TableFormat, Line as TabulateLine, DataRow, tabulate, float_format

if sys.version_info[:2] == (2, 6):
    OrderedDict = dict
else:
    from collections import OrderedDict


NULL = u'NULL'
TRUE = u'TRUE'
FALSE = u'FALSE'

crate_fmt = TableFormat(lineabove=TabulateLine("+", "-", "+", "+"),
                        linebelowheader=TabulateLine("+", "-", "+", "+"),
                        linebetweenrows=None,
                        linebelow=TabulateLine("+", "-", "+", "+"),
                        headerrow=DataRow("|", "|", "|"),
                        datarow=DataRow("|", "|", "|"),
                        padding=1,
                        with_header_hide=None)


def _val_len(v):
    if not v:
        return 4  # will be displayed as NULL
    if isinstance(v, (list, dict)):
        return len(json.dumps(v))
    if hasattr(v, '__len__'):
        return len(v)
    return len(str(v))


def _transform_field(field):
    """transform field for displaying"""
    if isinstance(field, bool):
        return TRUE if field else FALSE
    elif isinstance(field, (list, dict)):
        return json.dumps(field, sort_keys=True, ensure_ascii=False)
    else:
        return field


class OutputWriter(object):

    def __init__(self, writer, is_tty):
        self.is_tty = is_tty
        self._json_lexer = JsonLexer()
        self._formatter = TerminalFormatter()
        self.writer = writer
        self._output_format = 'tabular'
        self._formats = {
            'tabular': self.tabular,
            'json': self.json,
            'csv': self.csv,
            'raw': self.raw,
            'mixed': self.mixed,
            'dynamic': self.dynamic,
            'json_row': self.json_row
        }

    @property
    def formats(self):
        return self._formats.keys()

    @property
    def output_format(self):
        return self._output_format

    @output_format.setter
    def output_format(self, fmt):
        if fmt not in self.formats:
            raise ValueError('format: {0} is invalid. Valid formats are: {1}')
        self._output_format = fmt

    def to_json_str(self, obj, **kwargs):
        json_str = json.dumps(obj, indent=2, **kwargs)
        if self.is_tty:
            return highlight(json_str, self._json_lexer, self._formatter).rstrip('\n')
        return json_str

    def write(self, result):
        output_f = self._formats[self.output_format]
        output = output_f(result)
        if output:
            for line in output:
                self.writer.write(line)
        self.writer.write('\n')

    def raw(self, result):
        duration = result.duration
        yield self.to_json_str(dict(
            rows=result.rows,
            cols=result.cols,
            rowcount=result.rowcount,
            duration=duration > -1 and float(duration) / 1000.0 or duration,
        ))

    def tabular(self, result):
        rows = [list(map(_transform_field, row)) for row in result.rows]
        return tabulate(rows,
                        headers=result.cols,
                        tablefmt=crate_fmt,
                        floatfmt="",
                        missingval=NULL)

    def mixed(self, result):
        padding = max_col_len = max(len(c) for c in result.cols)
        if self.is_tty:
            max_col_len += len(Fore.YELLOW + Style.RESET_ALL)
        tmpl = '{0:<' + str(max_col_len) + '} | {1}'
        row_delimiter = '-' * result.output_width
        for row in result.rows:
            for i, c in enumerate(result.cols):
                val = self._mixed_format(row[i], max_col_len, padding)
                if self.is_tty:
                    c = Fore.YELLOW + c + Style.RESET_ALL
                yield tmpl.format(c, val)
            yield row_delimiter + '\n'

    def json(self, result):
        obj = [OrderedDict(zip(result.cols, x)) for x in result.rows]
        yield self.to_json_str(obj)

    def csv(self, result):
        wr = csv.writer(self.writer, doublequote=False, escapechar='\\', quotechar="'")
        wr.writerow(result.cols)

        def json_dumps(r):
            t = type(r)
            return json.dumps(r, sort_keys=True) if t == dict or t == list else r

        for row in iter(result.rows):
            wr.writerow(list(map(json_dumps, row)))

    def dynamic(self, result):
        max_cols_required = sum(len(c) + 4 for c in result.cols) + 1
        for row in result.rows:
            cols_required = sum(_val_len(v) + 4 for v in row) + 1
            if cols_required > max_cols_required:
                max_cols_required = cols_required
        if max_cols_required > result.output_width:
            return self.mixed(result)
        else:
            return self.tabular(result)

    def json_row(self, result):
        rows = (json.dumps(dict(zip(result.cols, x))) for x in result.rows)
        for row in rows:
            if self.is_tty:
                yield highlight(row, self._json_lexer, self._formatter)
            else:
                yield row + '\n'

    def _mixed_format(self, value, max_col_len, padding):
        if value is None:
            value = NULL
        elif isinstance(value, (list, dict)):
            self.to_json_str(value, sort_keys=True)
            json_str = json.dumps(value, indent=2, sort_keys=True)
            lines = json_str.split('\n')
            lines[-1] = ' ' + lines[-1]
            lines = [lines[0]] + [' ' * padding + ' |' + l for l in lines[1:]]
            value = '\n'.join(lines)
        elif isinstance(value, float):
            value = float_format(value)
        return '{0}\n'.format(value)
