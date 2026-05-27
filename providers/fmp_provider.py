import os
import sys
from datetime import datetime, timedelta
from typing import Optional

import httpx

from .base import EarningsData, EarningsProvider

FMP_BASE = "https://financialmodelingprep.com/api/v3"
FMP_STABLE_BASE = "https://financialmodelingprep.com/stable"
REQUEST_TIMEOUT = 15.0


class FmpProviderError(Exception):
    pass


class FmpProvider(EarningsProvider):
    def __init__(self, api_key: Optional[str] = None, debug: bool = False):
        self.api_key = api_key or os.environ.get("FMP_API_KEY", "")
        if not self.api_key:
            raise FmpProviderError("FMP_API_KEY environment variable is required")
        self.debug = debug

    def _log(self, msg: str):
        if self.debug:
            print(f"[FMP-DEBUG] {msg}", file=sys.stderr)

    def _get(self, endpoint: str, base: str = FMP_BASE) -> dict:
        url = f"{base}{endpoint}"
        self._log(f"GET {url[:80]}...")
        try:
            resp = httpx.get(url, timeout=REQUEST_TIMEOUT)
        except httpx.TimeoutException:
            raise FmpProviderError(f"Timeout fetching {endpoint}")
        except httpx.RequestError as e:
            raise FmpProviderError(f"Request error: {e}")

        if resp.status_code != 200:
            raise FmpProviderError(f"HTTP {resp.status_code} from {endpoint}")

        try:
            data = resp.json()
        except Exception:
            raise FmpProviderError(f"Invalid JSON from {endpoint}")

        return data

    def _date_range(self) -> tuple[str, str]:
        today = datetime.now().date()
        from_date = (today - timedelta(days=14)).isoformat()
        to_date = (today + timedelta(days=30)).isoformat()
        return from_date, to_date

    def _fetch_earnings_calendar(self, ticker: str) -> Optional[dict]:
        from_date, to_date = self._date_range()
        self._log(f"Date range: {from_date} to {to_date}")

        endpoint = f"/earnings-calendar?from={from_date}&to={to_date}&apikey={self.api_key}"
        data = self._get(endpoint, base=FMP_STABLE_BASE)

        if not isinstance(data, list):
            self._log(f"Unexpected response type: {type(data)}")
            return None

        self._log(f"Calendar records returned: {len(data)}")

        for entry in data:
            if entry.get("symbol", "").upper() == ticker.upper():
                self._log(f"Found match: {entry.get('symbol')} on {entry.get('date')}")
                return entry

        self._log(f"No match found for {ticker} in {len(data)} records")
        return None

    def _fetch_quote(self, ticker: str) -> Optional[dict]:
        data = self._get(f"/quote/{ticker}?apikey={self.api_key}")
        if not isinstance(data, list) or not data:
            return None
        return data[0]

    def _safe_float(self, val) -> Optional[float]:
        if val is None:
            return None
        try:
            return float(val)
        except (ValueError, TypeError):
            return None

    def _parse_timing(self, time_str: Optional[str]) -> str:
        if not time_str:
            return "unknown"
        time_str = str(time_str).lower()
        if "before" in time_str or "bmo" in time_str:
            return "before_market"
        if "after" in time_str or "amc" in time_str:
            return "after_market"
        if "during" in time_str:
            return "during_market"
        return "unknown"

    def get_earnings(self, ticker: str) -> Optional[EarningsData]:
        ticker = ticker.upper()

        try:
            cal = self._fetch_earnings_calendar(ticker)
        except FmpProviderError:
            return None
        if not cal:
            return None

        earnings_date = cal.get("date", "")
        if not earnings_date:
            return None

        actual_eps = self._safe_float(cal.get("eps"))
        consensus_eps = self._safe_float(cal.get("epsEstimated"))
        actual_revenue = self._safe_float(cal.get("revenue"))
        consensus_revenue = self._safe_float(cal.get("revenueEstimated"))
        timing = self._parse_timing(cal.get("time"))

        # Convert revenue to billions if in raw dollars
        revenue_unit = "B"
        if actual_revenue is not None and actual_revenue > 1_000_000_000:
            actual_revenue = round(actual_revenue / 1_000_000_000, 2)
        if consensus_revenue is not None and consensus_revenue > 1_000_000_000:
            consensus_revenue = round(consensus_revenue / 1_000_000_000, 2)

        # Fetch quote for price
        current_price = None
        price_move_pct = None
        session = "regular"
        try:
            quote = self._fetch_quote(ticker)
            if quote:
                current_price = self._safe_float(quote.get("price"))
                price_move_pct = self._safe_float(quote.get("changesPercentage"))
                if price_move_pct is not None:
                    price_move_pct = round(price_move_pct, 2)
        except FmpProviderError:
            pass

        return EarningsData(
            ticker=ticker,
            company_name=cal.get("symbol", ticker),
            earnings_date=earnings_date,
            earnings_timing=timing,
            actual_eps=actual_eps,
            consensus_eps=consensus_eps,
            actual_revenue=actual_revenue,
            consensus_revenue=consensus_revenue,
            revenue_unit=revenue_unit,
            current_price=current_price,
            price_move_pct=price_move_pct,
            session=session,
            source="fmp",
        )

    def get_earnings_batch(self, tickers: list[str]) -> list[EarningsData]:
        results = []
        for ticker in tickers:
            try:
                ed = self.get_earnings(ticker)
                if ed:
                    results.append(ed)
            except FmpProviderError:
                continue
        return results
