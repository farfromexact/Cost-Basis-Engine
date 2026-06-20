from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from core.models import Side
from research.trigger_engine import ActionType, TradeIntent


@dataclass(frozen=True)
class SlippageStressBand:
    label: str
    slippage_multiplier: float
    extra_adverse_bps: float


@dataclass(frozen=True)
class ExecutionSensitivityBand:
    label: str
    slippage_multiplier: float
    extra_adverse_bps: float
    gross_edge: float
    estimated_fee: float
    stressed_slippage: float
    residual_buffer: float
    stressed_net_edge: float
    edge_survival_ratio: float
    status: str

    def as_dict(self) -> dict[str, Any]:
        return {
            "label": self.label,
            "slippage_multiplier": self.slippage_multiplier,
            "extra_adverse_bps": self.extra_adverse_bps,
            "gross_edge": self.gross_edge,
            "estimated_fee": self.estimated_fee,
            "stressed_slippage": self.stressed_slippage,
            "residual_buffer": self.residual_buffer,
            "stressed_net_edge": self.stressed_net_edge,
            "edge_survival_ratio": self.edge_survival_ratio,
            "status": self.status,
        }


@dataclass(frozen=True)
class ExecutionSensitivityReport:
    status: str
    summary: str
    symbol: str
    side: str
    qty: int
    reference_price: float
    baseline_net_edge: float
    worst_net_edge: float
    bands: tuple[ExecutionSensitivityBand, ...]

    def as_dict(self) -> dict[str, Any]:
        return {
            "status": self.status,
            "summary": self.summary,
            "symbol": self.symbol,
            "side": self.side,
            "qty": self.qty,
            "reference_price": self.reference_price,
            "baseline_net_edge": self.baseline_net_edge,
            "worst_net_edge": self.worst_net_edge,
            "bands": [band.as_dict() for band in self.bands],
            "capability_note": "execution-quality sensitivity only; no order is routed and no fill is inferred",
        }


DEFAULT_SLIPPAGE_STRESS_BANDS = (
    SlippageStressBand("base", 1.0, 0.0),
    SlippageStressBand("worse_fill", 1.5, 5.0),
    SlippageStressBand("bad_fill", 2.0, 10.0),
    SlippageStressBand("tail_fill", 3.0, 20.0),
)


def build_execution_sensitivity_report(
    intent: TradeIntent,
    bands: tuple[SlippageStressBand, ...] = DEFAULT_SLIPPAGE_STRESS_BANDS,
) -> ExecutionSensitivityReport:
    side = _side_from_intent(intent)
    qty = int(intent.suggested_qty or 0)
    price = float(intent.reference_price or 0.0)
    if side is None or qty <= 0 or price <= 0:
        return ExecutionSensitivityReport(
            status="NO_ACTION",
            summary="No actionable first-leg intent is available for execution sensitivity.",
            symbol=intent.symbol,
            side="NONE",
            qty=0,
            reference_price=0.0,
            baseline_net_edge=0.0,
            worst_net_edge=0.0,
            bands=(),
        )

    gross_edge = float(intent.estimated_gross_edge or 0.0)
    estimated_fee = max(0.0, float(intent.estimated_fee or 0.0))
    base_slippage = max(0.0, float(intent.estimated_slippage or 0.0))
    baseline_net = float(intent.estimated_net_edge or 0.0)
    residual_buffer = max(0.0, gross_edge - estimated_fee - base_slippage - baseline_net)
    notional = qty * price
    rows = tuple(
        _build_band(
            stress=stress,
            gross_edge=gross_edge,
            estimated_fee=estimated_fee,
            base_slippage=base_slippage,
            residual_buffer=residual_buffer,
            notional=notional,
        )
        for stress in bands
    )
    status = _report_status(rows)
    worst_net = min((row.stressed_net_edge for row in rows), default=0.0)
    return ExecutionSensitivityReport(
        status=status,
        summary=_summary(status, side, qty, price, worst_net),
        symbol=intent.symbol,
        side=side.value,
        qty=qty,
        reference_price=price,
        baseline_net_edge=baseline_net,
        worst_net_edge=worst_net,
        bands=rows,
    )


def _build_band(
    stress: SlippageStressBand,
    gross_edge: float,
    estimated_fee: float,
    base_slippage: float,
    residual_buffer: float,
    notional: float,
) -> ExecutionSensitivityBand:
    extra_adverse_cost = notional * stress.extra_adverse_bps / 10000.0
    stressed_slippage = base_slippage * stress.slippage_multiplier + extra_adverse_cost
    net_edge = gross_edge - estimated_fee - stressed_slippage - residual_buffer
    survival = net_edge / gross_edge if gross_edge > 0 else 0.0
    status = "OK" if net_edge > 0 else "BLOCKED"
    if 0 < survival < 0.25:
        status = "WARN"
    return ExecutionSensitivityBand(
        label=stress.label,
        slippage_multiplier=stress.slippage_multiplier,
        extra_adverse_bps=stress.extra_adverse_bps,
        gross_edge=round(gross_edge, 4),
        estimated_fee=round(estimated_fee, 4),
        stressed_slippage=round(stressed_slippage, 4),
        residual_buffer=round(residual_buffer, 4),
        stressed_net_edge=round(net_edge, 4),
        edge_survival_ratio=round(survival, 6),
        status=status,
    )


def _side_from_intent(intent: TradeIntent) -> Side | None:
    if intent.action_type is ActionType.TRIGGER_SELL_TO_BUY:
        return Side.SELL
    if intent.action_type is ActionType.TRIGGER_BUY_TO_SELL:
        return Side.BUY
    return None


def _report_status(rows: tuple[ExecutionSensitivityBand, ...]) -> str:
    if not rows:
        return "NO_ACTION"
    statuses = {row.status for row in rows}
    if "BLOCKED" in statuses:
        return "BLOCKED"
    if "WARN" in statuses:
        return "WARN"
    return "OK"


def _summary(status: str, side: Side, qty: int, price: float, worst_net: float) -> str:
    prefix = f"Execution sensitivity for {side.value} {qty} at {price:.4f}: worst stressed net edge {worst_net:.2f}."
    if status == "OK":
        return prefix + " Edge remains positive across configured slippage bands."
    if status == "WARN":
        return prefix + " Edge is thin under worse fills; require broker preview and stricter limit discipline."
    return prefix + " Edge is exhausted under at least one worse-fill band; do not treat the signal as robust."
