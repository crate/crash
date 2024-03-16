from unittest.mock import Mock

from crate.client.cursor import Cursor


def mocked_cursor(description, records, duration=0.1):
    """
    Provide a mocked `crate.client.cursor.Cursor` instance.
    """
    rowcount = len(records)
    fake_cursor = Mock(name='fake_cursor', description=description, rowcount=rowcount, duration=duration)
    fake_cursor.fetchall.return_value = records
    FakeCursor = Mock(name='FakeCursor', spec=Cursor)
    FakeCursor.return_value = fake_cursor
    return FakeCursor


def fake_cursor():
    """
    Provide an empty/minimal mocked cursor object,
    that just works if you do not care about results.
    """
    return mocked_cursor(description=[('undef',)], records=[('undef', None)])
