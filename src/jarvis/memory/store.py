"""Persistent memory: markdown files with YAML frontmatter, one directory
per user. Distinct from conversation history — this is what survives
across sessions (weeks/months), not just within one chat.

TODO (Step 7): implement MemoryStore. See docs/PLAN.md
§ "Memory (index + on-demand recall)" for the exact shape:

- read/write/append operate on a single file under `users/<user_id>/`,
  parsing/writing "---\\nYAML frontmatter\\n---\\nmarkdown body" format
  (yaml.safe_load / yaml.safe_dump — same library config.py already uses)
- load_index() returns the *index* only (file list + descriptions) — this
  is what goes into the system prompt at startup, NOT full file contents
- search() is plain keyword/grep over file contents, no vector DB
- create user_dir and an empty index.md the first time a MemoryStore is
  constructed for a user_id that doesn't have one yet
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any


@dataclass
class MemoryEntry:
    path: Path
    frontmatter: dict[str, Any]
    body: str


class MemoryStore:
    def __init__(self, root: Path, user_id: str = "default") -> None:
        self.root = root
        self.user_dir = root / "users" / user_id

    def read(self, relative_path: str) -> MemoryEntry:
        raise NotImplementedError("TODO: Step 7 — see docs/PLAN.md")

    def write(
        self, relative_path: str, body: str, frontmatter: dict[str, Any] | None = None
    ) -> None:
        raise NotImplementedError("TODO: Step 7 — see docs/PLAN.md")

    def append(self, relative_path: str, text: str) -> None:
        """Append `text` as a new line to an existing (or new) file's body."""
        raise NotImplementedError("TODO: Step 7 — see docs/PLAN.md")

    def load_index(self) -> str:
        """Return the index (file list + descriptions) as a string, ready
        to drop into the system prompt. Must NOT include full file bodies."""
        raise NotImplementedError("TODO: Step 7 — see docs/PLAN.md")

    def search(self, query: str) -> list[str]:
        """Return relative paths of files whose content matches `query`
        (plain substring/keyword match — no embeddings)."""
        raise NotImplementedError("TODO: Step 7 — see docs/PLAN.md")
