from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Iterable

from app.execution_sensitivity import ExecutionSensitivityReport
from app.manual_fills import ManualFill, manual_pair_id
from app.order_ticket import PreTradeOrderTicket
from core.models import Side


POST_TRADE_REVIEW_NOTE = (
    "post-trade review uses manual broker fills only; it does not route orders, "
    "infer fills, or count cost-basis reduction until both legs are closed, target "
    "inventory is restored, and all fees/slippage are deducted"
)


@dataclass(frozen=True)
class PostTradeReviewCheck:
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
class PostTradeReviewReport:
    status: str
    summary: str
    symbol: str
    pair_id: str
    expected_side: str
    expected_qty: int
    ticket_limit_price: float
    fill_qty: int
    fill_avg_price: float
    fill_fees: float
    fill_slippage: float
    realized_notional: float
    price_diff_vs_ticket: float
    ticket_estimated_fees: float
    ticket_estimated_slippage: float
    sensitivity_status: str
    worst_sensitivity_net_edge: float
    checks: tuple[PostTradeReviewCheck, ...]

    def as_dict(self) -> dict[str, Any]:
        return {
            "status": self.status,
            "summary": self.summary,
            "symbol": self.symbol,
            "pair_id": self.pair_id,
            "expected_side": self.expected_side,
            "expected_qty": self.expected_qty,
            "ticket_limit_price": self.ticket_limit_price,
            "fill_qty": self.fill_qty,
            "fill_avg_price": self.fill_avg_price,
            "fill_fees": self.fill_fees,
            "fill_slippage": self.fill_slippage,
            "realized_notional": self.realized_notional,
            "price_diff_vs_ticket": self.price_diff_vs_ticket,
            "ticket_estimated_fees": self.ticket_estimated_fees,
            "ticket_estimated_slippage": self.ticket_estimated_slippage,
            "sensitivity_status": self.sensitivity_status,
            "worst_sensitivity_net_edge": self.worst_sensitivity_net_edge,
            "checks": [check.as_dict() for check in self.checks],
            "capability_note": POST_TRADE_REVIEW_NOTE,
        }


def review_pair_id_from_ticket(ticket: PreTradeOrderTicket) -> str:
    side = _ticket_side(ticket.side)
    if side is Side.SELL:
        return manual_pair_id(ticket.symbol, "SB", ticket.limit_price, ticket.qty)
    if side is Side.BUY:
        return manual_pair_id(ticket.symbol, "BS", ticket.limit_price, ticket.qty)
    return ""


def build_post_trade_review_report(
    ticket: PreTradeOrderTicket,
    sensitivity: ExecutionSensitivityReport,
    fills: Iterable[ManualFill],
    pair_id: str | None = None,
) -> PostTradeReviewReport:
    expected_side = _ticket_side(ticket.side)
    review_pair_id = pair_id or review_pair_id_from_ticket(ticket)
    if expected_side is None or ticket.qty <= 0:
        check = PostTradeReviewCheck(
            check="actionable_ticket",
            status="NO_ACTION",
            detail="No actionable pre-trade ticket is active, so there is no fill to review.",
            operator_action="Do not record a post-trade review for a no-action ticket.",
        )
        return _empty_report(ticket, sensitivity, review_pair_id, "NO_ACTION", check)

    fills_list = list(fills)
    same_pair_fills = [
        fill
        for fill in fills_list
        if fill.symbol == ticket.symbol and fill.pair_id == review_pair_id
    ]
    matching_fills = [fill for fill in same_pair_fills if fill.side == expected_side]
    if not matching_fills:
        other_sides = sorted({fill.side.value for fill in same_pair_fills})
        suffix = f" Other recorded sides for this pair: {', '.join(other_sides)}." if other_sides else ""
        check = PostTradeReviewCheck(
            check="manual_fill_match",
            status="NO_FILL",
            detail=f"No manual {expected_side.value} fill is recorded for pair {review_pair_id}.{suffix}",
            operator_action="Record the broker-confirmed fill with this pair id before judging execution quality.",
        )
        return _empty_report(ticket, sensitivity, review_pair_id, "NO_FILL", check)

    fill_qty = sum(fill.qty for fill in matching_fills)
    realized_notional = sum(fill.qty * fill.price for fill in matching_fills)
    fill_avg_price = realized_notional / fill_qty if fill_qty > 0 else 0.0
    fill_fees = sum(fill.fees for fill in matching_fills)
    fill_slippage = sum(fill.slippage for fill in matching_fills)
    price_diff = fill_avg_price - ticket.limit_price if fill_qty > 0 else 0.0
    adverse_price_cost = _adverse_price_cost(expected_side, ticket.limit_price, fill_avg_price, fill_qty)

    checks = (
        _ticket_status_check(ticket),
        _quantity_check(fill_qty, ticket.qty),
        _price_check(expected_side, ticket.limit_price, fill_avg_price, adverse_price_cost),
        _cost_check(ticket, fill_fees, fill_slippage),
        _sensitivity_check(sensitivity, adverse_price_cost, fill_fees + fill_slippage, ticket.estimated_fees + ticket.estimated_slippage),
    )
    status = _aggregate_status(check.status for check in checks)
    return PostTradeReviewReport(
        status=status,
        summary=_summary(status, expected_side, ticket.qty, fill_qty, fill_avg_price, review_pair_id),
        symbol=ticket.symbol,
        pair_id=review_pair_id,
        expected_side=expected_side.value,
        expected_qty=ticket.qty,
        ticket_limit_price=round(ticket.limit_price, 4),
        fill_qty=fill_qty,
        fill_avg_price=round(fill_avg_price, 4),
        fill_fees=round(fill_fees, 4),
        fill_slippage=round(fill_slippage, 4),
        realized_notional=round(realized_notional, 4),
        price_diff_vs_ticket=round(price_diff, 4),
        ticket_estimated_fees=round(ticket.estimated_fees, 4),
        ticket_estimated_slippage=round(ticket.estimated_slippage, 4),
        sensitivity_status=sensitivity.status,
        worst_sensitivity_net_edge=round(sensitivity.worst_net_edge, 4),
        checks=checks,
    )


