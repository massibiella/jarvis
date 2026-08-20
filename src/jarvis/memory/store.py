"""Persistent memory: markdown files with YAML frontmatter, one directory
per user. Distinct from conversation history — this is what survives
across sessions (weeks/months), not just within one chat.

Files are named `memory_*.md` (see tools/memory_tools.py, which is what
actually writes them) — read/write/append operate on any relative path
under `users/<user_id>/`, parsing/writing the
"---\\nYAML frontmatter\\n---\\nmarkdown body" format (yaml.safe_load /
yaml.safe_dump — same library config.py already uses). load_index()
derives the index from the real files' own frontmatter `description`
field every time — there's no separate manually-maintained index file,
by design (see docs/PLAN.md § "Memory" for why). search() is plain
substring matching, no embeddings.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml


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
        full_path = self.user_dir / relative_path
        file_content = full_path.read_text()

        _, frontmatter_text, body = file_content.split("---", 2)
        frontmatter = yaml.safe_load(frontmatter_text) or {}

        return MemoryEntry(path=full_path, frontmatter=frontmatter, body=body.strip())

    def write(
        self, relative_path: str, body: str, frontmatter: dict[str, Any] | None = None
    ) -> None:
    
        full_path = self.user_dir / relative_path
        full_path.parent.mkdir(parents=True, exist_ok=True)

        yaml_text = yaml.safe_dump(frontmatter or {})
        yaml_text = f'---\n{yaml_text}---\n'

        full_path.write_text(f"{yaml_text}{body}")


    def append(
        self, relative_path: str, text: str, default_frontmatter: dict[str, Any] | None = None
    ) -> None:
        """Append `text` as a new line to an existing (or new) file's body.

        `default_frontmatter` is only used the first time this file is
        created — an existing file's frontmatter is always preserved as-is,
        never overwritten by a later append.
        """
        try:
            entry = self.read(relative_path)
            body, frontmatter = entry.body, entry.frontmatter
        except FileNotFoundError:
            body, frontmatter = "", default_frontmatter or {}

        new_body = f"{body}\n{text}" if body else text
        self.write(relative_path, body=new_body, frontmatter=frontmatter)

    def load_index(self) -> str:
        """Return the index (file list + descriptions) as a string, ready
        to drop into the system prompt. Must NOT include full file bodies."""
        lines = []
        for file in sorted(self.user_dir.glob("memory_*.md")):
            entry = self.read(file.name)
            description = entry.frontmatter.get("description", "(no description)")
            lines.append(f"- {file.name} — {description}")

        return "\n".join(lines)

    def search(self, query: str) -> list[str]:
        """Return relative paths of files whose content matches `query`
        (plain substring/keyword match — no embeddings)."""
        matches = []
        for file in sorted(self.user_dir.glob("memory_*.md")):
            if query in file.read_text():
                matches.append(file.name)
        return matches
