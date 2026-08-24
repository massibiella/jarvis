"""Native tools wrapping MemoryStore, registered into a ToolRegistry.

Kept separate from cli.py — same reasoning as weather_tools.py living in
its own file, not inline in the entry point. cli.py's job is wiring
things together, not defining feature/tool logic.
"""

from __future__ import annotations

from jarvis.memory.store import MemoryStore
from jarvis.tools.registry import ToolRegistry

# Written once, by a human, here — not by the model at write time. Keeps
# every memory_*.md file's description meaningful from the moment it's
# first created, instead of relying on the model to invent a good one on
# the fly (see docs/PLAN.md "Memory" section for why that's the design).
_CATEGORY_DESCRIPTIONS = {
    "facts": "Durable facts about the user — plans, work, ongoing life situations.",
    "preferences": "How the user likes to communicate and be helped.",
    "interests": "Topics the user wants news tracked on, surfaced each morning check-in.",
}


def register_memory_tools(tools: ToolRegistry, memory: MemoryStore) -> None:
    @tools.register()
    def remember(category: str, text: str) -> str:
        """Save something worth remembering long-term, for future conversations.
        category must be exactly 'facts', 'preferences', or 'interests'.
        Use 'facts' for durable info about the user (plans, work, ongoing situations).
        Use 'preferences' for how they like to communicate/be helped.
        Use 'interests' when the user asks you to track news/updates on a topic
        (e.g. "tell me news about the Fed") — store the topic concisely (e.g.
        "Federal Reserve interest rate decisions"), not a running log of headlines.
        """
        if category not in _CATEGORY_DESCRIPTIONS:
            return f"Error: category must be one of {list(_CATEGORY_DESCRIPTIONS)}."

        default_frontmatter = {
            "title": category.title(),
            "description": _CATEGORY_DESCRIPTIONS.get(category, ""),
        }
        memory.append(f"memory_{category}.md", text, default_frontmatter=default_frontmatter)
        return "Remembered."

    @tools.register()
    def list_memory() -> str:
        """List every memory file with its one-line description. Use this to
        see what's been remembered before deciding whether to read one in full."""
        index = memory.load_index()
        return index if index else "Nothing has been remembered yet."

    @tools.register()
    def read_memory(path: str) -> str:
        """Read the full content of one memory file, e.g. 'memory_facts.md'.
        Get the exact filename from list_memory first."""
        return memory.read(path).body

    @tools.register()
    def search_memory(query: str) -> str:
        """Search all memory files for a keyword; returns which files matched
        (not their content — use read_memory on a match to see it)."""
        matches = memory.search(query)
        return ", ".join(matches) if matches else "No matches found."
