import json

from app.broker_import import load_broker_fill_export, reconcile_manual_fills_with_broker_export
from app.manual_fills import make_manual_fill, manual_pair_id


def test_load_broker_fill_export_from_csv(tmp_path) -> None:
    path = tmp_path / "broker.csv"
    path.write_text(
        "broker_fill_id,order_id,symbol,side,qty,price,ts,fees,slippage,status\n"
        "bf1,o1,603236,SELL,100,53.98,2026-06-20 10:00:00,1.2,0.3,FILLED\n",
        encoding="utf-8",
    )

    rows = load_broker_fill_export(path)

    assert len(rows) == 1
    assert rows[0].broker_fill_id == "bf1"
    assert rows[0].side.value == "SELL"
    assert rows[0].fees == 1.2


def test_load_broker_fill_export_from_json_object(tmp_path) -> None:
    path = tmp_path / "broker.json"
    path.write_text(
        json.dumps(
            {
                "fills": [
                    {
                        "fill_id": "bf1",
                        "symbol": "603236",
                        "side": "BUY",
                        "qty": 100,
                        "price": 53.5,
                        "ts": "2026-06-20T10:05:00",
                    }
                ]
            }
        ),
        encoding="utf-8",
    )

    rows = load_broker_fill_export(path)

    assert rows[0].broker_fill_id == "bf1"
    assert rows[0].match_key[-1] == "2026-06-20 10:05:00"


def test_broker_reconciliation_matches_manual_fill_exact_key(tmp_path) -> None:
    pair_id = manual_pair_id("603236", "SB", 53.98, 100)
    manual = make_manual_fill("603236", pair_id, "SELL", 100, 53.98, ts="2026-06-20 10:00:00")
    broker = load_broker_fill_export(_write_broker_csv(tmp_path, "bf1,603236,SELL,100,53.98,2026-06-20 10:00:00\n"))

    report = reconcile_manual_fills_with_broker_export([manual], broker, symbol="603236")

    assert report.status == "OK"
    assert report.matched_count == 1
    assert report.items[0].status == "MATCHED"


def test_broker_reconciliation_flags_broker_only_and_manual_only(tmp_path) -> None:
    pair_id = manual_pair_id("603236", "SB", 53.98, 100)
    manual = make_manual_fill("603236", pair_id, "SELL", 100, 53.98, ts="2026-06-20 10:00:00")
    broker = load_broker_fill_export(_write_broker_csv(tmp_path, "bf2,603236,BUY,100,53.50,2026-06-20 10:05:00\n"))

    report = reconcile_manual_fills_with_broker_export([manual], broker, symbol="603236")

    assert report.status == "WARN"
    assert report.broker_only_count == 1
    assert report.manual_only_count == 1


def test_broker_reconciliation_blocks_ambiguous_duplicate_keys(tmp_path) -> None:
    pair_id = manual_pair_id("603236", "SB", 53.98, 100)
    manual = make_manual_fill("603236", pair_id, "SELL", 100, 53.98, ts="2026-06-20 10:00:00")
    broker = load_broker_fill_export(
        _write_broker_csv(
            tmp_path,
            "bf1,603236,SELL,100,53.98,2026-06-20 10:00:00\n"
            "bf2,603236,SELL,100,53.98,2026-06-20 10:00:00\n",
        )
    )

    report = reconcile_manual_fills_with_broker_export([manual], broker, symbol="603236")

    assert report.status == "BLOCKED"
    assert report.ambiguous_count == 1


def _write_broker_csv(tmp_path, rows: str):
    path = tmp_path / "broker.csv"
    path.write_text("broker_fill_id,symbol,side,qty,price,ts\n" + rows, encoding="utf-8")
    return path

def test_broker_fill_promotion_preview_requires_pair_and_review_token(tmp_path) -> None:
    from app.broker_import import build_broker_fill_promotion_preview

    broker = load_broker_fill_export(_write_broker_csv(tmp_path, "bf3,603236,SELL,100,53.98,2026-06-20 10:00:00\n"))

    preview = build_broker_fill_promotion_preview([], broker, "bf3", pair_id="")

    assert preview.status == "BLOCKED"
    assert any(check.match_key == "pair_assignment" and check.status == "BLOCKED" for check in preview.checks)
    assert any(check.match_key == "review_token" and check.status == "REVIEW_REQUIRED" for check in preview.checks)


def test_broker_fill_promotion_preview_ready_with_pair_and_token(tmp_path) -> None:
    from app.broker_import import BROKER_FILL_PROMOTION_REVIEW_TOKEN, build_broker_fill_promotion_preview

    broker = load_broker_fill_export(_write_broker_csv(tmp_path, "bf3,603236,SELL,100,53.98,2026-06-20 10:00:00\n"))

    preview = build_broker_fill_promotion_preview([], broker, "bf3", "603236-SB-53p9800-100", BROKER_FILL_PROMOTION_REVIEW_TOKEN)

    assert preview.status == "READY"
    assert preview.manual_fill_id.startswith("manual-from-broker-bf3")
    assert any(check.match_key == "ready" and check.status == "OK" for check in preview.checks)


def test_promote_broker_fill_after_review_creates_manual_fill_with_pair_context(tmp_path) -> None:
    from app.broker_import import BROKER_FILL_PROMOTION_REVIEW_TOKEN, promote_broker_fill_after_review

    broker = load_broker_fill_export(_write_broker_csv(tmp_path, "bf3,603236,SELL,100,53.98,2026-06-20 10:00:00\n"))

    fill = promote_broker_fill_after_review([], broker, "bf3", "603236-SB-53p9800-100", BROKER_FILL_PROMOTION_REVIEW_TOKEN)

    assert fill.symbol == "603236"
    assert fill.pair_id == "603236-SB-53p9800-100"
    assert fill.side.value == "SELL"
    assert fill.note.startswith("Broker-confirmed")


def test_broker_fill_promotion_blocks_duplicate_manual_key(tmp_path) -> None:
    from app.broker_import import BROKER_FILL_PROMOTION_REVIEW_TOKEN, build_broker_fill_promotion_preview

    broker = load_broker_fill_export(_write_broker_csv(tmp_path, "bf3,603236,SELL,100,53.98,2026-06-20 10:00:00\n"))
    manual = make_manual_fill("603236", "603236-SB-53p9800-100", "SELL", 100, 53.98, ts="2026-06-20 10:00:00")

    preview = build_broker_fill_promotion_preview([manual], broker, "bf3", "603236-SB-53p9800-100", BROKER_FILL_PROMOTION_REVIEW_TOKEN)

    assert preview.status == "BLOCKED"
    assert any(check.match_key == "manual_duplicate" and check.status == "BLOCKED" for check in preview.checks)
