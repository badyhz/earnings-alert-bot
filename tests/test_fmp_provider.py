import pytest
from unittest.mock import patch, MagicMock
import httpx

from providers.fmp_provider import FmpProvider, FmpProviderError


MOCK_EARNINGS_CALENDAR = [
    {
        "date": "2026-05-27",
        "symbol": "AAPL",
        "eps": 1.50,
        "epsEstimated": 1.45,
        "revenue": 95000000000,
        "revenueEstimated": 93000000000,
        "time": "After Market Close",
    },
    {
        "date": "2026-05-28",
        "symbol": "NVDA",
        "eps": 6.12,
        "epsEstimated": 5.58,
        "revenue": 38200000000,
        "revenueEstimated": 36000000000,
        "time": "After Market Close",
    },
    {
        "date": "2026-05-27",
        "symbol": "MRVL",
        "eps": 0.83,
        "epsEstimated": 0.79,
        "revenue": 24700000000,
        "revenueEstimated": 24000000000,
        "time": "After Market Close",
    },
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
        resp.status_code = 200
        resp.json.return_value = MOCK_EARNINGS_CALENDAR
    elif "quote" in url:
        symbol = url.split("/quote/")[1].split("?")[0] if "/quote/" in url else ""
        matching = [q for q in MOCK_QUOTE if q["symbol"] == symbol]
        resp.status_code = 200
        resp.json.return_value = matching if matching else []
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

    @patch("providers.fmp_provider.httpx.get", side_effect=mock_httpx_get)
    def test_date_range_used(self, mock_get):
        p = FmpProvider(api_key="test_key")
        data = p.get_earnings("AAPL")

        assert data is not None
        assert data.ticker == "AAPL"
        # Verify the first call (earning_calendar) contained date range params
        first_call_url = mock_get.call_args_list[0][0][0]
        assert "from=" in first_call_url
        assert "to=" in first_call_url
        assert "earning_calendar" in first_call_url

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
    def test_ticker_not_in_calendar(self, mock_get):
        resp = MagicMock()
        resp.status_code = 200
        resp.json.return_value = MOCK_EARNINGS_CALENDAR
        mock_get.return_value = resp

        p = FmpProvider(api_key="test_key")
        data = p.get_earnings("TSLA")
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

    @patch("providers.fmp_provider.httpx.get", side_effect=mock_httpx_get)
    def test_debug_mode(self, mock_get, capsys):
        p = FmpProvider(api_key="test_key", debug=True)
        data = p.get_earnings("MRVL")
        captured = capsys.readouterr()
        assert "FMP-DEBUG" in captured.err
        assert "Date range" in captured.err


class TestFmpProviderBatch:
    @patch("providers.fmp_provider.httpx.get", side_effect=mock_httpx_get)
    def test_batch(self, mock_get):
        p = FmpProvider(api_key="test_key")
        results = p.get_earnings_batch(["MRVL", "UNKNOWN"])
        assert len(results) == 1
        assert results[0].ticker == "MRVL"

    @patch("providers.fmp_provider.httpx.get", side_effect=mock_httpx_get)
    def test_batch_multiple(self, mock_get):
        p = FmpProvider(api_key="test_key")
        results = p.get_earnings_batch(["MRVL", "NVDA", "AAPL"])
        assert len(results) == 3
        tickers = {r.ticker for r in results}
        assert tickers == {"MRVL", "NVDA", "AAPL"}
