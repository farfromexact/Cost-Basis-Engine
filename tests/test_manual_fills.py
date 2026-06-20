from app.manual_fills import (
    MANUAL_FILL_NOTE,
    build_execution_checklist,
    expected_close_side,
    expected_next_fill_side,
    expected_open_side,
    load_manual_fills,
    make_manual_fill,
    manual_pair_id,
    record_manual_fill,
)
from core.models import Side


def test_manual_fill_round_trips_to_json(tmp_path) -> None:
    path = tmp_path / "manual_fills.json"
    pair_id = manual_pair_id("603236", "SB", 53.98, 15100)
    fill = make_manual_fill("603236", pair_id, Side.SELL, 15100, 53.98, ts="2026-06-20 10:00:00", fees=8.0, slippage=3.0)

    record_manual_fill(fill, path)
    loaded = load_manual_fills(path)

    assert loaded == [fill]
    assert loaded[0].note == MANUAL_FILL_NOTE
    assert loaded[0].cash_delta == 15100 * 53.98 - 8.0 - 3.0


def test_duplicate_manual_fill_id_is_rejected(tmp_path) -> None:
    path = tmp_path / "manual_fills.json"
    pair_id = manual_pair_id("603236", "SB", 53.98, 15100)
    fill = make_manual_fill("603236", pair_id, "SELL", 15100, 53.98, ts="2026-06-20 10:00:00")

    record_manual_fill(fill, path)
    try:
        record_manual_fill(fill, path)
    except ValueError as exc:
        assert "duplicate" in str(exc)
    else:
        raise AssertionError("duplicate fill should fail")


def test_execution_checklist_requires_manual_open_and_close_fills() -> None:
    pair_id = manual_pair_id("603236", "SB", 53.98, 15100)
    open_fill = make_manual_fill("603236", pair_id, "SELL", 15100, 53.98, ts="2026-06-20 10:00:00")

    missing = build_execution_checklist("603236", "SB", 53.98, 15100, [])
    open_only = build_execution_checklist("603236", "SB", 53.98, 15100, [open_fill])

    assert missing.status == "MISSING_MANUAL_OPEN_FILL"
    assert any(item.status == "REQUIRED" and "signals do not count" in item.detail for item in missing.items)
    assert open_only.status == "AWAITING_MANUAL_CLOSE_FILL"
    assert expected_next_fill_side("SB", [open_fill], pair_id) is Side.BUY


def test_execution_checklist_closes_only_after_manual_close_fill() -> None:
    pair_id = manual_pair_id("603236", "BS", 52.50, 15100)
    open_fill = make_manual_fill("603236", pair_id, "BUY", 15100, 52.50, ts="2026-06-20 10:00:00")
    close_fill = make_manual_fill("603236", pair_id, "SELL", 15100, 52.70, ts="2026-06-20 10:10:00")

    checklist = build_execution_checklist("603236", "BS", 52.50, 15100, [open_fill, close_fill])

    assert checklist.status == "MANUAL_CLOSE_RECORDED"
    assert expected_open_side("BS") is Side.BUY
    assert expected_close_side("BS") is Side.SELL
    assert all(item.status != "REQUIRED" for item in checklist.items if item.step.startswith("Record"))
