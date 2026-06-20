from app.broker_import import BrokerFillPromotionPreview, BrokerFillReconciliationItem
from app.dashboard import _build_broker_fill_promotion_preview_table


def test_dashboard_broker_fill_promotion_preview_table_flattens_checks() -> None:
    preview = BrokerFillPromotionPreview(
        status="REVIEW_REQUIRED",
        summary="review required",
        broker_fill_id="bf3",
        pair_id="603236-SB-53p9800-100",
        manual_fill_id="manual-from-broker-bf3",
        symbol="603236",
        side="SELL",
        qty=100,
        price=53.98,
        ts="2026-06-20 10:00:00",
        checks=(
            BrokerFillReconciliationItem("review_token", "REVIEW_REQUIRED", "bf3", "manual-from-broker-bf3", "603236", "SELL", 100, 53.98, "2026-06-20 10:00:00", "token missing", "supply token"),
        ),
    )

    table = _build_broker_fill_promotion_preview_table(preview)

    assert list(table.columns) == ["match_key", "status", "broker_fill_id", "manual_fill_id", "symbol", "side", "qty", "price", "ts", "detail", "operator_action"]
    assert table.iloc[0]["status"] == "REVIEW_REQUIRED"