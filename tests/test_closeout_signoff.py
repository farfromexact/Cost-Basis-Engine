import json

import pytest

from app.broker_import import reconcile_manual_fills_with_broker_export
from app.closeout_signoff import (
    CLOSEOUT_SIGNOFF_REVIEW_TOKEN,
    build_closeout_signoff_preview,
    write_closeout_signoff_after_review,
)
from app.end_of_day_review import build_end_of_day_review_report
from app.manual_fills import make_manual_fill, manual_pair_id
from app.session_closeout import build_session_closeout_report
from app.session_risk import build_live_session_risk_usage_report


def test_closeout_signoff_requires_review_token_before_write(tmp_path) -> None:
    closeout = _no_action_closeout()

    preview = build_closeout_signoff_preview(closeout, directory=tmp_path)

    assert preview.status == "REVIEW_REQUIRED"
    assert preview.closeout_status == "NO_ACTION"
    assert preview.signoff_path.endswith("eod-signoff-603236-2026-06-20.json")


def test_closeout_signoff_writes_no_action_snapshot_after_review(tmp_path) -> None:
    closeout = _no_action_closeout()
    review = build_end_of_day_review_report(closeout, recent_journals=[])

    path = write_closeout_signoff_after_review(
        closeout,
        review,
        review_token=CLOSEOUT_SIGNOFF_REVIEW_TOKEN,
        directory=tmp_path,
        reviewer_note="No fills; closeout reviewed.",
    )

    raw = path.read_text(encoding="utf-8")
    payload = json.loads(raw)
    assert payload["review_token_confirmed"] is True
    assert payload["closeout"]["status"] == "NO_ACTION"
    assert payload["end_of_day_review"]["closeout_status"] == "NO_ACTION"
    assert "APPROVE_EOD_CLOSEOUT_SIGNOFF" not in raw


def test_closeout_signoff_blocks_unmatched_manual_fills_even_with_token(tmp_path) -> None:
    closeout = _blocked_closeout()
    review = build_end_of_day_review_report(closeout, recent_journals=[])

    preview = build_closeout_signoff_preview(closeout, review_token=CLOSEOUT_SIGNOFF_REVIEW_TOKEN, directory=tmp_path)

    assert preview.status == "BLOCKED"
    with pytest.raises(ValueError, match="blocked"):
        write_closeout_signoff_after_review(closeout, review, CLOSEOUT_SIGNOFF_REVIEW_TOKEN, directory=tmp_path)


def _no_action_closeout():
    reconciliation = reconcile_manual_fills_with_broker_export([], [], symbol="603236")
    risk = build_live_session_risk_usage_report("603236", [], 10000, 10.0, "balanced", "2026-06-20", "2026-06-20 15:00:00")
    return build_session_closeout_report("603236", [], reconciliation, risk, "2026-06-20")


def _blocked_closeout():
    pair_id = manual_pair_id("603236", "SB", 10.0, 100)
    fills = [
        make_manual_fill("603236", pair_id, "SELL", 100, 10.0, ts="2026-06-20 10:00:00"),
        make_manual_fill("603236", pair_id, "BUY", 100, 9.8, ts="2026-06-20 10:20:00"),
    ]
    reconciliation = reconcile_manual_fills_with_broker_export(fills, [], symbol="603236")
    risk = build_live_session_risk_usage_report("603236", fills, 10000, 10.0, "balanced", "2026-06-20", "2026-06-20 15:00:00")
    return build_session_closeout_report("603236", fills, reconciliation, risk, "2026-06-20")
