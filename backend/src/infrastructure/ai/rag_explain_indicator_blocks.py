"""
Generic value formatters plus the indicator, model-metrics and candle blocks of the signal-explain RAG context.

IMPORTERS/CALLERS: rag_explain_signal_sections (section registry + header/triggers), rag_context.
AFFECTED API: none (prompt text only).
DATA SCHEMAS: none.

Split out of rag_explain_signal_sections.py (P1-8b) to respect module line limits.
"""

from __future__ import annotations

import json
from collections.abc import Callable
from typing import Any

from src.domain.enums import RSI_OVERBOUGHT_THRESHOLD, RSI_OVERSOLD_THRESHOLD

PRIMARY_INDICATOR_KEYS = frozenset({"rsi", "macd", "bb", "price"})
MIN_CANDLES_FOR_CHANGE = 2


def humanize_snake(label: str) -> str:
    return label.replace("_", " ").strip()


def format_loose_value(value: Any) -> str:
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, float):
        return f"{value:.6g}"
    if isinstance(value, int) and not isinstance(value, bool):
        return str(value)
    if isinstance(value, dict):
        return json.dumps(value, separators=(",", ":"), default=str)
    if isinstance(value, list):
        return json.dumps(value, separators=(",", ":"), default=str)
    return str(value)


def _rsi_line(rsi: Any) -> str:
    if not isinstance(rsi, (int, float)):
        return f"- RSI: {format_loose_value(rsi)}"
    rsi_f = float(rsi)
    if rsi_f < RSI_OVERSOLD_THRESHOLD:
        rsi_status = "oversold"
    elif rsi_f > RSI_OVERBOUGHT_THRESHOLD:
        rsi_status = "overbought"
    else:
        rsi_status = "neutral"
    return f"- RSI: {rsi_f:.1f} ({rsi_status})"


def _macd_line(macd: Any) -> str:
    if not isinstance(macd, dict):
        return f"- MACD: {format_loose_value(macd)}"
    value = macd.get("value", 0)
    signal_line = macd.get("signal", 0)
    histogram = macd.get("histogram", 0)
    trend = "bullish" if histogram > 0 else "bearish"
    return f"- MACD: {value:.4f} (signal: {signal_line:.4f}, {trend})"


def _bollinger_line(bb: Any) -> str:
    if not isinstance(bb, dict):
        return f"- Bollinger Bands: {format_loose_value(bb)}"
    upper = bb.get("upper", 0)
    middle = bb.get("middle", 0)
    lower = bb.get("lower", 0)
    bb_text = f"Upper ${upper:,.0f}, Middle ${middle:,.0f}, Lower ${lower:,.0f}"
    return f"- Bollinger Bands: {bb_text}"


def _snapshot_price_line(p: Any) -> str:
    if isinstance(p, (int, float)):
        return f"- Snapshot price from features: ${float(p):,.2f}"
    return f"- Snapshot price from features: {format_loose_value(p)}"


# Display order is the prompt order (rsi, macd, bb, price).
_PRIMARY_INDICATOR_LINES: tuple[tuple[str, Callable[[Any], str]], ...] = (
    ("rsi", _rsi_line),
    ("macd", _macd_line),
    ("bb", _bollinger_line),
    ("price", _snapshot_price_line),
)


def format_primary_indicators_block(indicators: dict[str, Any]) -> str:
    if not indicators:
        return ""
    lines = ["## Technical indicators (canonical TA)"]
    lines.extend(render(indicators[key]) for key, render in _PRIMARY_INDICATOR_LINES if key in indicators)
    return "\n".join(lines)


def format_indicators_split_block(indicators: dict[str, Any]) -> str:
    primary: dict[str, Any] = {}
    supplementary: dict[str, Any] = {}
    for key, val in indicators.items():
        k = str(key)
        if k in PRIMARY_INDICATOR_KEYS:
            primary[k] = val
        else:
            supplementary[k] = val

    chunks: list[str] = []
    ta_lines = format_primary_indicators_block(primary)
    if ta_lines:
        chunks.append(ta_lines)

    if supplementary:
        sup_lines = ["## Sentiment, on-chain proxies, and other numeric inputs"]
        sup_lines.extend(f"- {humanize_snake(k)} (`{k}`): {format_loose_value(supplementary[k])}" for k in sorted(supplementary.keys()))
        chunks.append("\n".join(sup_lines))

    return "\n\n".join(chunks)


def format_model_metrics_block(metrics: dict[str, Any] | None) -> str | None:
    if not metrics:
        return None
    lines = ["## Model Performance"]
    if "accuracy" in metrics:
        lines.append(f"- Accuracy: {metrics['accuracy']:.1%}")
    if "sharpe" in metrics:
        lines.append(f"- Sharpe Ratio: {metrics['sharpe']:.2f}")
    if "win_rate" in metrics:
        lines.append(f"- Win Rate: {metrics['win_rate']:.1%}")
    if "recent_signals" in metrics:
        recent = metrics["recent_signals"]
        lines.append(f"- Recent Signals: {len(recent)} in last 24h")
    return "\n".join(lines)


def format_recent_candles_block(candles: list[dict[str, Any]] | None) -> str | None:
    if not candles:
        return None
    lines = ["## Recent Price Action"]
    highs = [c.get("high", 0) for c in candles]
    lows = [c.get("low", 0) for c in candles]
    closes = [c.get("close", 0) for c in candles]
    if highs and lows:
        lines.append(f"- Period High: ${max(highs):,.2f}")
        lines.append(f"- Period Low: ${min(lows):,.2f}")
    if closes and len(closes) >= MIN_CANDLES_FOR_CHANGE:
        change = ((closes[-1] - closes[0]) / closes[0]) * 100
        direction = "up" if change > 0 else "down"
        lines.append(f"- Period Change: {abs(change):.2f}% {direction}")
    return "\n".join(lines)