def _empty_report(
    ticket: PreTradeOrderTicket,
    sensitivity: ExecutionSensitivityReport,
    pair_id: str,
    status: str,
    check: PostTradeReviewCheck,
) -> PostTradeReviewReport:
    return PostTradeReviewReport(
        status=status,
        summary=_empty_summary(status, ticket, pair_id),
        symbol=ticket.symbol,
        pair_id=pair_id,
        expected_side=ticket.side,
        expected_qty=ticket.qty,
        ticket_limit_price=round(ticket.limit_price, 4),
        fill_qty=0,
        fill_avg_price=0.0,
        fill_fees=0.0,
        fill_slippage=0.0,
        realized_notional=0.0,
        price_diff_vs_ticket=0.0,
        ticket_estimated_fees=round(ticket.estimated_fees, 4),
        ticket_estimated_slippage=round(ticket.estimated_slippage, 4),
        sensitivity_status=sensitivity.status,
        worst_sensitivity_net_edge=round(sensitivity.worst_net_edge, 4),
        checks=(check,),
    )


def _ticket_side(side: str) -> Side | None:
    try:
        return Side(str(side).upper())
    except ValueError:
        return None


def _ticket_status_check(ticket: PreTradeOrderTicket) -> PostTradeReviewCheck:
    if ticket.status == "BLOCKED":
        return PostTradeReviewCheck(
            "pre_trade_ticket_status",
            "BLOCKED",
            f"The pre-trade ticket was BLOCKED: {ticket.summary}",
            "Treat the fill as an exception; reconcile why a blocked ticket was executed.",
        )
    if ticket.status == "WARN":
        return PostTradeReviewCheck(
            "pre_trade_ticket_status",
            "WARN",
            f"The pre-trade ticket carried warnings: {ticket.summary}",
            "Document the broker preview and why the warning was accepted.",
        )
    return PostTradeReviewCheck(
        "pre_trade_ticket_status",
        "OK",
        f"The pre-trade ticket status was {ticket.status}.",
        "No action required.",
    )


def _quantity_check(fill_qty: int, expected_qty: int) -> PostTradeReviewCheck:
    if fill_qty > expected_qty:
        return PostTradeReviewCheck(
            "quantity",
            "BLOCKED",
            f"Manual fill quantity {fill_qty} exceeds ticket quantity {expected_qty}.",
            "Reconcile the broker order/fill list before using the result in risk or cost-basis accounting.",
        )
    if fill_qty < expected_qty:
        return PostTradeReviewCheck(
            "quantity",
            "WARN",
            f"Manual fill quantity {fill_qty} is below ticket quantity {expected_qty}.",
            "Treat the order as partially filled; update open quantity and do not assume full target restoration.",
        )
    return PostTradeReviewCheck("quantity", "OK", f"Manual fill quantity matches ticket quantity {expected_qty}.", "No action required.")


def _price_check(side: Side, limit_price: float, fill_avg_price: float, adverse_price_cost: float) -> PostTradeReviewCheck:
    if limit_price <= 0 or fill_avg_price <= 0:
        return PostTradeReviewCheck("price", "BLOCKED", "Ticket or fill price is not positive.", "Do not use this review until prices are corrected.")
    if adverse_price_cost > 0:
        direction = "above" if side is Side.BUY else "below"
        return PostTradeReviewCheck(
            "price_vs_ticket",
            "WARN",
            f"Average {side.value} fill {fill_avg_price:.4f} is adverse versus ticket limit {limit_price:.4f}; adverse cost {adverse_price_cost:.2f}.",
            f"Review why execution occurred {direction} the ticket reference and tighten future limit discipline.",
        )
    return PostTradeReviewCheck(
        "price_vs_ticket",
        "OK",
        f"Average {side.value} fill {fill_avg_price:.4f} is not adverse versus ticket limit {limit_price:.4f}.",
        "No action required.",
    )


