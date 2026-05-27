import pytest
from alert_formatter import calc_surprise_pct


def test_positive_surprise():
    assert calc_surprise_pct(1.10, 1.00) == 10.0


def test_negative_surprise():
    assert calc_surprise_pct(0.90, 1.00) == -10.0


def test_zero_surprise():
    assert calc_surprise_pct(1.00, 1.00) == 0.0


def test_actual_none():
    assert calc_surprise_pct(None, 1.00) is None


def test_consensus_none():
    assert calc_surprise_pct(1.00, None) is None


def test_consensus_zero():
    assert calc_surprise_pct(1.00, 0) is None


def test_small_surprise():
    result = calc_surprise_pct(0.83, 0.79)
    assert result is not None
    assert abs(result - 5.06) < 0.01


def test_negative_consensus():
    # Negative consensus, surprise should still work
    result = calc_surprise_pct(-0.50, -1.00)
    assert result == 50.0
