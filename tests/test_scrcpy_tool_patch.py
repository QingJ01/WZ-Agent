"""Tests for the ScrcpyTool stream-loop compatibility patch."""

from __future__ import annotations

import scrcpy

from wzry_ai.device.ScrcpyTool import (
    _patched_deploy_server,
    _patched_init_server_connection,
    _patched_stream_loop,
)


class _BlockingSocket:
    def recv(self, _size):
        raise BlockingIOError()


class _EmptyThenBlockingSocket:
    def __init__(self):
        self.calls = 0

    def recv(self, _size):
        self.calls += 1
        if self.calls == 1:
            return b""
        raise BlockingIOError()


class _FakeClient:
    def __init__(self, socket=None):
        self.alive = True
        self.block_frame = False
        self.flip = False
        self._Client__video_socket = socket or _BlockingSocket()
        self.events = []

    def _Client__send_to_listeners(self, event, frame=None):
        self.events.append((event, frame))
        self.alive = False

    def stop(self):
        self.alive = False


class _FakeSocket:
    def __init__(self):
        self.blocking = True
        self.closed = False

    def setblocking(self, value):
        self.blocking = value

    def close(self):
        self.closed = True


class _FakeDevice:
    serial = "fake-serial"

    def __init__(self):
        self.push_calls = []
        self.shell_calls = []
        self.connections = []
        self.sockets = [_FakeSocket(), _FakeSocket()]

    def push(self, source, target):
        self.push_calls.append((source, target))

    def shell(self, commands, stream=False):
        self.shell_calls.append((commands, stream))
        return "server-stream"

    def create_connection(self, namespace, name):
        self.connections.append((namespace, name))
        return self.sockets[len(self.connections) - 1]


class _FakeLocalClient:
    def __init__(self):
        self._wzry_use_local_scrcpy_server = True
        self._wzry_local_scrcpy_server_path = "D:/project/wzry_ai/scrcpy/scrcpy-server"
        self._wzry_local_scrcpy_server_version = "3.3.4"
        self.device = _FakeDevice()
        self.max_width = 1920
        self.max_fps = 30
        self.bitrate = 8000000
        self.connection_timeout = 3000
        self.control_socket = None
        self.device_name = None
        self.resolution = None


def test_patched_stream_loop_treats_blocking_io_as_empty_frame():
    client = _FakeClient()

    _patched_stream_loop(client)

    assert client.events == [(scrcpy.EVENT_FRAME, None)]


def test_patched_stream_loop_treats_empty_reads_as_empty_frame():
    client = _FakeClient(socket=_EmptyThenBlockingSocket())

    _patched_stream_loop(client)

    assert client.events == [(scrcpy.EVENT_FRAME, None)]


def test_patched_deploy_server_uses_local_official_raw_stream():
    client = _FakeLocalClient()

    _patched_deploy_server(client)

    assert client.device.push_calls == [
        (
            "D:/project/wzry_ai/scrcpy/scrcpy-server",
            "/data/local/tmp/scrcpy-server.jar",
        )
    ]
    commands, stream = client.device.shell_calls[0]
    assert stream is True
    assert "com.genymobile.scrcpy.Server" in commands
    assert "3.3.4" in commands
    assert "raw_stream=true" in commands
    assert "control=true" in commands
    assert "audio=false" in commands
    assert "video_codec=h264" in commands
    assert "max_size=1920" in commands
    assert "max_fps=30" in commands
    assert "video_bit_rate=8000000" in commands
    assert getattr(client, "_Client__server_stream") == "server-stream"


def test_patched_init_server_connection_uses_two_raw_stream_sockets():
    client = _FakeLocalClient()

    _patched_init_server_connection(client)

    assert len(client.device.connections) == 2
    assert client.device.connections[0][1] == "scrcpy"
    assert client.device.connections[1][1] == "scrcpy"
    assert getattr(client, "_Client__video_socket") is client.device.sockets[0]
    assert client.control_socket is client.device.sockets[1]
    assert client.device.sockets[0].blocking is False
    assert client.device_name == "fake-serial"
    assert client.resolution is None
