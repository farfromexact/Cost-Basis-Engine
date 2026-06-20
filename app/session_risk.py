from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime
from typing import Any, Iterable

from app.manual_fills import ManualFill
from core.models import Side
from research.risk_limits import RiskLimitPreset, risk_limit_preset


LIVE_SESSION_RISK_NOTE = (
    "live-session risk usage is computed from manual broker fills only; signals, "
    "chart markers, and tickets do not consume limits until a fill is recorded"
)


@dataclass(frozen=True)
class LiveSessionRiskUsageCheck:
    metric: str
    status: str
    used: float
    limit: float
    usage_ratio: float
    detail: str
    operator_action: str

    def as_dict(self) -> dict[str, Any]:
        return {
            "metric": self.metric,
            "status": self.status,
            "used": self.used,
            "limit": self.limit,
            "usage_ratio": self.usage_ratio,
            "detail": self.detail,
            "operator_action": self.operator_action,
        }


@dataclass(frozen=True)
class LiveSessionRiskUsageReport:
    status: str
    summary: str
    symbol: str
    session_date: str
    preset_id: str
    preset_label: str
    target_qty: int
    reference_price: float
    manual_fill_count: int
    gross_turnover_qty: int
    gross_turnover_notional: float
    net_position_delta_qty: int
    open_pair_count: int
    open_pair_qty: int
    open_pair_notional: float
    max_open_pair_age_minutes: float
    checks: tuple[LiveSessionRiskUsageCheck, ...]

    def as_dict(self) -> dict[str, Any]:
        return {
            "status": self.status,
            "summary": self.summary,
            "symbol": self.symbol,
            "session_date": self.session_date,
            "preset_id": self.preset_id,
            "preset_label": self.preset_label,
            "target_qty": self.target_qty,
            "reference_price": self.reference_price,
            "manual_fill_count": self.manual_fill_count,
            "gross_turnover_qty": self.gross_turnover_qty,
            "gross_turnover_notional": self.gross_turnover_notional,
            "net_position_delta_qty": self.net_position_delta_qty,
            "open_pair_count": self.open_pair_count,
            "open_pair_qty": self.open_pair_qty,
            "open_pair_notional": self.open_pair_notional,
            "max_open_pair_age_minutes": self.max_open_pair_age_minutes,
            "checks": [check.as_dict() for check in self.checks],
            "capability_note": LIVE_SESSION_RISK_NOTE,
        }


def build_live_session_risk_usage_report(
    symbol: str,
    fills: Iterable[ManualFill],
    target_qty: int,
    reference_price: float,
    preset_id: str | None = None,
    session_date: str | date | datetime | None = None,
    as_of: str | datetime | None = None,
) -> LiveSessionRiskUsageReport:
    preset = risk_limit_preset(preset_id)
    all_symbol_fills = [fill for fill in fills if fill.symbol == symbol]
    session_date_text = _session_date_text(session_date, all_symbol_fills)
    session_fills = [fill for fill in all_symbol_fills if _date_text(fill.ts) == session_date_text]

    gross_turnover_qty = sum(fill.qty for fill in session_fills)
    gross_turnover_notional = sum(fill.qty * fill.price for fill in session_fills)
    net_position_delta_qty = sum(_signed_qty(fill) for fill in session_fills)
    open_pairs = _open_pair_exposures(session_fills)
    open_pair_qty = sum(pair["open_qty"] for pair in open_pairs)
    open_pair_notional = sum(pair["open_notional"] for pair in open_pairs)
    max_age = _max_open_age_minutes(open_pairs, as_of)

    checks = (
        _turnover_check(gross_turnover_qty, gross_turnover_notional, target_qty, reference_price, preset),
        _capital_at_risk_check(open_pair_notional, target_qty, reference_price, preset),
        _open_pair_age_check(max_age, len(open_pairs), preset),
    )
    status = _aggregate_status(check.status for check in checks)
    return LiveSessionRiskUsageReport(
        status=status,
        summary=_summary(status, symbol, session_date_text, preset, gross_turnover_qty, open_pair_notional, len(open_pairs)),
        symbol=symbol,
        session_date=session_date_text,
        preset_id=preset.preset_id,
        preset_label=preset.label,
        target_qty=int(target_qty or 0),
        reference_price=round(float(reference_price or 0.0), 4),
        manual_fill_count=len(session_fills),
        gross_turnover_qty=int(gross_turnover_qty),
        gross_turnover_notional=round(gross_turnover_notional, 4),
        net_position_delta_qty=int(net_position_delta_qty),
        open_pair_count=len(open_pairs),
        open_pair_qty=int(open_pair_qty),
        open_pair_notional=round(open_pair_notional, 4),
        max_open_pair_age_minutes=round(max_age, 2),
        checks=checks,
    )


