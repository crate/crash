from tabulate import DataRow, Line as TabulateLine, TableFormat, _strip_ansi

crate_fmt = TableFormat(lineabove=TabulateLine("+", "-", "+", "+"),
                        linebelowheader=TabulateLine("+", "-", "+", "+"),
                        linebetweenrows=None,
                        linebelow=TabulateLine("+", "-", "+", "+"),
                        headerrow=DataRow("|", "|", "|"),
                        datarow=DataRow("|", "|", "|"),
                        padding=1,
                        with_header_hide=None)


def _format(val, valtype, floatfmt, intfmt="", missingval="", has_invisible=True):
    """Format a value according to its type.

    Unicode is supported:

    >>> hrow = ['\u0431\u0443\u043a\u0432\u0430', '\u0446\u0438\u0444\u0440\u0430'] ; \
        tbl = [['\u0430\u0437', 2], ['\u0431\u0443\u043a\u0438', 4]] ; \
        good_result = '\\u0431\\u0443\\u043a\\u0432\\u0430      \\u0446\\u0438\\u0444\\u0440\\u0430\\n-------  -------\\n\\u0430\\u0437             2\\n\\u0431\\u0443\\u043a\\u0438           4' ; \
        tabulate(tbl, headers=hrow) == good_result
    True

    """  # noqa
    if val is None:
        return missingval

    if valtype in (int, str):
        return "{0}".format(val)
    elif valtype is bytes:
        try:
            return str(val, "ascii")
        except TypeError:
            return str(val)
    elif valtype is float:
        is_a_colored_number = has_invisible and isinstance(
            val, (str, bytes)
        )
        if is_a_colored_number:
            raw_val = _strip_ansi(val)
            formatted_val = format(float(raw_val), floatfmt)
            return val.replace(raw_val, formatted_val)
        # PATCH: Preserve string formatting even for numeric looking values.
        # https://github.com/crate/crash/commit/1052e0d79
        elif not floatfmt:
            return str(val)
        else:
            return format(float(val), floatfmt)
    else:
        return "{0}".format(val)


def monkeypatch():
    import tabulate

    # Register custom table format.
    tabulate._table_formats["cratedb"] = crate_fmt
    tabulate.multiline_formats["cratedb"] = "cratedb"

    # Module-level patch for more compact output.
    # https://github.com/astanin/python-tabulate/issues/116
    tabulate.MIN_PADDING = 0

    # Override original `_format` helper function to make output format
    # of float values consistent. See `PATCH` marker.
    # Reference: https://github.com/crate/crash/commit/1052e0d79.
    tabulate._format = _format
