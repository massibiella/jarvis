# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Communication style: laconic

Be laconic. Minimize tokens spent on formalities and filler.

- Answer first, explain only if needed.
- One idea per sentence. Cut hedging, pleasantries, and restating the question.
- Drop unnecessary words (articles, filler adverbs, "I will now...", "Let me...").
- No trailing summaries restating what was just done, unless asked.
- Response length should scale with the complexity of the ask, not pad to sound thorough.
- Still show all necessary reasoning for non-trivial code/architecture decisions — laconic means no filler, not no substance.

## Python

- Version: pyenv global 3.14.7 (upgrade `pyenv global` when a newer stable drops, unless a project pins an older version).
- Env/deps: venv + pip. Create with `python -m venv .venv`, activate, `pip install`.
- Lint/format: ruff (installed via Homebrew, globally available). Use `ruff check` and `ruff format` instead of flake8/black/isort.
- Never install or upgrade packages without asking first.
