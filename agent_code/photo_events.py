from __future__ import annotations

from dataclasses import dataclass, field
from typing import Protocol


class EventSink(Protocol):
    def write(self, text: str, *, end: str = "", flush: bool = False) -> None:
        ...

    def line(self, text: str = "") -> None:
        ...

    def progress(self, message: str) -> None:
        ...


class ConsoleEventSink:
    def write(self, text: str, *, end: str = "", flush: bool = False) -> None:
        print(text, end=end, flush=flush)

    def line(self, text: str = "") -> None:
        print(text)

    def progress(self, message: str) -> None:
        print(message)


@dataclass
class BufferEventSink:
    chunks: list[str] = field(default_factory=list)
    progress_updates: list[str] = field(default_factory=list)

    def write(self, text: str, *, end: str = "", flush: bool = False) -> None:
        del flush
        self.chunks.append(f"{text}{end}")

    def line(self, text: str = "") -> None:
        self.chunks.append(f"{text}\n")

    def progress(self, message: str) -> None:
        self.progress_updates.append(message)
        self.line(message)

    @property
    def text(self) -> str:
        return "".join(self.chunks)


DEFAULT_CONSOLE_SINK = ConsoleEventSink()


def ensure_event_sink(sink: EventSink | None) -> EventSink:
    return sink or DEFAULT_CONSOLE_SINK