def _cost_check(ticket: PreTradeOrderTicket, fill_fees: float, fill_slippage: float) -> PostTradeReviewCheck:
    estimated = max(0.0, ticket.estimated_fees + ticket.estimated_slippage)
    actual = max(0.0, fill_fees + fill_slippage)
    if actual <= 0 and estimated > 0:
        return PostTradeReviewCheck(
            "fees_slippage",
            "WARN",
            f"Ticket estimated costs {estimated:.2f}, but manual fill recorded zero fees/slippage.",
            "Enter broker-confirmed fees and slippage before treating execution quality as complete.",
        )
    if estimated > 0 and actual > estimated * 1.25 + 0.01:
        return PostTradeReviewCheck(
            "fees_slippage",
            "WARN",
            f"Actual recorded costs {actual:.2f} exceed ticket estimate {estimated:.2f} by more than 25%.",
            "Review broker fee profile and update fee assumptions if this is repeatable.",
        )
    return PostTradeReviewCheck(
        "fees_slippage",
        "OK",
        f"Actual recorded costs {actual:.2f} are within the ticket cost estimate {estimated:.2f}.",
        "No action required.",
    )


def _sensitivity_check(
    sensitivity: ExecutionSensitivityReport,
    adverse_price_cost: float,
    actual_cost: float,
    estimated_cost: float,
) -> PostTradeReviewCheck:
    incremental_cost = adverse_price_cost + max(0.0, actual_cost - estimated_cost)
    if sensitivity.status == "BLOCKED":
        return PostTradeReviewCheck(
            "execution_sensitivity",
            "BLOCKED",
            "The pre-trade sensitivity report already showed edge exhaustion under at least one worse-fill band.",
            "Do not treat this execution as robust without a separate exception review.",
        )
    if sensitivity.status == "NO_ACTION" or not sensitivity.bands:
        return PostTradeReviewCheck(
            "execution_sensitivity",
            "NO_DATA",
            "No execution sensitivity bands were available for this ticket.",
            "Review execution quality manually before drawing conclusions.",
        )
    if sensitivity.status == "WARN":
        return PostTradeReviewCheck(
            "execution_sensitivity",
            "WARN",
            f"Sensitivity was already thin; actual incremental adverse cost is {incremental_cost:.2f}.",
            "Treat the fill as fragile and prefer tighter limits until more evidence is collected.",
        )
    if incremental_cost > max(0.0, sensitivity.worst_net_edge):
        return PostTradeReviewCheck(
            "execution_sensitivity",
            "WARN",
            f"Actual incremental adverse cost {incremental_cost:.2f} exceeds worst stressed net edge {sensitivity.worst_net_edge:.2f}.",
            "Do not count the setup as execution-robust; review limit placement and slippage assumptions.",
        )
    return PostTradeReviewCheck(
        "execution_sensitivity",
        "OK",
        f"Actual incremental adverse cost {incremental_cost:.2f} is within worst stressed net edge {sensitivity.worst_net_edge:.2f}.",
        "No action required.",
    )


def _adverse_price_cost(side: Side, limit_price: float, fill_avg_price: float, qty: int) -> float:
    if side is Side.BUY:
        return max(0.0, fill_avg_price - limit_price) * qty
    return max(0.0, limit_price - fill_avg_price) * qty


def _aggregate_status(statuses: Iterable[str]) -> str:
    status_set = set(statuses)
    if "BLOCKED" in status_set:
        return "BLOCKED"
    if "WARN" in status_set or "NO_DATA" in status_set:
        return "WARN"
    if "NO_FILL" in status_set:
        return "NO_FILL"
    if "NO_ACTION" in status_set:
        return "NO_ACTION"
    return "OK"


def _summary(status: str, side: Side, expected_qty: int, fill_qty: int, fill_avg_price: float, pair_id: str) -> str:
    prefix = f"Post-trade review for {side.value} {fill_qty}/{expected_qty} at average {fill_avg_price:.4f} on pair {pair_id}."
    if status == "OK":
        return prefix + " Manual fill matches ticket quantity, ticket price discipline, costs, and sensitivity checks."
    if status == "BLOCKED":
        return prefix + " A hard conflict was found; do not use this fill for risk or cost-basis accounting until reconciled."
    return prefix + " Review warnings remain; execution quality is not clean enough for automatic interpretation."


def _empty_summary(status: str, ticket: PreTradeOrderTicket, pair_id: str) -> str:
    if status == "NO_ACTION":
        return "No post-trade review is active because the pre-trade ticket has no actionable side or quantity."
    return f"No manual {ticket.side} fill has been recorded for {ticket.symbol} pair {pair_id}."