def _session_date_text(session_date: str | date | datetime | None, fills: list[ManualFill]) -> str:
    if session_date is not None:
        return _date_text(session_date)
    dated = [_date_text(fill.ts) for fill in fills if _date_text(fill.ts)]
    if dated:
        return max(dated)
    return date.today().isoformat()


def _date_text(value: str | date | datetime) -> str:
    if isinstance(value, datetime):
        return value.date().isoformat()
    if isinstance(value, date):
        return value.isoformat()
    text = str(value).strip()
    if not text:
        return ""
    try:
        return datetime.fromisoformat(text.replace("Z", "")).date().isoformat()
    except ValueError:
        return text[:10]


def _datetime_value(value: str | datetime | None) -> datetime | None:
    if value is None:
        return None
    if isinstance(value, datetime):
        return value
    text = str(value).strip()
    if not text:
        return None
    try:
        return datetime.fromisoformat(text.replace("Z", ""))
    except ValueError:
        return None


def _signed_qty(fill: ManualFill) -> int:
    return fill.qty if fill.side is Side.BUY else -fill.qty


def _open_pair_exposures(fills: list[ManualFill]) -> list[dict[str, Any]]:
    grouped: dict[str, dict[str, Any]] = {}
    for fill in fills:
        bucket = grouped.setdefault(
            fill.pair_id,
            {
                "pair_id": fill.pair_id,
                "buy_qty": 0,
                "sell_qty": 0,
                "buy_notional": 0.0,
                "sell_notional": 0.0,
                "first_ts": fill.ts,
            },
        )
        if _datetime_sort_key(fill.ts) < _datetime_sort_key(bucket["first_ts"]):
            bucket["first_ts"] = fill.ts
        if fill.side is Side.BUY:
            bucket["buy_qty"] += fill.qty
            bucket["buy_notional"] += fill.qty * fill.price
        else:
            bucket["sell_qty"] += fill.qty
            bucket["sell_notional"] += fill.qty * fill.price

    open_pairs: list[dict[str, Any]] = []
    for bucket in grouped.values():
        buy_qty = int(bucket["buy_qty"])
        sell_qty = int(bucket["sell_qty"])
        if buy_qty == sell_qty:
            continue
        if buy_qty > sell_qty:
            open_qty = buy_qty - sell_qty
            avg_price = bucket["buy_notional"] / buy_qty if buy_qty else 0.0
            open_side = "BUY"
        else:
            open_qty = sell_qty - buy_qty
            avg_price = bucket["sell_notional"] / sell_qty if sell_qty else 0.0
            open_side = "SELL"
        open_pairs.append(
            {
                "pair_id": bucket["pair_id"],
                "open_side": open_side,
                "open_qty": open_qty,
                "open_notional": open_qty * avg_price,
                "first_ts": bucket["first_ts"],
            }
        )
    return open_pairs


def _datetime_sort_key(value: str | datetime | None) -> datetime:
    parsed = _datetime_value(value)
    return parsed or datetime.min


def _max_open_age_minutes(open_pairs: list[dict[str, Any]], as_of: str | datetime | None) -> float:
    if not open_pairs:
        return 0.0
    as_of_dt = _datetime_value(as_of)
    if as_of_dt is None:
        latest = max((_datetime_value(pair["first_ts"]) for pair in open_pairs), default=None)
        as_of_dt = latest
    if as_of_dt is None:
        return 0.0
    ages = []
    for pair in open_pairs:
        opened_at = _datetime_value(pair["first_ts"])
        if opened_at is not None:
            ages.append(max(0.0, (as_of_dt - opened_at).total_seconds() / 60.0))
    return max(ages, default=0.0)


def _turnover_check(
    gross_turnover_qty: int,
    gross_turnover_notional: float,
    target_qty: int,
    reference_price: float,
    preset: RiskLimitPreset,
) -> LiveSessionRiskUsageCheck:
    if target_qty <= 0:
        return LiveSessionRiskUsageCheck(
            "daily_turnover_qty",
            "NO_DATA",
            float(gross_turnover_qty),
            0.0,
            0.0,
            "Target quantity is not recorded, so daily turnover usage cannot be scaled.",
            "Record target/held quantity before using risk usage for live limits.",
        )
    limit_qty = target_qty * preset.max_daily_turnover_ratio
    status = _usage_status(gross_turnover_qty, limit_qty)
    return LiveSessionRiskUsageCheck(
        "daily_turnover_qty",
        status,
        float(gross_turnover_qty),
        round(limit_qty, 4),
        _safe_ratio(gross_turnover_qty, limit_qty),
        f"Manual session turnover is {gross_turnover_qty} shares versus {limit_qty:.0f} allowed by {preset.label}.",
        _turnover_action(status),
    )


