from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Optional


@dataclass
class EarningsData:
    ticker: str
    company_name: str
    earnings_date: str
    earnings_timing: str  # "before_market", "after_market", "during_market", "unknown"
    actual_eps: Optional[float] = None
    consensus_eps: Optional[float] = None
    actual_revenue: Optional[float] = None
    consensus_revenue: Optional[float] = None
    revenue_unit: str = "B"
    guidance_revenue_next_q: Optional[float] = None
    consensus_revenue_next_q: Optional[float] = None
    current_price: Optional[float] = None
    price_move_pct: Optional[float] = None
    session: str = "regular"  # "regular", "pre_market", "after_hours"
    source: str = "unknown"

    def to_dict(self) -> dict:
        return {
            "ticker": self.ticker,
            "company_name": self.company_name,
            "earnings_date": self.earnings_date,
            "earnings_timing": self.earnings_timing,
            "actual_eps": self.actual_eps,
            "consensus_eps": self.consensus_eps,
            "actual_revenue": self.actual_revenue,
            "consensus_revenue": self.consensus_revenue,
            "revenue_unit": self.revenue_unit,
            "guidance_revenue_next_q": self.guidance_revenue_next_q,
            "consensus_revenue_next_q": self.consensus_revenue_next_q,
            "current_price": self.current_price,
            "price_move_pct": self.price_move_pct,
            "session": self.session,
            "source": self.source,
        }


class EarningsProvider(ABC):
    @abstractmethod
    def get_earnings(self, ticker: str) -> Optional[EarningsData]:
        """Fetch earnings data for a single ticker."""

    @abstractmethod
    def get_earnings_batch(self, tickers: list[str]) -> list[EarningsData]:
        """Fetch earnings data for multiple tickers."""
