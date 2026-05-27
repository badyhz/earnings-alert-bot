import json
import pytest
import tempfile
from datetime import datetime, timedelta
from pathlib import Path
from unittest.mock import patch

from earnings_bot import build_alert_key, is_alert_sent, load_sent_alerts, save_sent_alerts


@pytest.fixture
def temp_state(tmp_path):
    """Use a temporary directory for state files."""
    with patch("earnings_bot.STATE_DIR", tmp_path), \
         patch("earnings_bot.SENT_ALERTS_FILE", tmp_path / "sent_alerts.json"):
        yield tmp_path


def test_build_alert_key():
    key = build_alert_key("MRVL", "2026-05-27", "STRONG_BEAT")
    assert key == "MRVL|2026-05-27|STRONG_BEAT"


def test_no_alerts_sent(temp_state):
    assert not is_alert_sent("TEST|2026-01-01|MILD_BEAT", 12)


def test_alert_within_cooldown(temp_state):
    alerts = {"TEST|2026-01-01|MILD_BEAT": datetime.now().isoformat()}
    save_sent_alerts(alerts)
    assert is_alert_sent("TEST|2026-01-01|MILD_BEAT", 12)


def test_alert_outside_cooldown(temp_state):
    old_time = (datetime.now() - timedelta(hours=13)).isoformat()
    alerts = {"TEST|2026-01-01|MILD_BEAT": old_time}
    save_sent_alerts(alerts)
    assert not is_alert_sent("TEST|2026-01-01|MILD_BEAT", 12)


def test_different_keys_not_dedupe(temp_state):
    alerts = {"MRVL|2026-05-27|STRONG_BEAT": datetime.now().isoformat()}
    save_sent_alerts(alerts)
    assert not is_alert_sent("NVDA|2026-05-28|MILD_BEAT", 12)


def test_save_and_load(temp_state):
    data = {"key1": "2026-01-01T00:00:00"}
    save_sent_alerts(data)
    loaded = load_sent_alerts()
    assert loaded == data


def test_load_missing_file(temp_state):
    # File doesn't exist yet
    loaded = load_sent_alerts()
    assert loaded == {}
