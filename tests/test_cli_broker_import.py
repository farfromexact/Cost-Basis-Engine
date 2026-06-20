from types import SimpleNamespace

from app.cli import _run_broker_import_command
from app.manual_fills import make_manual_fill, manual_pair_id, save_manual_fills


def test_cli_broker_import_outputs_reconciliation_report(tmp_path, capsys) -> None:
    pair_id = manual_pair_id("603236", "SB", 53.98, 100)
    manual_path = tmp_path / "manual.json"
    save_manual_fills(
        [make_manual_fill("603236", pair_id, "SELL", 100, 53.98, ts="2026-06-20 10:00:00")],
        manual_path,
    )
    broker_path = tmp_path / "broker.csv"
    broker_path.write_text(
        "broker_fill_id,symbol,side,qty,price,ts\n"
        "bf1,603236,SELL,100,53.98,2026-06-20 10:00:00\n",
        encoding="utf-8",
    )

    _run_broker_import_command(SimpleNamespace(path=str(broker_path), manual_fills_path=str(manual_path), symbol="603236"))

    output = capsys.readouterr().out
    assert '"status": "OK"' in output
    assert '"matched_count": 1' in output
    assert '"supported_columns"' in output

def test_cli_broker_promote_previews_without_writing_when_token_missing(tmp_path, capsys) -> None:
    from app.cli import _run_broker_promote_command
    from app.manual_fills import load_manual_fills

    manual_path = tmp_path / "manual.json"
    manual_path.write_text("[]", encoding="utf-8")
    broker_path = tmp_path / "broker.csv"
    broker_path.write_text(
        "broker_fill_id,symbol,side,qty,price,ts\n"
        "bf3,603236,SELL,100,53.98,2026-06-20 10:00:00\n",
        encoding="utf-8",
    )

    _run_broker_promote_command(SimpleNamespace(path=str(broker_path), manual_fills_path=str(manual_path), broker_fill_id="bf3", pair_id="603236-SB-53p9800-100", review_token=None, note="reviewed"))

    output = capsys.readouterr().out
    assert '"status": "REVIEW_REQUIRED"' in output
    assert load_manual_fills(manual_path) == []


def test_cli_broker_promote_writes_after_review_token(tmp_path, capsys) -> None:
    from app.broker_import import BROKER_FILL_PROMOTION_REVIEW_TOKEN
    from app.cli import _run_broker_promote_command
    from app.manual_fills import load_manual_fills

    manual_path = tmp_path / "manual.json"
    manual_path.write_text("[]", encoding="utf-8")
    broker_path = tmp_path / "broker.csv"
    broker_path.write_text(
        "broker_fill_id,symbol,side,qty,price,ts\n"
        "bf3,603236,SELL,100,53.98,2026-06-20 10:00:00\n",
        encoding="utf-8",
    )

    _run_broker_promote_command(SimpleNamespace(path=str(broker_path), manual_fills_path=str(manual_path), broker_fill_id="bf3", pair_id="603236-SB-53p9800-100", review_token=BROKER_FILL_PROMOTION_REVIEW_TOKEN, note="reviewed"))

    output = capsys.readouterr().out
    fills = load_manual_fills(manual_path)
    assert '"status": "READY"' in output
    assert '"recorded"' in output
    assert len(fills) == 1
    assert fills[0].pair_id == "603236-SB-53p9800-100"
