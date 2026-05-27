import os
from datetime import datetime
from typing import Optional

import httpx

from .base import EarningsData, EarningsProvider

FMP_BASE = "https://financialmodelingprep.com/api/v3"
REQUEST_TIMEOUT = 10.0


class FmpProviderError(Exception):
    pass


class FmpProvider(EarningsProvider):
    def __init__(self, api_key: Optional[str] = None):
        self.api_key = api_key or os.environ.get("FMP_API_KEY", "")
        if not self.api_key:
            raise FmpProviderError("FMP_API_KEY environment variable is required")

    def _get(self, endpoint: str) -> dict:
        url = f"{FMP_BASE}{endpoint}"
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

    def _fetch_earnings_calendar(self, ticker: str) -> Optional[dict]:
        data = self._get(f"/earning_calendar?symbol={ticker}&apikey={self.api_key}")
        if not isinstance(data, list) or not data:
            return None
        return data[0]

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
        if "before" in time_str or "amc" not in time_str and "bmo" in time_str:
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
                # FMP doesn't provide after-hours move directly
                # Use day change as approximation
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
