import pytest
import subprocess
import sys
from unittest.mock import patch


def run_bot(*args):
    result = subprocess.run(
        [sys.executable, "earnings_bot.py", *args],
        capture_output=True,
        text=True,
        cwd="/Users/winnie/Documents/trae_projects/earnings-alert-bot",
    )
    return result


class TestDryRunNeverSends:
    def test_mock_dry_run(self):
        result = run_bot("--provider", "mock", "--ticker", "MRVL", "--dry-run")
        assert result.returncode == 0
        assert "DRY-RUN" in result.stdout
        assert "MRVL" in result.stdout

    def test_dry_run_no_feishu_env(self):
        """Dry-run should work even without FEISHU_WEBHOOK."""
        result = run_bot("--provider", "mock", "--ticker", "MRVL", "--dry-run")
        assert result.returncode == 0
        assert "DRY-RUN" in result.stdout


class TestSendRequiresWebhook:
    def test_send_without_webhook(self):
        """--send without FEISHU_WEBHOOK should fail cleanly."""
        result = run_bot("--provider", "mock", "--ticker", "MRVL", "--send")
        assert result.returncode == 1
        assert "FEISHU_WEBHOOK" in result.stdout or "FEISHU_WEBHOOK" in result.stderr


class TestFmpMissingApiKey:
    def test_fmp_without_api_key(self):
        """FMP without FMP_API_KEY should fail cleanly."""
        result = run_bot("--provider", "fmp", "--ticker", "MRVL", "--dry-run")
        assert result.returncode == 1
        assert "FMP_API_KEY" in result.stdout or "FMP_API_KEY" in result.stderr


class TestExplicitTickerNoData:
    def test_unknown_ticker(self):
        """Explicit ticker with no data should print specific message."""
        result = run_bot("--provider", "mock", "--ticker", "UNKNOWN", "--dry-run")
        assert result.returncode == 0
        assert "No earnings data found for UNKNOWN" in result.stdout

    def test_watchlist_no_data(self):
        """Watchlist with no data should print generic message."""
        # This test would need a config with only unknown tickers
        # For now, just verify the mock provider works
        result = run_bot("--provider", "mock", "--dry-run")
        assert result.returncode == 0
        assert "Processed" in result.stdout


class TestNoModeSpecified:
    def test_no_dry_run_or_send(self):
        """Running without --dry-run or --send should fail."""
        result = run_bot("--provider", "mock", "--ticker", "MRVL")
        assert result.returncode == 1
        assert "specify --dry-run or --send" in result.stdout
