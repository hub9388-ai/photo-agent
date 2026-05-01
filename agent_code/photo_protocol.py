from __future__ import annotations

import re
from typing import Sequence

from photo_events import EventSink, ensure_event_sink


RESPONSE_DELIMITER = "<<<PHOTO_AGENT_PAYLOAD>>>"
DEFAULT_PARSE_GUARD = max(len(RESPONSE_DELIMITER), 120)


def find_response_boundary(
    text: str,
    *,
    delimiter: str = RESPONSE_DELIMITER,
    anchor_keys: Sequence[str] | None = None,
) -> tuple[int, int]:
    marker_index = text.find(delimiter)
    if marker_index != -1:
        return marker_index, len(delimiter)

    keys = [str(item).strip() for item in (anchor_keys or []) if str(item).strip()]
    if keys:
        key_pattern = "|".join(re.escape(item) for item in keys)
        json_match = re.search(
            rf'\n\s*(\{{)(?=[\s\S]{{0,800}}"(?:{key_pattern})"\s*:)',
            text,
        )
        if json_match:
            return json_match.start(1), 0

        stripped = text.lstrip()
        if stripped.startswith("{") and re.search(rf'"(?:{key_pattern})"\s*:', stripped[:800]):
            return len(text) - len(stripped), 0

    return -1, 0


def split_response_sections(
    raw_text: str,
    *,
    delimiter: str = RESPONSE_DELIMITER,
    anchor_keys: Sequence[str] | None = None,
) -> tuple[str, str, bool]:
    boundary_index, boundary_length = find_response_boundary(
        raw_text,
        delimiter=delimiter,
        anchor_keys=anchor_keys,
    )
    if boundary_index == -1:
        return "", raw_text.strip(), False

    visible_text = raw_text[:boundary_index].strip()
    payload_text = raw_text[boundary_index + boundary_length :].strip()
    return visible_text, payload_text, True


def stream_visible_response(
    client,
    *,
    model: str,
    max_tokens: int,
    system: str,
    messages: list,
    anchor_keys: Sequence[str] | None = None,
    delimiter: str = RESPONSE_DELIMITER,
    parse_guard: int = DEFAULT_PARSE_GUARD,
    sink: EventSink | None = None,
) -> tuple[str, str]:
    event_sink = ensure_event_sink(sink)
    raw_text = ""
    visible_parts: list[str] = []
    buffer = ""
    boundary_detected = False

    with client.messages.stream(
        model=model,
        max_tokens=max_tokens,
        system=system,
        messages=messages,
    ) as stream:
        for chunk in stream.text_stream:
            raw_text += chunk

            if boundary_detected:
                continue

            buffer += chunk
            boundary_index, _ = find_response_boundary(
                buffer,
                delimiter=delimiter,
                anchor_keys=anchor_keys,
            )
            if boundary_index != -1:
                visible_segment = buffer[:boundary_index]
                if visible_segment:
                    event_sink.write(visible_segment, end="", flush=True)
                    visible_parts.append(visible_segment)
                buffer = ""
                boundary_detected = True
                continue

            safe_length = len(buffer) - parse_guard
            if safe_length > 0:
                safe_segment = buffer[:safe_length]
                event_sink.write(safe_segment, end="", flush=True)
                visible_parts.append(safe_segment)
                buffer = buffer[safe_length:]

    if not boundary_detected and buffer:
        boundary_index, _ = find_response_boundary(
            buffer,
            delimiter=delimiter,
            anchor_keys=anchor_keys,
        )
        if boundary_index != -1:
            visible_segment = buffer[:boundary_index]
            if visible_segment:
                event_sink.write(visible_segment, end="", flush=True)
                visible_parts.append(visible_segment)
        else:
            event_sink.write(buffer, end="", flush=True)
            visible_parts.append(buffer)

    event_sink.line()
    return "".join(visible_parts).strip(), raw_text.strip()
