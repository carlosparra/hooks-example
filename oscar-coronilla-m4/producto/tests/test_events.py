"""Pruebas de ``app.events``: una linea JSON por evento, con hora del reloj falso."""

import io
import json
from datetime import datetime

from app.events import EventLogger


def test_event_is_one_json_line_with_the_common_fields(fake_clock):
    stream = io.StringIO()
    logger = EventLogger(stream=stream, clock=fake_clock, service="hr-test")

    logger.emit(
        "audit",
        "req-1",
        action="tool_call",
        tool="search_by_department",
        args={"department": "Tecnología"},
    )

    text = stream.getvalue()
    assert text.endswith("\n")
    assert text.count("\n") == 1
    assert "Tecnología" in text
    event = json.loads(text)
    timestamp = datetime.fromisoformat(event.pop("ts").replace("Z", "+00:00"))
    assert timestamp == fake_clock.START
    assert timestamp.utcoffset().total_seconds() == 0
    assert event == {
        "service": "hr-test",
        "event": "audit",
        "request_id": "req-1",
        "action": "tool_call",
        "tool": "search_by_department",
        "args": {"department": "Tecnología"},
    }
