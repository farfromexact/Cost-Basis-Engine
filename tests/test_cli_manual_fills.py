from types import SimpleNamespace

from app.cli import _manual_fill_from_args
from app.manual_fills import manual_pair_id


def test_cli_manual_fill_from_args_derives_pair_id() -> None:
    args = SimpleNamespace(
        symbol="603236",
        pair_id=None,
        open_pair_side="SB",
        open_pair_price=53.98,
        qty=15100,
        side="SELL",
        price=53.98,
        ts="2026-06-20 10:00:00",
        fees=8.0,
        slippage=3.0,
        note="manual",
    )

    fill = _manual_fill_from_args(args)

    assert fill.pair_id == manual_pair_id("603236", "SB", 53.98, 15100)
    assert fill.side.value == "SELL"
    assert fill.note == "manual"


def test_cli_manual_fill_requires_core_fields() -> None:
    args = SimpleNamespace(
        symbol="603236",
        pair_id=None,
        open_pair_side="SB",
        open_pair_price=53.98,
        qty=None,
        side="SELL",
        price=53.98,
        ts=None,
        fees=0.0,
        slippage=0.0,
        note="manual",
    )

    try:
        _manual_fill_from_args(args)
    except SystemExit as exc:
        assert "--qty" in str(exc)
    else:
        raise AssertionError("missing qty should fail")
