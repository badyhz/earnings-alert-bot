from datetime import date, timedelta
from typing import Optional

from .base import EarningsData, EarningsProvider

MOCK_DATA: dict[str, dict] = {
    "MRVL": {
        "company_name": "Marvell Technology",
        "earnings_date": "2026-05-27",
        "earnings_timing": "after_market",
        "actual_eps": 0.83,
        "consensus_eps": 0.79,
        "actual_revenue": 24.7,
        "consensus_revenue": 24.0,
        "revenue_unit": "B",
        "guidance_revenue_next_q": 26.8,
        "consensus_revenue_next_q": 26.0,
        "current_price": 200.0,
        "price_move_pct": 11.8,
        "session": "after_hours",
    },
    "NVDA": {
        "company_name": "NVIDIA Corporation",
        "earnings_date": "2026-05-28",
        "earnings_timing": "after_market",
        "actual_eps": 6.12,
        "consensus_eps": 5.58,
        "actual_revenue": 38.2,
        "consensus_revenue": 36.0,
        "revenue_unit": "B",
        "guidance_revenue_next_q": 41.0,
        "consensus_revenue_next_q": 39.5,
        "current_price": 1150.0,
        "price_move_pct": 8.5,
        "session": "after_hours",
    },
    "AVGO": {
        "company_name": "Broadcom Inc.",
        "earnings_date": "2026-05-29",
        "earnings_timing": "after_market",
        "actual_eps": 12.50,
        "consensus_eps": 12.35,
        "actual_revenue": 14.5,
        "consensus_revenue": 14.2,
        "revenue_unit": "B",
        "guidance_revenue_next_q": 15.0,
        "consensus_revenue_next_q": 14.8,
        "current_price": 1850.0,
        "price_move_pct": 3.2,
        "session": "after_hours",
    },
    "AMD": {
        "company_name": "Advanced Micro Devices",
        "earnings_date": "2026-05-06",
        "earnings_timing": "after_market",
        "actual_eps": 1.20,
        "consensus_eps": 1.18,
        "actual_revenue": 7.4,
        "consensus_revenue": 7.1,
        "revenue_unit": "B",
        "guidance_revenue_next_q": None,
        "consensus_revenue_next_q": None,
        "current_price": 165.0,
        "price_move_pct": 4.5,
        "session": "after_hours",
    },
    "CRDO": {
        "company_name": "Credo Technology Group",
        "earnings_date": "2026-05-28",
        "earnings_timing": "after_market",
        "actual_eps": 0.52,
        "consensus_eps": 0.48,
        "actual_revenue": 0.18,
        "consensus_revenue": 0.16,
        "revenue_unit": "B",
        "guidance_revenue_next_q": None,
        "consensus_revenue_next_q": None,
        "current_price": 85.0,
        "price_move_pct": 7.2,
        "session": "after_hours",
    },
    "COHR": {
        "company_name": "Coherent Corp.",
        "earnings_date": "2026-05-07",
        "earnings_timing": "after_market",
        "actual_eps": 0.95,
        "consensus_eps": 1.02,
        "actual_revenue": 1.45,
        "consensus_revenue": 1.50,
        "revenue_unit": "B",
        "guidance_revenue_next_q": None,
        "consensus_revenue_next_q": None,
        "current_price": 92.0,
        "price_move_pct": -5.8,
        "session": "after_hours",
    },
    "LITE": {
        "company_name": "Lumentum Holdings",
        "earnings_date": "2026-05-06",
        "earnings_timing": "after_market",
        "actual_eps": 0.88,
        "consensus_eps": 0.82,
        "actual_revenue": 0.42,
        "consensus_revenue": 0.40,
        "revenue_unit": "B",
        "guidance_revenue_next_q": None,
        "consensus_revenue_next_q": None,
        "current_price": 105.0,
        "price_move_pct": 6.1,
        "session": "after_hours",
    },
}


class MockProvider(EarningsProvider):
    def get_earnings(self, ticker: str) -> Optional[EarningsData]:
        ticker = ticker.upper()
        data = MOCK_DATA.get(ticker)
        if not data:
            return None
        return EarningsData(ticker=ticker, source="mock", **data)

    def get_earnings_batch(self, tickers: list[str]) -> list[EarningsData]:
        results = []
        for ticker in tickers:
            ed = self.get_earnings(ticker)
            if ed:
                results.append(ed)
        return results
