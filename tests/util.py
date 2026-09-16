from unittest.mock import Mock

from verlib2 import Version

from crate.client.cursor import Cursor
from crate.client.exceptions import ConnectionError


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


def fake_connect():
    """
    Provide a mocked replacement for `crate.crash.command.connect`, so that
    instantiating a `CrateShell` in unit tests never opens real network
    connections to `localhost:4200`.

    The mock behaves like a connection to an unreachable server: the reported
    server version 0.0.0 makes `CrateShell.is_conn_available()` return False,
    and `cursor.execute()` raises `ConnectionError`. Tests that need a
    specific version set `cmd.connection.lowest_server_version` themselves;
    each `connect()` call yields a fresh connection, so such changes do not
    leak between tests.
    """
    def make_connection(*args, **kwargs):
        cursor = fake_cursor()()
        cursor.execute.side_effect = ConnectionError('mocked connection: no server available')
        connection = Mock(name='fake_connection')
        connection.lowest_server_version = Version('0.0.0')
        connection.cursor.return_value = cursor
        return connection
    return Mock(name='fake_connect', side_effect=make_connection)
