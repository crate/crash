import logging
import sys
from typing import Optional
from unittest.mock import Mock

from testcontainers.community.cratedb import CrateDBContainer
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


def setup_logging(level=logging.INFO):
    log_format = "%(asctime)-15s [%(name)-26s] %(levelname)-8s: %(message)s"
    logging.basicConfig(format=log_format, stream=sys.stderr, level=level)


class CrateDBTestAdapter:
    """
    A little helper wrapping Testcontainer's `CrateDBContainer`.
    """

    def __init__(self, crate_version: str = "nightly", **kwargs) -> None:
        self.cratedb: Optional[CrateDBContainer] = None
        if crate_version == "nightly":
            self.image = "crate/crate:nightly"
        else:
            self.image = "crate:{}".format(crate_version)

    def start(self, **kwargs) -> None:
        """
        Start container, used for tests set up
        """
        self.cratedb = CrateDBContainer(image=self.image, **kwargs)
        self.cratedb.start()

    def stop(self) -> None:
        """
        Stop container, used for tests tear down
        """
        if self.cratedb:
            self.cratedb.stop()

    def get_connection_url(self, *args, **kwargs) -> str:
        """
        Return a URL for SQLAlchemy DB engine
        """
        return self.cratedb.get_connection_url(*args, **kwargs)

    @property
    def http_url(self) -> str:
        """
        Return a URL for CrateDB's HTTP endpoint
        """
        return self.get_connection_url().replace("crate://", "http://")
