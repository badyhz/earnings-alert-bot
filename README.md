# Earnings Intelligence Bot

财报事件监控机器人。获取美股财报数据，对比实际与预期，生成中文交易解读，推送到飞书。

**不是交易机器人。不下单。不调用券商API。仅告警和分析。**

## Quick Start

```bash
# Clone and setup
cd earnings-alert-bot
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt

# Copy and configure env
cp .env.example .env
# Edit .env with your Feishu webhook

# Run with mock data (dry-run)
python earnings_bot.py --provider mock --dry-run

# Run single ticker
python earnings_bot.py --provider mock --ticker MRVL --dry-run

# Run all watchlist tickers
python earnings_bot.py --provider mock --dry-run
```

## Environment Setup

### Create .env file

```bash
cd /Users/winnie/Documents/trae_projects/earnings-alert-bot
cp .env.example .env
nano .env  # or use your preferred editor
```

### .env contents

```bash
# Required for FMP provider
FMP_API_KEY=your_fmp_api_key_here

# Required for Feishu sending
FEISHU_WEBHOOK=https://open.feishu.cn/open-apis/bot/v2/hook/xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx

# Optional: Feishu webhook signing secret
FEISHU_SECRET=
```

### Export environment variables

```bash
# Option 1: Source .env file
set -a
source .env
set +a

# Option 2: Export manually
export FMP_API_KEY="your_fmp_api_key_here"
export FEISHU_WEBHOOK="https://open.feishu.cn/open-apis/bot/v2/hook/xxxxxxxx"
export FEISHU_SECRET=""  # optional
```

## Safe Command Checklist

### 1. Mock dry-run (no API key needed)

```bash
python earnings_bot.py --provider mock --ticker MRVL --dry-run
```

### 2. FMP dry-run (requires FMP_API_KEY)

```bash
python earnings_bot.py --provider fmp --ticker MRVL --dry-run
```

### 3. Feishu send test (requires FEISHU_WEBHOOK)

```bash
python earnings_bot.py --provider mock --ticker MRVL --send
```

## Environment Variables

```bash
# Required for sending
FEISHU_WEBHOOK=https://open.feishu.cn/open-apis/bot/v2/hook/xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx

# Optional: Feishu webhook signing
FEISHU_SECRET=your_secret_here

# Required for FMP provider
FMP_API_KEY=your_fmp_api_key
```

## Feishu Webhook Setup

1. Open Feishu, go to target group chat
2. Click "Settings" -> "Bots" -> "Add Bot" -> "Custom Bot"
3. Copy the webhook URL
4. (Optional) Enable "Signature Verification" and copy the secret
5. Set `FEISHU_WEBHOOK` and optionally `FEISHU_SECRET` in `.env`

## CLI Usage

```bash
# Dry-run (print only, no send)
python earnings_bot.py --provider mock --dry-run
python earnings_bot.py --provider mock --ticker MRVL --dry-run

# Send to Feishu
python earnings_bot.py --provider mock --send
python earnings_bot.py --provider fmp --ticker MRVL --send

# Force ignore cooldown
python earnings_bot.py --provider mock --dry-run --force
```

## Configuration

Edit `config/watchlist.yaml`:

```yaml
tickers:
  - MRVL
  - NVDA
  - AVGO

thresholds:
  eps_surprise_strong_pct: 5
  revenue_surprise_strong_pct: 3
  price_move_alert_pct: 5
  price_move_strong_pct: 10
  cooldown_hours: 12
```

## Alert Classification

| Classification | Condition |
|---|---|
| STRONG_BEAT | EPS surprise >= 5% AND revenue surprise >= 3% |
| MILD_BEAT | EPS > 0 AND revenue > 0 (not strong) |
| MIXED | One beats, other misses |
| MISS | EPS < 0 AND revenue < 0 |
| PRICE_OVERREACTION | Price move >= 10% but only mild beat |
| PRICE_RESILIENCE | Miss but price move >= 0 |

## Cron Example

```bash
# Run every day at 5:30 PM ET (after market close)
30 17 * * 1-5 cd /path/to/earnings-alert-bot && .venv/bin/python earnings_bot.py --provider mock --send >> /var/log/earnings-bot.log 2>&1
```

## systemd Service Example

```ini
# /etc/systemd/system/earnings-bot.service
[Unit]
Description=Earnings Intelligence Bot
After=network.target

[Service]
Type=oneshot
WorkingDirectory=/path/to/earnings-alert-bot
ExecStart=/path/to/earnings-alert-bot/.venv/bin/python earnings_bot.py --provider mock --send
EnvironmentFile=/path/to/earnings-alert-bot/.env

[Install]
WantedBy=multi-user.target
```

Timer:
```ini
# /etc/systemd/system/earnings-bot.timer
[Unit]
Description=Run earnings bot daily

[Timer]
OnCalendar=Mon..Fri 17:30
Persistent=true

[Install]
WantedBy=timers.target
```

## Data Provider Limitations

- **Mock provider**: Test data only. Hardcoded sample earnings for MRVL, NVDA, AVGO, AMD, CRDO, COHR, LITE.
- **FMP provider**: Uses [Financial Modeling Prep](https://financialmodelingprep.com/) API. Requires `FMP_API_KEY`.
  - Earnings calendar: `/earning_calendar` endpoint. Only returns upcoming/recent earnings, not historical.
  - Price data: `/quote` endpoint. Regular session price only; no after-hours/pre-market data.
  - Revenue is returned in raw dollars and auto-converted to billions.
  - `earnings_timing` is parsed from the `time` field ("Before Market Open", "After Market Close").
  - `guidance_revenue_next_q` is not available from FMP and will be `None`.
  - `price_move_pct` uses `changesPercentage` from quote (regular session change, not after-hours).
  - Free tier: 250 requests/day. Use mock provider for development.

## Deduplication

Alerts are deduped by `ticker|earnings_date|classification` key. Same alert won't be resent within `cooldown_hours` unless `--force` is passed.

State is stored in `state/sent_alerts.json`.

## Tests

```bash
pytest tests/ -v
```

## Safety Notes

- This bot does NOT place trades
- This bot does NOT call broker APIs
- This is an alert/analysis tool only
- All trading decisions are your own responsibility
