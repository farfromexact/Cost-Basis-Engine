from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from app.position_reconciliation import BrokerPositionSnapshot
from core.fee_model import FeeBreakdown, FeeModel
from core.models import Side
from research.trigger_engine import ActionType, RulesConfig, TradeIntent


@dataclass(frozen=True)
class OrderTicketCheck:
    check: str
    status: str
    detail: str
    operator_action: str

    def as_dict(self) -> dict[str, str]:
        return {
            "check": self.check,
            "status": self.status,
            "detail": self.detail,
            "operator_action": self.operator_action,
        }


@dataclass(frozen=True)
class PreTradeOrderTicket:
    status: str
    summary: str
    symbol: str
    side: str
    qty: int
    limit_price: float
    gross_notional: float
    estimated_fees: float
    estimated_slippage: float
    cash_required: float
    checks: tuple[OrderTicketCheck, ...]

    def as_dict(self) -> dict[str, Any]:
        return {
            "status": self.status,
            "summary": self.summary,
            "symbol": self.symbol,
            "side": self.side,
            "qty": self.qty,
            "limit_price": self.limit_price,
            "gross_notional": self.gross_notional,
            "estimated_fees": self.estimated_fees,
            "estimated_slippage": self.estimated_slippage,
            "cash_required": self.cash_required,
            "checks": [check.as_dict() for check in self.checks],
            "capability_note": "pre-trade checklist only; no order is routed and no fill is inferred",
        }


def build_pre_trade_order_ticket(
    intent: TradeIntent,
    broker_snapshot: BrokerPositionSnapshot | None,
    fee_model: FeeModel,
    rules: RulesConfig,
) -> PreTradeOrderTicket:
    side = _order_side_from_intent(intent)
    if side is None:
        check = OrderTicketCheck(
            check="actionable_signal",
            status="NO_ACTION",
            detail=f"Intent action is {intent.action_type.value}; no first-leg order ticket is active.",
            operator_action="Do not place an order from this ticket.",
        )
        return PreTradeOrderTicket(
            status="NO_ACTION",
            summary="No actionable first-leg order ticket is active.",
            symbol=intent.symbol,
            side="NONE",
            qty=0,
            limit_price=0.0,
            gross_notional=0.0,
            estimated_fees=0.0,
            estimated_slippage=0.0,
            cash_required=0.0,
            checks=(check,),
        )

    qty = int(intent.suggested_qty or 0)
    price = float(intent.reference_price or 0.0)
    fee_breakdown = _safe_fee_breakdown(fee_model, side, price, qty)
    estimated_fees = fee_breakdown.total_fees if fee_breakdown else 0.0
    estimated_slippage = fee_breakdown.slippage if fee_breakdown else 0.0
    gross_notional = price * qty if price > 0 and qty > 0 else 0.0
    cash_required = gross_notional + estimated_fees + estimated_slippage if side is Side.BUY else 0.0

    checks = [
        _broker_snapshot_check(intent, broker_snapshot),
        _symbol_check(intent, broker_snapshot),
        _quantity_check(qty, rules),
        _price_check(price),
        _broker_capacity_check(side, qty, cash_required, broker_snapshot),
        _price_limit_check(intent, side, rules),
        _fee_slippage_check(estimated_fees, estimated_slippage),
    ]
    status = _worst_status(check.status for check in checks)
    summary = _summary_for_status(status, side, qty, price)
    return PreTradeOrderTicket(
        status=status,
        summary=summary,
        symbol=intent.symbol,
        side=side.value,
        qty=qty,
        limit_price=price,
        gross_notional=gross_notional,
        estimated_fees=estimated_fees,
        estimated_slippage=estimated_slippage,
        cash_required=cash_required,
        checks=tuple(checks),
    )


def _order_side_from_intent(intent: TradeIntent) -> Side | None:
    if intent.action_type is ActionType.TRIGGER_SELL_TO_BUY:
        return Side.SELL
    if intent.action_type is ActionType.TRIGGER_BUY_TO_SELL:
        return Side.BUY
    return None


