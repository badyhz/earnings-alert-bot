#!/usr/bin/env python3
import argparse
import json
import os
import sys
from datetime import datetime
from pathlib import Path
from typing import Optional

import yaml

from alert_formatter import Thresholds, calc_surprise_pct, classify_earnings, format_earnings_alert
from feishu_client import send_alert
from providers import EarningsProvider, MockProvider
from providers.base import EarningsData
from providers.fmp_provider import FmpProviderError

STATE_DIR = Path(__file__).parent / "state"
SENT_ALERTS_FILE = STATE_DIR / "sent_alerts.json"


def load_watchlist(path: str) -> dict:
    with open(path, "r") as f:
        return yaml.safe_load(f)


def load_sent_alerts() -> dict:
    if not SENT_ALERTS_FILE.exists():
        return {}
    with open(SENT_ALERTS_FILE, "r") as f:
        return json.load(f)


def save_sent_alerts(data: dict) -> None:
    STATE_DIR.mkdir(exist_ok=True)
    with open(SENT_ALERTS_FILE, "w") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)


def build_alert_key(ticker: str, earnings_date: str, classification: str) -> str:
    return f"{ticker}|{earnings_date}|{classification}"


def is_alert_sent(key: str, cooldown_hours: int) -> bool:
    alerts = load_sent_alerts()
    if key not in alerts:
        return False
    sent_at = datetime.fromisoformat(alerts[key])
    elapsed = (datetime.now() - sent_at).total_seconds() / 3600
    return elapsed < cooldown_hours


def mark_alert_sent(key: str) -> None:
    alerts = load_sent_alerts()
    alerts[key] = datetime.now().isoformat()
    save_sent_alerts(alerts)


def get_provider(name: str, debug: bool = False) -> EarningsProvider:
    if name == "mock":
        return MockProvider()
    elif name == "fmp":
        from providers import FmpProvider
        return FmpProvider(debug=debug)
    else:
        raise ValueError(f"Unknown provider: {name}")


def process_ticker(
    data: EarningsData,
    thresholds: Thresholds,
    cooldown_hours: int,
    force: bool,
    dry_run: bool,
    send: bool,
) -> bool:
    eps_surprise = calc_surprise_pct(data.actual_eps, data.consensus_eps)
    revenue_surprise = calc_surprise_pct(data.actual_revenue, data.consensus_revenue)
    classification = classify_earnings(eps_surprise, revenue_surprise, data.price_move_pct, thresholds)

    alert_key = build_alert_key(data.ticker, data.earnings_date, classification)

    if not force and is_alert_sent(alert_key, cooldown_hours):
        print(f"[SKIP] {data.ticker} - alert already sent within {cooldown_hours}h cooldown")
        return False

    message = format_earnings_alert(data, thresholds)

    if send and not dry_run:
        try:
            result = send_alert(message, dry_run=False)
            print(f"[SENT] {data.ticker} - Feishu response: {result}")
            mark_alert_sent(alert_key)
        except ValueError as e:
            print(f"Error: {e}")
            sys.exit(1)
    elif dry_run:
        send_alert(message, dry_run=True)
        print()
    else:
        print(message)
        print()

    return True


def main():
    parser = argparse.ArgumentParser(description="Earnings Intelligence Bot")
    parser.add_argument("--provider", default="mock", choices=["mock", "fmp"], help="Data provider")
    parser.add_argument("--ticker", help="Process single ticker instead of watchlist")
    parser.add_argument("--config", default="config/watchlist.yaml", help="Watchlist config path")
    parser.add_argument("--dry-run", action="store_true", help="Print only, don't send")
    parser.add_argument("--send", action="store_true", help="Send to Feishu")
    parser.add_argument("--force", action="store_true", help="Ignore cooldown")
    parser.add_argument("--debug", action="store_true", help="Enable FMP debug output")
    args = parser.parse_args()

    if not args.dry_run and not args.send:
        print("Error: specify --dry-run or --send")
        sys.exit(1)

    config_path = Path(__file__).parent / args.config
    config = load_watchlist(str(config_path))
    raw_thresholds = config.get("thresholds", {})
    cooldown_hours = raw_thresholds.pop("cooldown_hours", 12)
    thresholds = Thresholds(**raw_thresholds)

    try:
        provider = get_provider(args.provider, debug=args.debug)
    except (FmpProviderError, ValueError) as e:
        print(f"Error: {e}")
        sys.exit(1)

    if args.ticker:
        tickers = [args.ticker.upper()]
    else:
        tickers = [t.upper() for t in config.get("tickers", [])]

    earnings_list = provider.get_earnings_batch(tickers)

    if not earnings_list:
        if args.ticker:
            print(f"No earnings data found for {args.ticker.upper()}.")
        else:
            print("No earnings data found.")
        sys.exit(0)

    sent_count = 0
    for data in earnings_list:
        if process_ticker(data, thresholds, cooldown_hours, args.force, args.dry_run, args.send):
            sent_count += 1

    print(f"Processed {len(earnings_list)} tickers, {sent_count} alerts generated.")


if __name__ == "__main__":
    main()
