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


# Every informational item the model can be asked to report is a step: a
# plain instruction string (some are templates filled in with .format()),
# assembled into a numbered list by _numbered_steps(). Keeping every step's
# text here, in one place and one shape, is what makes the two prompt
# builders below just "which steps, in which order" instead of each
# hand-rolling its own prose.
_WEATHER_STEP = "Current weather at home ({home}) — use get_current_weather."

_COMMUTE_STEP = (
    "Commute time/traffic from home ({home}) to work ({work}) — use get_travel_time "
    "with mode=driving."
)

_CALENDAR_TODAY_STEP = (
    "What's on my calendar today — use get-current-time then list-events for today's date "
    "range, and give me a brief rundown of today's events."
)

_INTERESTS_NEWS_STEP = (
    "Read memory_interests.md via read_memory. For up to 3 topics listed there (in the "
    "order remembered), use web_search to find 1-2 current top headlines about each."
)

_HOLDINGS_NEWS_STEP = (
    "Look up my current investment holdings (get_account_positions), then for up to 3 of "
    "them use web_search to find 1-2 current headlines relevant to that specific "
    "holding/company."
)

_PERFORMANCE_STEP = (
    "Give me the overall portfolio change today, and the single best and single worst "
    'performing holding today, each named with its % move (e.g. "Your best performer was '
    'GOOGL, up 1.2%, while your worst was QQQM, down 0.35%."). Use '
    "get_pa_performance_all_periods for overall performance and get_account_positions "
    "(and get_price_snapshot per position if needed) to find today's best/worst performer."
)

# Not a step: unlike the informational items above, this changes how the
# model should behave for the rest of its reply (ask one question, then
# stop instead of reporting everything up front) — kept as its own
# constant rather than forced into the numbered list it doesn't belong in.
_CALENDAR_FOLLOWUP = (
    "After that, check today's calendar: use get-current-time and list-events to find "
    "today's events that have already ended. If there are any, pick the first one (in "
    "time order) and ask me directly whether I actually completed it — don't assume "
    "either way just because the scheduled time has passed. This is the one exception "
    "where you should ask a question and stop: ask about only that one event, then end "
    "your reply there and wait for my answer before asking about any others — don't list "
    "them all at once. If I say I did not complete it, ask where and when I'd like to "
    "move it to, then use update-event to actually reschedule it once I tell you, and "
    "afterward move on to asking about the next ended event the same way. If nothing has "
    "ended yet today, or there are no events today, skip this part entirely and don't "
    "mention it."
)


def _numbered_steps(steps: list[str]) -> str:
    return "\n".join(f"{i + 1}. {s}" for i, s in enumerate(steps))


def _morning_prompt(config: CheckinConfig) -> str:
    steps = []
    if config.home:
        steps.append(_WEATHER_STEP.format(home=config.home))
    if config.home and config.work:
        steps.append(_COMMUTE_STEP.format(home=config.home, work=config.work))
    steps += [_CALENDAR_TODAY_STEP, _INTERESTS_NEWS_STEP, _HOLDINGS_NEWS_STEP]
    return (
        "This is an automated morning check-in, not something I typed. Give me one concise, "
        "well-organized briefing covering the following, using your tools. Don't ask "
        "clarifying questions — do your best with what's available, and note plainly (don't "
        "silently skip) if something's missing, e.g. no interests remembered yet, or home/work "
        f"not configured:\n{_numbered_steps(steps)}"
    )


def _evening_prompt(config: CheckinConfig) -> str:
    steps = [_PERFORMANCE_STEP, _INTERESTS_NEWS_STEP, _HOLDINGS_NEWS_STEP]
    return (
        "This is an automated evening check-in, not something I typed. Start with a brief "
        "welcoming line (e.g. \"Welcome back. Here's a summary of your portfolio performance "
        f"today.\"), then give me the following, using your tools. Don't ask clarifying "
        f"questions for any of this:\n{_numbered_steps(steps)}\n\n{_CALENDAR_FOLLOWUP}"
    )


async def run_checkin(agent: Agent, kind: str, config: CheckinConfig) -> str:
    prompt = _morning_prompt(config) if kind == "morning" else _evening_prompt(config)
    return await agent.step(prompt)
