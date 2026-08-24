import json
from datetime import datetime
from pathlib import Path

from jarvis.checkin import determine_checkin, load_state, mark_ran, save_state, state_path
from jarvis.config import CheckinConfig

ENABLED = CheckinConfig(
    enabled=True, morning_start_hour=5, morning_end_hour=11, evening_start_hour=17
)


def test_disabled_returns_none_regardless_of_time() -> None:
    config = CheckinConfig(enabled=False)
    assert determine_checkin(datetime(2026, 1, 1, 9), config, {}) is None
    assert determine_checkin(datetime(2026, 1, 1, 20), config, {}) is None


def test_morning_window_no_prior_state() -> None:
    assert determine_checkin(datetime(2026, 1, 1, 9), ENABLED, {}) == "morning"


def test_morning_window_already_ran_today() -> None:
    state = {"morning": "2026-01-01"}
    assert determine_checkin(datetime(2026, 1, 1, 9), ENABLED, state) is None


def test_morning_window_ran_previous_day_fires_again() -> None:
    state = {"morning": "2025-12-31"}
    assert determine_checkin(datetime(2026, 1, 1, 9), ENABLED, state) == "morning"


def test_evening_window_no_prior_state() -> None:
    assert determine_checkin(datetime(2026, 1, 1, 20), ENABLED, {}) == "evening"


def test_outside_both_windows() -> None:
    assert determine_checkin(datetime(2026, 1, 1, 13), ENABLED, {}) is None


def test_morning_start_hour_inclusive() -> None:
    assert determine_checkin(datetime(2026, 1, 1, 5), ENABLED, {}) == "morning"


def test_morning_end_hour_exclusive() -> None:
    assert determine_checkin(datetime(2026, 1, 1, 11), ENABLED, {}) is None


def test_evening_start_hour_inclusive() -> None:
    assert determine_checkin(datetime(2026, 1, 1, 17), ENABLED, {}) == "evening"


def test_mark_ran_sets_kind_without_clobbering_other() -> None:
    state = {"evening": "2025-12-31"}
    mark_ran(state, "morning")
    assert state["evening"] == "2025-12-31"
    assert state["morning"] == datetime.now().date().isoformat()


def test_state_round_trips(tmp_path: Path) -> None:
    path = tmp_path / "state" / "checkins.json"
    save_state(path, {"morning": "2026-01-01"})
    assert load_state(path) == {"morning": "2026-01-01"}


def test_load_state_missing_file_returns_empty(tmp_path: Path) -> None:
    assert load_state(tmp_path / "nope.json") == {}


def test_load_state_malformed_json_returns_empty(tmp_path: Path) -> None:
    path = tmp_path / "checkins.json"
    path.write_text("not json")
    assert load_state(path) == {}


def test_save_state_creates_parent_dirs(tmp_path: Path) -> None:
    path = tmp_path / "a" / "b" / "checkins.json"
    save_state(path, {"morning": "2026-01-01"})
    assert json.loads(path.read_text()) == {"morning": "2026-01-01"}


def test_state_path_is_sibling_of_memory_dir() -> None:
    memory_root = Path("/data/memory")
    assert state_path(memory_root) == Path("/data/state/checkins.json")
