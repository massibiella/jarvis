"""Startup-triggered morning/evening check-ins.

Trigger model (deliberately simple, per docs/PLAN.md): checked once, at
process/session startup, by comparing local wall-clock time against
configured windows — no background poller, no continuous scheduler.
Dedup state (has today's check-in of this kind already run?) lives in a
small JSON file, sibling to the memory data dir, so it inherits whatever
on-disk location memory.root_dir resolves to (source checkout or a
packaged app's ~/.jarvis/...).

Reuses Agent.step() with a single crafted prompt per check-in kind — no
new tools. The prompt tells the model which existing tools to use
(weather, get_travel_time, read_memory, web_search, IBKR's read-only
tools) and what to report; the model decides how many calls to make.
"""

from __future__ import annotations

import json
import logging
from datetime import datetime
from pathlib import Path

from jarvis.agent import Agent
from jarvis.config import CheckinConfig

logger = logging.getLogger(__name__)


def state_path(memory_root_dir: Path) -> Path:
    """<memory.root_dir>.parent / "state" / "checkins.json" — sibling to
    the memory data dir, not inside it (dedupe bookkeeping isn't memory
    the agent should read into context, and it isn't user config either).
    """
    return memory_root_dir.parent / "state" / "checkins.json"


def load_state(path: Path) -> dict:
    if not path.is_file():
        return {}
    try:
        return json.loads(path.read_text())
    except (json.JSONDecodeError, OSError) as e:
        logger.warning("Failed to read checkin state at %s (%s) — starting fresh", path, e)
        return {}


def save_state(path: Path, state: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(state))


def determine_checkin(now: datetime, config: CheckinConfig, state: dict) -> str | None:
    """Pure, no I/O. Returns "morning", "evening", or None.

    Morning window: [morning_start_hour, morning_end_hour).
    Evening window: [evening_start_hour, 24).
    None if check-ins are disabled, the current hour is in neither window,
    or that kind of check-in already ran today.
    """
    if not config.enabled:
        return None

    hour = now.hour
    if config.morning_start_hour <= hour < config.morning_end_hour:
        kind = "morning"
    elif hour >= config.evening_start_hour:
        kind = "evening"
    else:
        return None

    if state.get(kind) == now.date().isoformat():
        return None
    return kind


def mark_ran(state: dict, kind: str) -> None:
    state[kind] = datetime.now().date().isoformat()


def _morning_prompt(config: CheckinConfig) -> str:
    steps = []
    if config.home:
        steps.append(f"Current weather at home ({config.home}) — use get_current_weather.")
    if config.home and config.work:
        steps.append(
            f"Commute time/traffic from home ({config.home}) to work ({config.work}) — "
            "use get_travel_time with mode=driving."
        )
    steps.append(
        "Read memory_interests.md via read_memory. For up to 3 topics listed there (in the "
        "order remembered), use web_search to find 1-2 current top headlines about each."
    )
    steps.append(
        "Look up my current investment holdings (get_account_positions), then for up to 3 of "
        "them use web_search to find 1-2 headlines relevant to that specific holding/company."
    )
    numbered = "\n".join(f"{i + 1}. {s}" for i, s in enumerate(steps))
    return (
        "This is an automated morning check-in, not something I typed. Give me one concise, "
        "well-organized briefing covering the following, using your tools. Don't ask "
        "clarifying questions — do your best with what's available, and note plainly (don't "
        "silently skip) if something's missing, e.g. no interests remembered yet, or home/work "
        f"not configured:\n{numbered}"
    )


def _evening_prompt(config: CheckinConfig) -> str:
    return (
        "This is an automated evening check-in, not something I typed. Start with a brief "
        "welcoming line (e.g. \"Welcome back. Here's a summary of your portfolio performance "
        'today."), then give me: the overall portfolio change today, and the single best and '
        'single worst performing holding today, each named with its % move (e.g. "Your best '
        'performer was GOOGL, up 1.2%, while your worst was QQQM, down 0.35%."). Use '
        "get_pa_performance_all_periods for overall performance and get_account_positions "
        "(and get_price_snapshot per position if needed) to find today's best/worst performer. "
        "Then, same as the morning check-in, read memory_interests.md via read_memory and use "
        "web_search to find 1-2 current headlines for up to 3 topics listed there. Don't ask "
        "clarifying questions."
    )


async def run_checkin(agent: Agent, kind: str, config: CheckinConfig) -> str:
    prompt = _morning_prompt(config) if kind == "morning" else _evening_prompt(config)
    return await agent.step(prompt)
