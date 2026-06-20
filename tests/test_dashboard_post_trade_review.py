from app.dashboard import _build_post_trade_review_table
from app.post_trade_review import PostTradeReviewCheck, PostTradeReviewReport


def test_dashboard_post_trade_review_table_flattens_checks() -> None:
    report = PostTradeReviewReport(
        status="OK",
        summary="review ok",
        symbol="603236",
        pair_id="603236-SB-53p9800-1000",
        expected_side="SELL",
        expected_qty=1000,
        ticket_limit_price=53.98,
        fill_qty=1000,
        fill_avg_price=53.98,
        fill_fees=20.0,
        fill_slippage=10.0,
        realized_notional=53980.0,
        price_diff_vs_ticket=0.0,
        ticket_estimated_fees=20.0,
        ticket_estimated_slippage=10.0,
        sensitivity_status="OK",
        worst_sensitivity_net_edge=800.0,
        checks=(
            PostTradeReviewCheck("quantity", "OK", "matched", "none"),
            PostTradeReviewCheck("execution_sensitivity", "OK", "within band", "none"),
        ),
    )

    table = _build_post_trade_review_table(report)

    assert list(table.columns) == ["check", "status", "detail", "operator_action"]
    assert list(table["check"]) == ["quantity", "execution_sensitivity"]