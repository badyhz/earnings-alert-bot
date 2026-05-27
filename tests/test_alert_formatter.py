import pytest
from alert_formatter import (
    Thresholds,
    classify_earnings,
    format_earnings_alert,
    build_interpretation,
    build_trading_advice,
)
from providers.base import EarningsData


def make_data(**kwargs):
    defaults = {
        "ticker": "TEST",
        "company_name": "Test Corp",
        "earnings_date": "2026-05-27",
        "earnings_timing": "after_market",
        "actual_eps": 1.0,
        "consensus_eps": 0.9,
        "actual_revenue": 10.0,
        "consensus_revenue": 9.5,
        "revenue_unit": "B",
        "guidance_revenue_next_q": None,
        "consensus_revenue_next_q": None,
        "current_price": 100.0,
        "price_move_pct": 5.0,
        "session": "after_hours",
        "source": "mock",
    }
    defaults.update(kwargs)
    return EarningsData(**defaults)


class TestClassification:
    def test_strong_beat(self):
        assert classify_earnings(6.0, 4.0, 8.0, Thresholds()) == "STRONG_BEAT"

    def test_mild_beat(self):
        assert classify_earnings(2.0, 2.0, 3.0, Thresholds()) == "MILD_BEAT"

    def test_mixed(self):
        assert classify_earnings(5.0, -2.0, 3.0, Thresholds()) == "MIXED"

    def test_miss(self):
        assert classify_earnings(-3.0, -2.0, -5.0, Thresholds()) == "MISS"

    def test_price_overreaction(self):
        assert classify_earnings(2.0, 2.0, 12.0, Thresholds()) == "PRICE_OVERREACTION"

    def test_price_resilience(self):
        assert classify_earnings(-5.0, -3.0, 2.0, Thresholds()) == "PRICE_RESILIENCE"

    def test_no_data(self):
        assert classify_earnings(None, None, None, Thresholds()) == "NO_DATA"


class TestInterpretation:
    def test_strong_beat_text(self):
        text = build_interpretation("STRONG_BEAT", 6.0, 4.0, 8.0, None, None)
        assert "大幅超预期" in text

    def test_mild_beat_text(self):
        text = build_interpretation("MILD_BEAT", 2.0, 2.0, 3.0, None, None)
        assert "小幅超预期" in text

    def test_guidance_strong(self):
        text = build_interpretation("MILD_BEAT", 2.0, 2.0, 3.0, 10.0, 9.0)
        assert "指引偏强" in text

    def test_guidance_weak(self):
        text = build_interpretation("MILD_BEAT", 2.0, 2.0, 3.0, 8.0, 9.0)
        assert "指引偏弱" in text


class TestTradingAdvice:
    def test_beat_with_high_move(self):
        text = build_trading_advice("STRONG_BEAT", 12.0)
        assert "利好兑现" in text

    def test_miss_advice(self):
        text = build_trading_advice("MISS", -5.0)
        assert "观望" in text

    def test_overreaction_advice(self):
        text = build_trading_advice("PRICE_OVERREACTION", 15.0)
        assert "追高风险" in text


class TestFullFormat:
    def test_full_data(self):
        data = make_data()
        result = format_earnings_alert(data)
        assert "TEST" in result
        assert "EPS" in result
        assert "收入" in result
        assert "交易解释" in result
        assert "风险" in result

    def test_missing_revenue(self):
        data = make_data(actual_revenue=None, consensus_revenue=None)
        result = format_earnings_alert(data)
        assert "数据缺失" in result
        assert "TEST" in result  # Should still work

    def test_missing_guidance(self):
        data = make_data(guidance_revenue_next_q=None, consensus_revenue_next_q=None)
        result = format_earnings_alert(data)
        assert "下季收入指引" not in result

    def test_missing_price(self):
        data = make_data(current_price=None, price_move_pct=None)
        result = format_earnings_alert(data)
        assert "TEST" in result
        assert "涨跌" not in result

    def test_chinese_output(self):
        data = make_data()
        result = format_earnings_alert(data)
        assert "🚨" in result
        assert "盘后" in result
        assert "预期" in result
