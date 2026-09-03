"""In-memory MJPEG frame buffer.

The ingest pipeline pipes raw MJPEG bytes from ffmpeg stdout. This module parses
the concatenated JPEG stream, keeps a small ring of the most recent frames for
snapshots, tracks arrival statistics (fps, jitter, bitrate) and serves live
previews as an async generator so any number of consumers share one pipe.
"""

import asyncio
import time
from collections import deque
from typing import AsyncIterator

SOI = b"\xff\xd8"
EOI = b"\xff\xd9"


class MjpegBuffer:
    """Single-consumer-safe latest-frame store plus subscribe iterator."""

    def __init__(self, max_frames: int = 2) -> None:
        self._max_frames = max(1, max_frames)
        self._frames: deque[bytes] = deque(maxlen=self._max_frames)
        self._arrivals: deque[float] = deque(maxlen=200)
        self._bytes_window: deque[tuple[float, int]] = deque()
        self._last_frame_ts: float | None = None
        self._lock = asyncio.Lock()

    @property
    def last_frame_at(self) -> float | None:
        return self._last_frame_ts

    async def push(self, frame: bytes) -> None:
        """Store a parsed JPEG frame and update arrival statistics."""
        async with self._lock:
            now = time.monotonic()
            self._frames.append(frame)
            self._arrivals.append(now)
            self._bytes_window.append((now, len(frame)))
            while self._bytes_window and self._bytes_window[0][0] < now - 1.0:
                self._bytes_window.popleft()
            self._last_frame_ts = now

    async def get_latest(self) -> bytes | None:
        async with self._lock:
            return self._frames[-1] if self._frames else None

    async def stats(self) -> dict:
        """Rolling 1-second / lifetime statistics for this session."""
        async with self._lock:
            now = time.monotonic()
            recent = [t for t in self._arrivals if t >= now - 1.0]
            arrivals = list(self._arrivals)
            window_bytes = sum(size for _t, size in self._bytes_window)
            fps = len(recent)
            if len(arrivals) >= 2:
                intervals = [b - a for a, b in zip(arrivals[:-1], arrivals[1:])]
                avg = sum(intervals) / len(intervals)
                jitter = sum(abs(i - avg) for i in intervals) / len(intervals) if intervals else 0.0
            else:
                jitter = 0.0
            age = (now - self._last_frame_ts) if self._last_frame_ts else None
            return {
                "frames": len(self._frames),
                "fps": fps,
                "bitrate_kbps": round(window_bytes * 8 / 1024, 1) if window_bytes else 0.0,
                "jitter_ms": round(jitter * 1000, 2),
                "last_frame_age_ms": round(float(age or 0.0) * 1000, 1),
            }


async def iter_frames(buffer: MjpegBuffer, *, fps: int | None = None) -> AsyncIterator[bytes]:
    """Continuously yield the newest buffered frame.

    Consumers that are slower than the ingest rate simply skip frames — this
    keeps every preview client in near-real-time without back-pressure.
    """
    fps = fps or 15
    interval = 1.0 / max(1, fps)
    while True:
        frame = await buffer.get_latest()
        if frame is not None:
            yield frame
        await asyncio.sleep(interval)


def extract_jpegs(data: bytes, carry: bytearray) -> list[bytes]:
    """Split a raw pipe chunk into complete JPEG frames.

    `carry` retains a partial frame between chunks. Returns an empty list when
    the chunk contains no complete frame.
    """
    carry.extend(data)
    frames: list[bytes] = []
    while True:
        start = carry.find(SOI)
        if start == -1:
            carry.clear()
            break
        end = carry.find(EOI, start + 2)
        if end == -1:
            # Keep only the trailing partial candidate
            del carry[:start]
            break
        end += 2
        frames.append(bytes(carry[start:end]))
        del carry[:end]
    return frames


__all__ = ["MjpegBuffer", "iter_frames", "extract_jpegs", "SOI", "EOI"]