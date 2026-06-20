from types import SimpleNamespace

from app.cli import _broker_snapshot_from_args
from app.position_state import PositionSnapshot


def test_cli_broker_snapshot_from_args_uses_persisted_symbol_defaults() -> None:
    args = SimpleNamespace(
        market_source=None,
        symbol=None,
        total_qty=151400,
        sellable_qty=120000,
        purchasable_qty=15100,
        cash_available=50000.0,
        as_of="2026-06-20 10:00:00",
        note="broker screen",
    )
    persisted = PositionSnapshot(symbol="603236", market_source="A-share / Eastmoney")

    snapshot = _broker_snapshot_from_args(args, persisted)

    assert snapshot.symbol == "603236"
    assert snapshot.market_source == "A-share / Eastmoney"
    assert snapshot.sellable_qty == 120000
    assert snapshot.note == "broker screen"


def test_cli_broker_snapshot_requires_core_quantities() -> None:
    args = SimpleNamespace(
        market_source="A-share / Eastmoney",
        symbol="603236",
        total_qty=151400,
        sellable_qty=None,
        purchasable_qty=15100,
        cash_available=0.0,
        as_of=None,
        note="",
    )

    try:
        _broker_snapshot_from_args(args, None)
    except SystemExit as exc:
        assert "--sellable-qty" in str(exc)
    else:
        raise AssertionError("missing sellable qty should fail")
