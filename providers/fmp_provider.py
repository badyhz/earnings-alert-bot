import os
import sys
from datetime import datetime, timedelta
from typing import Optional, Union

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

    def _get_optional(self, endpoint: str, base: str = FMP_STABLE_BASE) -> Optional[Union[list, dict]]:
        try:
            return self._get(endpoint, base=base)
        except FmpProviderError as e:
            self._log(f"Fallback failed: {e}")
            return None

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

    def _fetch_analyst_estimates(self, ticker: str) -> Optional[list]:
        self._log(f"Trying fallback: analyst-estimates for {ticker}")
        endpoint = f"/analyst-estimates?symbol={ticker}&apikey={self.api_key}"
        data = self._get_optional(endpoint)
        if isinstance(data, list) and data:
            self._log(f"analyst-estimates returned {len(data)} records")
            return data
        self._log("analyst-estimates: no data")
        return None

    def _fetch_income_statement(self, ticker: str) -> Optional[list]:
        self._log(f"Trying fallback: income-statement for {ticker}")
        endpoint = f"/income-statement?symbol={ticker}&period=quarter&limit=4&apikey={self.api_key}"
        data = self._get_optional(endpoint)
        if isinstance(data, list) and data:
            self._log(f"income-statement returned {len(data)} records")
            return data
        self._log("income-statement: no data")
        return None

    def _enrich_eps_from_income_statement(self, ticker: str, actual_eps: Optional[float]) -> Optional[float]:
        if actual_eps is not None:
            return actual_eps
        self._log("actual EPS fallback: trying income-statement epsdiluted")
        statements = self._fetch_income_statement(ticker)
        if not statements:
            self._log("actual EPS fallback unavailable / unsupported")
            return None
        eps = self._safe_float(statements[0].get("epsdiluted"))
        if eps is not None:
            self._log(f"Filled actual EPS from income-statement epsdiluted: {eps}")
            return eps
        self._log("actual EPS fallback unavailable / unsupported")
        return None

    def _enrich_from_estimates(
        self, ticker: str, earnings_date: str,
        consensus_eps: Optional[float], consensus_revenue: Optional[float]
    ) -> tuple[Optional[float], Optional[float]]:
        if consensus_eps is not None and consensus_revenue is not None:
            return consensus_eps, consensus_revenue
        estimates = self._fetch_analyst_estimates(ticker)
        if not estimates:
            return consensus_eps, consensus_revenue
        best_entry = None
        for entry in estimates:
            if entry.get("date") == earnings_date:
                best_entry = entry
                break
        if not best_entry:
            best_entry = estimates[0]
        if consensus_eps is None:
            eps_est = self._safe_float(best_entry.get("estimatedEarningPerShare"))
            if eps_est is not None:
                self._log(f"Filled consensus EPS from analyst-estimates: {eps_est}")
                consensus_eps = eps_est
        if consensus_revenue is None:
            rev_est = self._safe_float(best_entry.get("estimatedRevenue"))
            if rev_est is not None:
                if rev_est > 1_000_000_000:
                    rev_est = round(rev_est / 1_000_000_000, 2)
                self._log(f"Filled consensus revenue from analyst-estimates: {rev_est}")
                consensus_revenue = rev_est
        return consensus_eps, consensus_revenue

    def _enrich_revenue_from_income_statement(self, ticker: str, actual_revenue: Optional[float]) -> Optional[float]:
        if actual_revenue is not None:
            return actual_revenue
        statements = self._fetch_income_statement(ticker)
        if not statements:
            return None
        rev = self._safe_float(statements[0].get("revenue"))
        if rev is not None:
            if rev > 1_000_000_000:
                rev = round(rev / 1_000_000_000, 2)
            self._log(f"Filled actual revenue from income-statement: {rev}")
        return rev

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

        # Fallback enrichment if fields are missing
        missing_eps = actual_eps is None or consensus_eps is None
        missing_rev = actual_revenue is None or consensus_revenue is None

        if missing_eps or missing_rev:
            self._log(f"Fields missing (eps={actual_eps}, consensus_eps={consensus_eps}, rev={actual_revenue}, consensus_rev={consensus_revenue}), trying fallbacks...")

            # EPS fallback: income-statement epsdiluted (no earnings-surprises on stable free tier)
            if actual_eps is None:
                actual_eps = self._enrich_eps_from_income_statement(ticker, actual_eps)

            if consensus_eps is None or consensus_revenue is None:
                consensus_eps, consensus_revenue = self._enrich_from_estimates(ticker, earnings_date, consensus_eps, consensus_revenue)

            if actual_revenue is None:
                actual_revenue = self._enrich_revenue_from_income_statement(ticker, actual_revenue)

        self._log(f"Final: actual_eps={actual_eps}, consensus_eps={consensus_eps}, actual_revenue={actual_revenue}, consensus_revenue={consensus_revenue}")

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
