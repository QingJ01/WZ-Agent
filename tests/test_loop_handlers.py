"""Tests for main-loop frame helpers."""

from __future__ import annotations

import numpy as np

from wzry_ai.app.loop_handlers import LoopHandlers, MinimapPreviewWriter


def test_prepare_state_detection_frame_converts_bgr_to_gray():
    frame = np.zeros((4, 6, 3), dtype=np.uint8)
    frame[:, :, 2] = 255

    gray_frame, bgr_frame = LoopHandlers._prepare_state_detection_frame(frame)

    assert gray_frame.shape == (4, 6)
    assert gray_frame.dtype == np.uint8
    assert bgr_frame is frame


def test_prepare_state_detection_frame_keeps_gray_frame():
    frame = np.zeros((4, 6), dtype=np.uint8)

    gray_frame, bgr_frame = LoopHandlers._prepare_state_detection_frame(frame)

    assert gray_frame is frame
    assert bgr_frame is None


def test_minimap_preview_writer_writes_png_atomically(tmp_path):
    path = tmp_path / "preview" / "minimap.png"
    writer = MinimapPreviewWriter(path=path, enabled=True, interval=0.0)
    image = np.zeros((12, 18, 3), dtype=np.uint8)
    image[:, :, 1] = 255

    assert writer.write(image, now=1.0) is True

    assert path.exists()
    assert not (tmp_path / "preview" / "minimap.tmp.png").exists()
    assert path.read_bytes().startswith(b"\x89PNG")


def test_minimap_preview_writer_respects_interval(tmp_path):
    path = tmp_path / "minimap.png"
    writer = MinimapPreviewWriter(path=path, enabled=True, interval=1.0)
    image = np.zeros((4, 4, 3), dtype=np.uint8)

    assert writer.write(image, now=1.0) is True
    assert writer.write(image, now=1.2) is False