def _safe_fee_breakdown(fee_model: FeeModel, side: Side, price: float, qty: int) -> FeeBreakdown | None:
    if price <= 0 or qty <= 0:
        return None
    return fee_model.calculate(side, price, qty)


def _broker_snapshot_check(intent: TradeIntent, broker_snapshot: BrokerPositionSnapshot | None) -> OrderTicketCheck:
    if broker_snapshot is None:
        return OrderTicketCheck(
            check="broker_snapshot",
            status="BLOCKED",
            detail="No broker/manual position snapshot is available for pre-trade validation.",
            operator_action="Record or import broker-confirmed holdings/cash before placing an order.",
        )
    return OrderTicketCheck(
        check="broker_snapshot",
        status="OK",
        detail=f"Broker snapshot available for {broker_snapshot.symbol} as of {broker_snapshot.as_of or 'unknown time'}.",
        operator_action="Continue only if this snapshot matches the broker screen now.",
    )


def _symbol_check(intent: TradeIntent, broker_snapshot: BrokerPositionSnapshot | None) -> OrderTicketCheck:
    if broker_snapshot is None:
        return OrderTicketCheck("symbol", "BLOCKED", "Cannot compare symbol without broker snapshot.", "Record broker snapshot first.")
    if intent.symbol == broker_snapshot.symbol:
        return OrderTicketCheck("symbol", "OK", f"Intent and broker snapshot both use {intent.symbol}.", "No action required.")
    return OrderTicketCheck(
        check="symbol",
        status="BLOCKED",
        detail=f"Intent symbol {intent.symbol} differs from broker snapshot {broker_snapshot.symbol}.",
        operator_action="Switch to the broker-confirmed symbol before placing an order.",
    )


def _quantity_check(qty: int, rules: RulesConfig) -> OrderTicketCheck:
    if qty <= 0:
        return OrderTicketCheck("quantity", "BLOCKED", "Suggested quantity is zero or negative.", "Do not place an order.")
    if qty < rules.minimum_order_qty:
        return OrderTicketCheck(
            "quantity",
            "BLOCKED",
            f"Suggested quantity {qty} is below minimum order quantity {rules.minimum_order_qty}.",
            "Round or skip the order.",
        )
    if rules.lot_size > 1 and qty % rules.lot_size != 0:
        return OrderTicketCheck(
            "quantity",
            "BLOCKED",
            f"Suggested quantity {qty} is not aligned to lot size {rules.lot_size}.",
            "Round to a valid lot before entering the ticket.",
        )
    return OrderTicketCheck("quantity", "OK", f"Suggested quantity {qty} passes lot/minimum checks.", "No action required.")


def _price_check(price: float) -> OrderTicketCheck:
    if price <= 0:
        return OrderTicketCheck("price", "BLOCKED", "Suggested limit/reference price is not positive.", "Do not place an order.")
    return OrderTicketCheck("price", "OK", f"Suggested reference price is {price:.4f}.", "Confirm executable bid/ask in broker.")


