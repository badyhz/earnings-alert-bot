from dataclasses import dataclass
from typing import Optional

from providers.base import EarningsData

TIMING_MAP = {
    "before_market": "盘前",
    "after_market": "盘后",
    "during_market": "盘中",
    "unknown": "未知",
}

SESSION_MAP = {
    "regular": "盘中",
    "pre_market": "盘前",
    "after_hours": "盘后",
}


@dataclass
class Thresholds:
    eps_surprise_strong_pct: float = 5.0
    revenue_surprise_strong_pct: float = 3.0
    price_move_alert_pct: float = 5.0
    price_move_strong_pct: float = 10.0


def calc_surprise_pct(actual: Optional[float], consensus: Optional[float]) -> Optional[float]:
    if actual is None or consensus is None or consensus == 0:
        return None
    return round((actual - consensus) / abs(consensus) * 100, 2)


def classify_earnings(
    eps_surprise: Optional[float],
    revenue_surprise: Optional[float],
    price_move_pct: Optional[float],
    thresholds: Thresholds,
) -> str:
    has_eps = eps_surprise is not None
    has_rev = revenue_surprise is not None
    has_price = price_move_pct is not None

    if not has_eps and not has_rev:
        return "NO_DATA"

    eps_beat = has_eps and eps_surprise > 0
    rev_beat = has_rev and revenue_surprise > 0
    eps_miss = has_eps and eps_surprise < 0
    rev_miss = has_rev and revenue_surprise < 0

    eps_strong = has_eps and eps_surprise >= thresholds.eps_surprise_strong_pct
    rev_strong = has_rev and revenue_surprise >= thresholds.revenue_surprise_strong_pct
    price_strong = has_price and abs(price_move_pct) >= thresholds.price_move_strong_pct
    price_alert = has_price and abs(price_move_pct) >= thresholds.price_move_alert_pct

    # STRONG_BEAT
    if eps_strong and rev_strong:
        return "STRONG_BEAT"

    # MISS
    if eps_miss and rev_miss:
        if has_price and price_move_pct >= 0:
            return "PRICE_RESILIENCE"
        return "MISS"

    # MIXED
    if (eps_beat and rev_miss) or (eps_miss and rev_beat):
        return "MIXED"

    # MILD_BEAT
    if eps_beat and rev_beat:
        if price_strong:
            return "PRICE_OVERREACTION"
        return "MILD_BEAT"

    # One beat, other neutral
    if eps_beat or rev_beat:
        return "MILD_BEAT"

    return "MILD_BEAT"


def format_surprise_line(label: str, actual: Optional[float], consensus: Optional[float], unit: str = "") -> str:
    if actual is None or consensus is None:
        return f"{label}：数据缺失"
    surprise = calc_surprise_pct(actual, consensus)
    sign = "+" if surprise >= 0 else ""
    unit_str = unit if unit else ""
    return f"{label}：{actual}{unit_str} vs 预期 {consensus}{unit_str}，差异 {sign}{surprise}%"


def build_interpretation(classification: str, eps_surprise: Optional[float], revenue_surprise: Optional[float],
                         price_move_pct: Optional[float], guidance_rev: Optional[float],
                         consensus_rev_next: Optional[float]) -> str:
    parts = []

    if classification == "STRONG_BEAT":
        parts.append("大幅超预期，业绩表现强劲。")
    elif classification == "MILD_BEAT":
        parts.append("小幅超预期。")
    elif classification == "MIXED":
        parts.append("EPS和收入表现分化，需关注具体业务线。")
    elif classification == "MISS":
        parts.append("低于预期，业绩承压。")
    elif classification == "PRICE_OVERREACTION":
        parts.append("小幅超预期，但股价涨幅已经较大。")
    elif classification == "PRICE_RESILIENCE":
        parts.append("业绩不及预期，但股价表现相对抗跌。")
    else:
        parts.append("数据不足，无法判断。")

    if guidance_rev is not None and consensus_rev_next is not None:
        guidance_surprise = calc_surprise_pct(guidance_rev, consensus_rev_next)
        if guidance_surprise is not None:
            if guidance_surprise > 3:
                parts.append("指引偏强。")
            elif guidance_surprise < -3:
                parts.append("指引偏弱。")
            else:
                parts.append("指引符合预期。")

    return "".join(parts)


def build_trading_advice(classification: str, price_move_pct: Optional[float]) -> str:
    if classification in ("STRONG_BEAT", "MILD_BEAT"):
        if price_move_pct is not None and price_move_pct > 8:
            return ("如果盘后涨幅明显大于财报超预期幅度，次日容易出现利好兑现；"
                    "不适合盲目追高，优先观察开盘后是否能站稳关键价位。")
        return "关注开盘后走势，可等待回踩支撑位再考虑介入。"
    elif classification == "MISS":
        return "业绩不及预期，建议观望，等待企稳信号。"
    elif classification == "MIXED":
        return "业绩分化，建议关注管理层电话会议中对各业务线的展望。"
    elif classification == "PRICE_OVERREACTION":
        return ("股价涨幅可能已透支短期利好，追高风险较大；"
                "建议等待回调后再评估。")
    elif classification == "PRICE_RESILIENCE":
        return "虽然业绩不及预期，但市场反应温和，可能存在其他利好因素支撑。"
    return "数据不足，无法给出交易建议。"


def format_earnings_alert(data: EarningsData, thresholds: Optional[Thresholds] = None) -> str:
    if thresholds is None:
        thresholds = Thresholds()

    eps_surprise = calc_surprise_pct(data.actual_eps, data.consensus_eps)
    revenue_surprise = calc_surprise_pct(data.actual_revenue, data.consensus_revenue)

    classification = classify_earnings(eps_surprise, revenue_surprise, data.price_move_pct, thresholds)

    timing = TIMING_MAP.get(data.earnings_timing, data.earnings_timing)
    session = SESSION_MAP.get(data.session, data.session)

    lines = [f"🚨 {data.ticker} 财报对比结果", ""]
    lines.append(f"时间：{timing} / {data.earnings_date}")
    lines.append(f"公司：{data.company_name}")

    if data.current_price is not None:
        lines.append(f"当前价：{data.current_price:.2f}")

    if data.price_move_pct is not None:
        sign = "+" if data.price_move_pct >= 0 else ""
        lines.append(f"{session}涨跌：{sign}{data.price_move_pct}%")

    lines.append("")
    lines.append(format_surprise_line("EPS", data.actual_eps, data.consensus_eps))
    lines.append(format_surprise_line("收入", data.actual_revenue, data.consensus_revenue, data.revenue_unit))

    if data.guidance_revenue_next_q is not None and data.consensus_revenue_next_q is not None:
        guidance_surprise = calc_surprise_pct(data.guidance_revenue_next_q, data.consensus_revenue_next_q)
        sign = "+" if guidance_surprise >= 0 else ""
        lines.append(
            f"下季收入指引：{data.guidance_revenue_next_q}{data.revenue_unit}"
            f" vs 预期 {data.consensus_revenue_next_q}{data.revenue_unit}，差异 {sign}{guidance_surprise}%"
        )

    lines.append("")
    interpretation = build_interpretation(classification, eps_surprise, revenue_surprise,
                                          data.price_move_pct, data.guidance_revenue_next_q,
                                          data.consensus_revenue_next_q)
    lines.append(f"判断：")
    lines.append(interpretation)

    lines.append("")
    lines.append("交易解释：")
    lines.append(build_trading_advice(classification, data.price_move_pct))

    lines.append("")
    lines.append("风险：")
    lines.append("这只是财报事件监控，不构成买卖建议。")

    return "\n".join(lines)
