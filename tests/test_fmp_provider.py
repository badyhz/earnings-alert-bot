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

# Calendar entry with missing EPS/revenue (like server-side NVDA case)
MOCK_CALENDAR_SPARSE = [
    {
        "date": "2026-05-20",
        "symbol": "NVDA",
        "eps": None,
        "epsEstimated": None,
        "revenue": None,
        "revenueEstimated": None,
        "time": "After Market Close",
    },
]

MOCK_ANALYST_ESTIMATES = [
    {"date": "2026-05-20", "estimatedEarningPerShare": 0.76, "estimatedRevenue": 28500000000},
    {"date": "2026-08-15", "estimatedEarningPerShare": 0.85, "estimatedRevenue": 30000000000},
]

MOCK_INCOME_STATEMENT = [
    {"date": "2026-04-30", "revenue": 28000000000, "epsdiluted": 0.82, "symbol": "NVDA"},
    {"date": "2026-01-31", "revenue": 26000000000, "epsdiluted": 0.70, "symbol": "NVDA"},
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
    if "earnings-calendar" in url:
        resp.status_code = 200
        resp.json.return_value = MOCK_EARNINGS_CALENDAR
    elif "analyst-estimates" in url:
        resp.status_code = 200
        resp.json.return_value = MOCK_ANALYST_ESTIMATES
    elif "income-statement" in url:
        resp.status_code = 200
        resp.json.return_value = MOCK_INCOME_STATEMENT
    elif "quote" in url:
        symbol = url.split("/quote/")[1].split("?")[0] if "/quote/" in url else ""
        matching = [q for q in MOCK_QUOTE if q["symbol"] == symbol]
        resp.status_code = 200
        resp.json.return_value = matching if matching else []
    else:
        resp.status_code = 404
        resp.json.return_value = {"Error Message": "not found"}
    return resp


def mock_httpx_get_sparse(url, timeout=None):
    """Mock that returns sparse calendar + fallback data for NVDA."""
    resp = MagicMock()
    if "earnings-calendar" in url:
        resp.status_code = 200
        resp.json.return_value = MOCK_CALENDAR_SPARSE
    elif "analyst-estimates" in url:
        resp.status_code = 200
        resp.json.return_value = MOCK_ANALYST_ESTIMATES
    elif "income-statement" in url:
        resp.status_code = 200
        resp.json.return_value = MOCK_INCOME_STATEMENT
    elif "quote" in url:
        resp.status_code = 200
        resp.json.return_value = [{"symbol": "NVDA", "price": 130.0, "changesPercentage": 2.5}]
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
        first_call_url = mock_get.call_args_list[0][0][0]
        assert "from=" in first_call_url
        assert "to=" in first_call_url
        assert "/stable/earnings-calendar" in first_call_url
        assert "api/v3/earning_calendar" not in first_call_url

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
    def test_debug_mode(self, mock_get, capsys):
        p = FmpProvider(api_key="test_key", debug=True)
        data = p.get_earnings("MRVL")
        captured = capsys.readouterr()
        assert "FMP-DEBUG" in captured.err
        assert "Date range" in captured.err


class TestFallbackEnrichment:
    @patch("providers.fmp_provider.httpx.get", side_effect=mock_httpx_get_sparse)
    def test_sparse_calendar_fills_from_fallbacks(self, mock_get):
        """NVDA-like case: calendar found but EPS/revenue missing -> fallback fills data."""
        p = FmpProvider(api_key="test_key")
        data = p.get_earnings("NVDA")

        assert data is not None
        assert data.ticker == "NVDA"
        assert data.earnings_date == "2026-05-20"
        # actual EPS from income-statement epsdiluted (latest quarter)
        assert data.actual_eps == 0.82
        # consensus EPS from analyst-estimates (matching date)
        assert data.consensus_eps == 0.76
        # actual revenue from income-statement (latest quarter, converted to B)
        assert data.actual_revenue == 28.0
        # consensus revenue from analyst-estimates (matching date, converted to B)
        assert data.consensus_revenue == 28.5

    @patch("providers.fmp_provider.httpx.get", side_effect=mock_httpx_get_sparse)
    def test_fallback_debug_output(self, mock_get, capsys):
        p = FmpProvider(api_key="test_key", debug=True)
        data = p.get_earnings("NVDA")
        captured = capsys.readouterr()

        assert "Fields missing" in captured.err
        assert "income-statement" in captured.err
        assert "analyst-estimates" in captured.err
        assert "Filled actual EPS from income-statement epsdiluted" in captured.err
        assert "Filled consensus EPS from analyst-estimates" in captured.err
        assert "Filled consensus revenue from analyst-estimates" in captured.err
        assert "Filled actual revenue from income-statement" in captured.err

    @patch("providers.fmp_provider.httpx.get")
    def test_fallback_all_fail_gracefully(self, mock_get):
        """Calendar found, all fallbacks fail -> data has Nones, no crash."""
        def failing_get(url, timeout=None):
            resp = MagicMock()
            if "earnings-calendar" in url:
                resp.status_code = 200
                resp.json.return_value = MOCK_CALENDAR_SPARSE
            else:
                resp.status_code = 500
                resp.json.return_value = {"error": "server error"}
            return resp

        mock_get.side_effect = failing_get
        p = FmpProvider(api_key="test_key")
        data = p.get_earnings("NVDA")

        assert data is not None
        assert data.ticker == "NVDA"
        assert data.actual_eps is None
        assert data.consensus_eps is None
        assert data.actual_revenue is None
        assert data.consensus_revenue is None

    @patch("providers.fmp_provider.httpx.get")
    def test_fallback_network_errors_graceful(self, mock_get):
        """Calendar found, fallbacks throw network errors -> no crash."""
        call_count = [0]
        def error_get(url, timeout=None):
            call_count[0] += 1
            if call_count[0] == 1:
                resp = MagicMock()
                resp.status_code = 200
                resp.json.return_value = MOCK_CALENDAR_SPARSE
                return resp
            raise httpx.RequestError("connection failed")

        mock_get.side_effect = error_get
        p = FmpProvider(api_key="test_key")
        data = p.get_earnings("NVDA")

        assert data is not None
        assert data.actual_eps is None

    @patch("providers.fmp_provider.httpx.get", side_effect=mock_httpx_get)
    def test_no_fallback_when_data_complete(self, mock_get):
        """When calendar has full data, no fallback endpoints called."""
        p = FmpProvider(api_key="test_key")
        data = p.get_earnings("MRVL")

        assert data is not None
        assert data.actual_eps == 0.83
        # Only 2 calls: earnings-calendar + quote (no fallbacks)
        assert mock_get.call_count == 2
        urls = [call[0][0] for call in mock_get.call_args_list]
        assert not any("analyst-estimates" in u for u in urls)
        assert not any("income-statement" in u for u in urls)

    @patch("providers.fmp_provider.httpx.get")
    def test_eps_fallback_unavailable_debug(self, mock_get, capsys):
        """When income-statement has no epsdiluted, debug says fallback unavailable."""
        def custom_get(url, timeout=None):
            resp = MagicMock()
            if "earnings-calendar" in url:
                resp.status_code = 200
                resp.json.return_value = MOCK_CALENDAR_SPARSE
            elif "income-statement" in url:
                resp.status_code = 200
                resp.json.return_value = [{"date": "2026-04-30", "revenue": 28000000000}]  # no epsdiluted
            elif "analyst-estimates" in url:
                resp.status_code = 200
                resp.json.return_value = []
            else:
                resp.status_code = 200
                resp.json.return_value = [{"symbol": "NVDA", "price": 130.0, "changesPercentage": 1.0}]
            return resp

        mock_get.side_effect = custom_get
        p = FmpProvider(api_key="test_key", debug=True)
        data = p.get_earnings("NVDA")
        captured = capsys.readouterr()

        assert data is not None
        assert data.actual_eps is None
        assert "actual EPS fallback unavailable / unsupported" in captured.err

    @patch("providers.fmp_provider.httpx.get")
    def test_eps_fallback_404_no_noise(self, mock_get, capsys):
        """When income-statement returns 404, no raw 404 noise in debug."""
        def custom_get(url, timeout=None):
            resp = MagicMock()
            if "earnings-calendar" in url:
                resp.status_code = 200
                resp.json.return_value = MOCK_CALENDAR_SPARSE
            elif "income-statement" in url:
                resp.status_code = 404
                resp.json.return_value = {"error": "not found"}
            elif "analyst-estimates" in url:
                resp.status_code = 404
                resp.json.return_value = {"error": "not found"}
            else:
                resp.status_code = 200
                resp.json.return_value = [{"symbol": "NVDA", "price": 130.0, "changesPercentage": 1.0}]
            return resp

        mock_get.side_effect = custom_get
        p = FmpProvider(api_key="test_key", debug=True)
        data = p.get_earnings("NVDA")
        captured = capsys.readouterr()

        assert data is not None
        assert data.actual_eps is None
        # Should have clean message, not raw HTTP 404 repeated
        assert "actual EPS fallback unavailable / unsupported" in captured.err


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