def _broker_capacity_check(
    side: Side,
    qty: int,
    cash_required: float,
    broker_snapshot: BrokerPositionSnapshot | None,
) -> OrderTicketCheck:
    if broker_snapshot is None:
        return OrderTicketCheck("broker_capacity", "BLOCKED", "Cannot verify sellable/cash capacity without broker snapshot.", "Record broker snapshot first.")
    if side is Side.SELL:
        if qty <= broker_snapshot.sellable_qty:
            return OrderTicketCheck(
                "broker_sellable_qty",
                "OK",
                f"Order quantity {qty} is within broker sellable quantity {broker_snapshot.sellable_qty}.",
                "Confirm no pending orders have reduced sellable quantity.",
            )
        return OrderTicketCheck(
            "broker_sellable_qty",
            "BLOCKED",
            f"Order quantity {qty} exceeds broker sellable quantity {broker_snapshot.sellable_qty}.",
            "Reduce quantity or reconcile holdings before sell-first action.",
        )
    if qty > broker_snapshot.purchasable_qty:
        return OrderTicketCheck(
            "broker_purchasable_qty",
            "BLOCKED",
            f"Order quantity {qty} exceeds broker purchasable quantity {broker_snapshot.purchasable_qty}.",
            "Reduce quantity or update broker snapshot before buy-first action.",
        )
    if broker_snapshot.cash_available <= 0:
        return OrderTicketCheck(
            "broker_cash",
            "BLOCKED",
            "Broker cash available is not recorded for this buy-first ticket.",
            "Record broker-confirmed cash before placing a buy order.",
        )
    if cash_required > broker_snapshot.cash_available:
        return OrderTicketCheck(
            "broker_cash",
            "BLOCKED",
            f"Cash required {cash_required:.2f} exceeds broker cash {broker_snapshot.cash_available:.2f}.",
            "Reduce quantity or add cash before buy-first action.",
        )
    return OrderTicketCheck(
        "broker_cash",
        "OK",
        f"Cash required {cash_required:.2f} is within broker cash {broker_snapshot.cash_available:.2f}.",
        "Confirm available cash has not changed due to pending orders.",
    )


def _price_limit_check(intent: TradeIntent, side: Side, rules: RulesConfig) -> OrderTicketCheck:
    feature = intent.feature_snapshot
    if feature is None:
        return OrderTicketCheck(
            "price_limit_risk",
            "WARN",
            f"No feature snapshot is available to evaluate limit proximity; configured price-limit pct is {rules.price_limit_pct:.2%}.",
            "Check broker price-limit band manually before order entry.",
        )
    if side is Side.BUY and feature.near_upper_limit:
        return OrderTicketCheck(
            "price_limit_risk",
            "WARN",
            "Buy-first ticket is near the configured upper-limit risk zone.",
            "Confirm remaining offer liquidity and limit-up risk in broker before entering the order.",
        )
    if side is Side.SELL and feature.near_lower_limit:
        return OrderTicketCheck(
            "price_limit_risk",
            "WARN",
            "Sell-first ticket is near the configured lower-limit risk zone.",
            "Confirm bid liquidity and limit-down risk in broker before entering the order.",
        )
    return OrderTicketCheck(
        "price_limit_risk",
        "OK",
        f"Signal is not flagged near the configured {rules.price_limit_pct:.2%} price-limit risk zone.",
        "Still confirm broker limit band before order entry.",
    )


def _fee_slippage_check(estimated_fees: float, estimated_slippage: float) -> OrderTicketCheck:
    total_cost = estimated_fees + estimated_slippage
    if total_cost <= 0:
        return OrderTicketCheck(
            "fee_slippage",
            "BLOCKED",
            "Expected fee plus slippage is zero; live ticket is probably using a research-only zero-fee profile.",
            "Select a broker-confirmed costed fee profile before action.",
        )
    return OrderTicketCheck(
        "fee_slippage",
        "OK",
        f"Estimated fees {estimated_fees:.2f}; estimated slippage {estimated_slippage:.2f}; total cost {total_cost:.2f}.",
        "Compare this estimate with broker preview before submitting.",
    )


def _worst_status(statuses) -> str:
    values = set(statuses)
    if "BLOCKED" in values:
        return "BLOCKED"
    if "WARN" in values:
        return "WARN"
    if "OK" in values:
        return "OK"
    return "NO_ACTION"


def _summary_for_status(status: str, side: Side, qty: int, price: float) -> str:
    base = f"Pre-trade ticket for {side.value} {qty} at reference/limit price {price:.4f}."
    if status == "OK":
        return base + " All mechanical checks passed; still confirm broker preview before submission."
    if status == "WARN":
        return base + " Warnings require manual broker confirmation before submission."
    return base + " Blocked until failed checks are reconciled."
