"""Tests for the ScrcpyTool stream-loop compatibility patch."""

from __future__ import annotations

import scrcpy

from wzry_ai.device.ScrcpyTool import _patched_stream_loop


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


def test_patched_stream_loop_treats_blocking_io_as_empty_frame():
    client = _FakeClient()

    _patched_stream_loop(client)

    assert client.events == [(scrcpy.EVENT_FRAME, None)]


def test_patched_stream_loop_treats_empty_reads_as_empty_frame():
    client = _FakeClient(socket=_EmptyThenBlockingSocket())

    _patched_stream_loop(client)

    assert client.events == [(scrcpy.EVENT_FRAME, None)]
