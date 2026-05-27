import pytest
from unittest.mock import patch, MagicMock
import httpx

from providers.fmp_provider import FmpProvider, FmpProviderError


MOCK_EARNINGS_CALENDAR = [
    {
        "date": "2026-05-27",
        "symbol": "MRVL",
        "eps": 0.83,
        "epsEstimated": 0.79,
        "revenue": 24700000000,
        "revenueEstimated": 24000000000,
        "time": "After Market Close",
        "updatedFromDate": "2026-05-27",
    }
]

MOCK_QUOTE = [
    {
        "symbol": "MRVL",
        "price": 200.0,
        "changesPercentage": 11.8,
        "change": 21.12,
        "volume": 50000000,
    }
]


def mock_httpx_get(url, timeout=None):
    resp = MagicMock()
    if "earning_calendar" in url:
        if "UNKNOWN" in url:
            resp.status_code = 200
            resp.json.return_value = []
        else:
            resp.status_code = 200
            resp.json.return_value = MOCK_EARNINGS_CALENDAR
    elif "quote" in url:
        if "UNKNOWN" in url:
            resp.status_code = 200
            resp.json.return_value = []
        else:
            resp.status_code = 200
            resp.json.return_value = MOCK_QUOTE
    else:
        resp.status_code = 404
        resp.json.return_value = {"Error Message": "not found"}
    return resp


class TestFmpProviderInit:
    def test_missing_api_key(self):
        with pytest.raises(FmpProviderError, match="FMP_API_KEY"):
            FmpProvider(api_key="")

    def test_with_api_key(self):
        p = FmpProvider(api_key="test_key")
        assert p.api_key == "test_key"


class TestFmpProviderGetEarnings:
    @patch("providers.fmp_provider.httpx.get", side_effect=mock_httpx_get)
    def test_full_data(self, mock_get):
        p = FmpProvider(api_key="test_key")
        data = p.get_earnings("MRVL")

        assert data is not None
        assert data.ticker == "MRVL"
        assert data.earnings_date == "2026-05-27"
        assert data.actual_eps == 0.83
        assert data.consensus_eps == 0.79
        assert data.actual_revenue == 24.7
        assert data.consensus_revenue == 24.0
        assert data.revenue_unit == "B"
        assert data.current_price == 200.0
        assert data.price_move_pct == 11.8
        assert data.source == "fmp"

    @patch("providers.fmp_provider.httpx.get", side_effect=mock_httpx_get)
    def test_earnings_timing(self, mock_get):
        p = FmpProvider(api_key="test_key")
        data = p.get_earnings("MRVL")
        assert data.earnings_timing == "after_market"

    @patch("providers.fmp_provider.httpx.get")
    def test_empty_calendar(self, mock_get):
        resp = MagicMock()
        resp.status_code = 200
        resp.json.return_value = []
        mock_get.return_value = resp

        p = FmpProvider(api_key="test_key")
        data = p.get_earnings("UNKNOWN")
        assert data is None

    @patch("providers.fmp_provider.httpx.get")
    def test_no_earnings_date(self, mock_get):
        resp = MagicMock()
        resp.status_code = 200
        resp.json.return_value = [{"symbol": "TEST", "date": "", "eps": None}]
        mock_get.return_value = resp

        p = FmpProvider(api_key="test_key")
        data = p.get_earnings("TEST")
        assert data is None

    @patch("providers.fmp_provider.httpx.get")
    def test_timeout(self, mock_get):
        mock_get.side_effect = httpx.TimeoutException("timeout")

        p = FmpProvider(api_key="test_key")
        data = p.get_earnings("MRVL")
        assert data is None

    @patch("providers.fmp_provider.httpx.get")
    def test_http_error(self, mock_get):
        resp = MagicMock()
        resp.status_code = 429
        mock_get.return_value = resp

        p = FmpProvider(api_key="test_key")
        data = p.get_earnings("MRVL")
        assert data is None

    @patch("providers.fmp_provider.httpx.get")
    def test_invalid_json(self, mock_get):
        resp = MagicMock()
        resp.status_code = 200
        resp.json.side_effect = ValueError("bad json")
        mock_get.return_value = resp

        p = FmpProvider(api_key="test_key")
        data = p.get_earnings("MRVL")
        assert data is None

    @patch("providers.fmp_provider.httpx.get")
    def test_request_error(self, mock_get):
        mock_get.side_effect = httpx.RequestError("connection failed")

        p = FmpProvider(api_key="test_key")
        data = p.get_earnings("MRVL")
        assert data is None

    @patch("providers.fmp_provider.httpx.get", side_effect=mock_httpx_get)
    def test_missing_optional_fields(self, mock_get):
        """Quote fails but earnings calendar works - should still return data."""
        def custom_get(url, timeout=None):
            if "earning_calendar" in url:
                resp = MagicMock()
                resp.status_code = 200
                resp.json.return_value = [{
                    "date": "2026-05-27",
                    "symbol": "MRVL",
                    "eps": None,
                    "epsEstimated": None,
                    "revenue": None,
                    "revenueEstimated": None,
                    "time": None,
                }]
                return resp
            raise httpx.RequestError("no quote")

        mock_get.side_effect = custom_get
        p = FmpProvider(api_key="test_key")
        data = p.get_earnings("MRVL")

        assert data is not None
        assert data.actual_eps is None
        assert data.consensus_eps is None
        assert data.actual_revenue is None
        assert data.consensus_revenue is None
        assert data.current_price is None
        assert data.price_move_pct is None


class TestFmpProviderBatch:
    @patch("providers.fmp_provider.httpx.get", side_effect=mock_httpx_get)
    def test_batch(self, mock_get):
        p = FmpProvider(api_key="test_key")
        results = p.get_earnings_batch(["MRVL", "UNKNOWN"])
        assert len(results) == 1
        assert results[0].ticker == "MRVL"
