"""Asynchronous event bus for realtime inference event fan-out.

In-process asyncio pub/sub hub. Channels are named topics (`overlay`,
`stats`, `alert`, `run`); payloads are JSON-safe dicts. Subscribers create a
bounded queue and are dropped (with a warning) when they fail to keep up, so a
slow WebSocket client can never stall the inference loop.
"""

from __future__ import annotations

from asyncio import Queue, QueueEmpty, QueueFull
from collections import defaultdict
from typing import Any

from src.core.logging import log

MAX_QUEUE = 128


class EventBus:
    """Topic-based in-process event hub."""

    def __init__(self) -> None:
        self._subs: dict[str, list[Queue[dict[str, Any]]]] = defaultdict(list)

    def subscribe(self, channel: str, *, maxsize: int = MAX_QUEUE) -> Queue[dict[str, Any]]:
        queue: Queue[dict[str, Any]] = Queue(maxsize=maxsize)
        self._subs[channel].append(queue)
        return queue

    def unsubscribe(self, channel: str, queue: Queue[dict[str, Any]]) -> None:
        subs = self._subs.get(channel)
        if subs is not None:
            try:
                subs.remove(queue)
            except ValueError:
                return
            if not subs:
                self._subs.pop(channel, None)

    async def publish(self, channel: str, payload: dict[str, Any]) -> None:
        subs = list(self._subs.get(channel, []))
        for queue in subs:
            try:
                queue.put_nowait(payload)
            except QueueFull:
                # Drop the oldest entry so the subscriber always gets fresh
                # realtime state rather than a backlog.
                try:
                    queue.get_nowait()
                except QueueEmpty:
                    continue
                try:
                    queue.put_nowait(payload)
                except QueueFull:
                    log.warning("ai.event.subscriber_overloaded", channel=channel)
        if channel == "alert" and subs:
            log.debug("ai.event.published", channel=channel, subscribers=len(subs))

    async def subscribe_many(
        self, channels: list[str]
    ) -> tuple[list[str], list[Queue[dict[str, Any]]]]:
        return channels, [self.subscribe(ch) for ch in channels]


__all__ = ["EventBus"]