"""
Small helpers shared by the WebSocket-based voice services.

The HTTP services under `app.services.voice`/`voice2` stay untouched; this
module centralizes the transport bits needed to stream audio over
WebSocket instead of issuing single HTTP POST requests.
"""

from __future__ import annotations

import asyncio
import json
import time
from pathlib import Path
from typing import Any, BinaryIO, Coroutine, Iterable, Sequence, TypeVar

import websockets


class WebSocketExchangeError(RuntimeError):
    """Raised when a WebSocket round-trip fails."""


T = TypeVar("T")


def read_audio_bytes(source: str | Path | bytes | BinaryIO) -> bytes:
    """
    Normalize various audio inputs into raw bytes.
    Mirrors the helpers in the HTTP implementations to keep the public
    surface compatible.
    """
    if isinstance(source, (bytes, bytearray)):
        return bytes(source)
    if isinstance(source, (str, Path)):
        return Path(source).expanduser().read_bytes()
    if hasattr(source, "read"):
        data = source.read()
        if isinstance(data, str):
            return data.encode()
        return data
    raise TypeError(f"Unsupported audio source type: {type(source)!r}")


def iter_chunks(data: bytes, *, size: int = 8192) -> Iterable[bytes]:
    """Yield fixed-size chunks from `data` to avoid oversized frames."""
    for start in range(0, len(data), size):
        yield data[start : start + size]


async def stream_audio_over_websocket(
    url: str,
    *,
    headers: dict[str, str] | None,
    start_message: Any | None,
    stop_message: Any | None,
    audio_bytes: bytes,
    chunk_size: int = 8192,
    timeout: float = 60.0,
    terminal_events: Sequence[str] = ("final", "done", "result"),
) -> list[Any]:
    """
    Connects to `url`, sends an optional start message, streams the audio
    as binary frames, then sends an optional stop message. Returns all
    messages received until a terminal event is observed.
    """
    try:
        async with websockets.connect(
            url,
            extra_headers=headers,
            open_timeout=timeout,
            close_timeout=timeout,
        ) as websocket:
            if start_message is not None:
                await websocket.send(_serialize_if_needed(start_message))

            for chunk in iter_chunks(audio_bytes, size=chunk_size):
                await websocket.send(chunk)

            if stop_message is not None:
                await websocket.send(_serialize_if_needed(stop_message))

            messages: list[Any] = []
            deadline = time.monotonic() + timeout
            while True:
                remaining = max(0.0, deadline - time.monotonic())
                if remaining == 0:
                    raise WebSocketExchangeError("Timed out waiting for WebSocket response")
                try:
                    message = await asyncio.wait_for(websocket.recv(), timeout=remaining)
                except asyncio.TimeoutError as exc:  # pragma: no cover - defensive, depends on server behavior
                    raise WebSocketExchangeError("Timed out waiting for WebSocket response") from exc
                except websockets.WebSocketException as exc:
                    raise WebSocketExchangeError(f"WebSocket error: {exc}") from exc

                messages.append(message)
                if is_terminal_message(message, terminal_events):
                    break

            return messages
    except (OSError, websockets.WebSocketException) as exc:
        raise WebSocketExchangeError(f"WebSocket connection failed: {exc}") from exc


def parse_json_message(message: Any) -> dict[str, Any] | None:
    """Best-effort JSON parser for incoming WebSocket messages."""
    if isinstance(message, (bytes, bytearray)):
        return None
    try:
        return json.loads(message)
    except (TypeError, json.JSONDecodeError):
        return None


def is_terminal_message(message: Any, terminal_events: Sequence[str]) -> bool:
    """
    Determines whether `message` should stop the receive loop.
    Looks for common markers like type/event/status fields or `done=True`.
    """
    payload = parse_json_message(message)
    if not payload:
        return False

    markers = [
        str(payload.get("type") or "").lower(),
        str(payload.get("event") or "").lower(),
        str(payload.get("status") or "").lower(),
    ]
    markers = [marker for marker in markers if marker]

    terminal_set = {event.lower() for event in terminal_events}
    if any(marker in terminal_set for marker in markers):
        return True
    if payload.get("done") is True or payload.get("final") is True:
        return True
    return False


def run_coroutine(coro: Coroutine[Any, Any, T]) -> T:
    """
    Run a coroutine from sync code.
    Raises a friendly error if already inside a running event loop so the
    caller can switch to the async entrypoint instead of nesting loops.
    """
    try:
        return asyncio.run(coro)
    except RuntimeError as exc:  # pragma: no cover - depends on caller context
        if "event loop" in str(exc).lower():
            raise WebSocketExchangeError("Cannot run synchronous API inside a running event loop. Use the async method.") from exc
        raise


def safe_float(value: Any) -> float | None:
    try:
        return float(value) if value is not None else None
    except (TypeError, ValueError):
        return None


def safe_int(value: Any) -> int | None:
    try:
        return int(value) if value is not None else None
    except (TypeError, ValueError):
        return None


def _serialize_if_needed(message: Any) -> Any:
    """Send dicts as JSON strings; passthrough bytes/strings."""
    if isinstance(message, (bytes, bytearray, str)):
        return message
    return json.dumps(message)

