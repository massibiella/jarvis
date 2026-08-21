"""Google Calendar's tool-schema overrides.

Its create-event/update-event/list-events schemas hand back far more than
needed — Workspace-only and edge-case fields that inflate every agent
turn's tool-schema cost (see docs/PLAN.md's "Resolved: Google Calendar
tool-schema cost"). Overriding the schema only changes what the LLM sees;
the underlying MCP tool call still goes through unchanged — the server
still accepts (and validates) its full original schema, so any field we
didn't expose simply keeps its server-side default.
"""

from __future__ import annotations

from typing import Any

_ATTENDEE_SCHEMA = {
    "type": "object",
    "properties": {
        "email": {"type": "string", "description": "Email address of the attendee"},
        "displayName": {"type": "string", "description": "Display name of the attendee"},
    },
    "required": ["email"],
}

_EVENT_CORE_PROPERTIES = {
    "calendarId": {
        "type": "string",
        "description": "ID of the calendar (use 'primary' for the main calendar)",
    },
    "summary": {"type": "string", "description": "Title of the event"},
    "description": {"type": "string", "description": "Description/notes for the event"},
    "start": {
        "type": "string",
        "description": "Event start time, e.g. '2025-01-01T10:00:00' (timed) or "
        "'2025-01-01' (all-day).",
    },
    "end": {
        "type": "string",
        "description": "Event end time, e.g. '2025-01-01T11:00:00' (timed) or "
        "'2025-01-02' (all-day, exclusive).",
    },
    "timeZone": {
        "type": "string",
        "description": "Timezone as IANA name (e.g., America/Los_Angeles). Only used for "
        "timezone-naive datetime strings.",
    },
    "location": {"type": "string", "description": "Location of the event"},
    "attendees": {
        "type": "array",
        "description": "List of event attendees",
        "items": _ATTENDEE_SCHEMA,
    },
    "recurrence": {
        "type": "array",
        "description": 'Recurrence rules in RFC5545 format (e.g., ["RRULE:FREQ=WEEKLY;COUNT=5"])',
        "items": {"type": "string"},
    },
}

SCHEMA_OVERRIDES: dict[str, dict[str, Any]] = {
    "create-event": {
        "type": "object",
        "properties": _EVENT_CORE_PROPERTIES,
        "required": ["calendarId", "summary", "start", "end"],
    },
    "update-event": {
        "type": "object",
        "properties": {
            "eventId": {"type": "string", "description": "ID of the event to update"},
            **_EVENT_CORE_PROPERTIES,
        },
        "required": ["calendarId", "eventId"],
    },
    "list-events": {
        "type": "object",
        "properties": {
            "calendarId": {
                "type": "string",
                "description": "ID of the calendar (use 'primary' for the main calendar)",
            },
            "timeMin": {
                "type": "string",
                "description": "Start of time range (ISO 8601, e.g., '2024-01-01T00:00:00').",
            },
            "timeMax": {
                "type": "string",
                "description": "End of time range (ISO 8601, e.g., '2024-01-31T23:59:59').",
            },
            "timeZone": {
                "type": "string",
                "description": "IANA timezone (e.g., 'America/Los_Angeles'). Defaults to "
                "calendar's timezone.",
            },
        },
        "required": ["calendarId"],
    },
}