def _capital_at_risk_check(
    open_pair_notional: float,
    target_qty: int,
    reference_price: float,
    preset: RiskLimitPreset,
) -> LiveSessionRiskUsageCheck:
    if target_qty <= 0 or reference_price <= 0:
        return LiveSessionRiskUsageCheck(
            "same_day_capital_at_risk",
            "NO_DATA",
            round(open_pair_notional, 4),
            0.0,
            0.0,
            "Target quantity or reference price is missing, so open-pair capital at risk cannot be scaled.",
            "Record target quantity and a current reference price before interpreting open-pair risk.",
        )
    limit_notional = target_qty * reference_price * preset.max_same_day_capital_at_risk_ratio
    status = _usage_status(open_pair_notional, limit_notional)
    return LiveSessionRiskUsageCheck(
        "same_day_capital_at_risk",
        status,
        round(open_pair_notional, 4),
        round(limit_notional, 4),
        _safe_ratio(open_pair_notional, limit_notional),
        f"Unclosed manual pair exposure is {open_pair_notional:.2f} versus {limit_notional:.2f} allowed by {preset.label}.",
        _capital_action(status),
    )


def _open_pair_age_check(max_age_minutes: float, open_pair_count: int, preset: RiskLimitPreset) -> LiveSessionRiskUsageCheck:
    limit_minutes = float(preset.max_open_pair_minutes)
    if open_pair_count <= 0:
        return LiveSessionRiskUsageCheck(
            "max_open_pair_age_minutes",
            "OK",
            0.0,
            limit_minutes,
            0.0,
            "No manually open pair exposure remains for the session.",
            "No action required.",
        )
    status = _usage_status(max_age_minutes, limit_minutes, warn_ratio=0.75)
    return LiveSessionRiskUsageCheck(
        "max_open_pair_age_minutes",
        status,
        round(max_age_minutes, 2),
        limit_minutes,
        _safe_ratio(max_age_minutes, limit_minutes),
        f"Oldest unclosed manual pair age is {max_age_minutes:.1f} minutes versus {limit_minutes:.0f} allowed by {preset.label}.",
        _age_action(status),
    )


def _usage_status(used: float, limit: float, warn_ratio: float = 0.85) -> str:
    if limit <= 0:
        return "NO_DATA"
    if used > limit:
        return "BLOCKED"
    if used >= limit * warn_ratio and used > 0:
        return "WARN"
    return "OK"


def _safe_ratio(used: float, limit: float) -> float:
    return round(used / limit, 6) if limit > 0 else 0.0


def _aggregate_status(statuses) -> str:
    status_set = set(statuses)
    if "BLOCKED" in status_set:
        return "BLOCKED"
    if "WARN" in status_set or "NO_DATA" in status_set:
        return "WARN"
    return "OK"


def _summary(
    status: str,
    symbol: str,
    session_date: str,
    preset: RiskLimitPreset,
    gross_turnover_qty: int,
    open_pair_notional: float,
    open_pair_count: int,
) -> str:
    prefix = (
        f"Live session risk usage for {symbol} on {session_date} under {preset.label}: "
        f"manual turnover {gross_turnover_qty} shares, open pair exposure {open_pair_notional:.2f}, open pairs {open_pair_count}."
    )
    if status == "OK":
        return prefix + " Usage is within the selected preset limits."
    if status == "BLOCKED":
        return prefix + " At least one preset limit is exceeded; do not add risk until reconciled."
    return prefix + " Usage is near a limit or missing required scale inputs."


def _turnover_action(status: str) -> str:
    if status == "BLOCKED":
        return "Stop opening new pairs for this session unless a risk exception is approved."
    if status == "WARN":
        return "Avoid adding fresh turnover unless the next fill closes existing exposure."
    if status == "NO_DATA":
        return "Record target quantity before using this limit."
    return "No action required."


def _capital_action(status: str) -> str:
    if status == "BLOCKED":
        return "Prioritize closing or restoring existing open pairs before considering new exposure."
    if status == "WARN":
        return "Treat new first-leg orders as high risk until open exposure is reduced."
    if status == "NO_DATA":
        return "Record target quantity and reference price before using this limit."
    return "No action required."


def _age_action(status: str) -> str:
    if status == "BLOCKED":
        return "Escalate to close/restore workflow; open-pair wait time has exceeded the preset."
    if status == "WARN":
        return "Prepare close/restore action and avoid opening another pair."
    return "No action required."