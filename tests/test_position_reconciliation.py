from app.position_reconciliation import (
    BrokerPositionSnapshot,
    load_broker_position_snapshot,
    reconcile_position_state,
    save_broker_position_snapshot,
)
from app.position_state import PositionSnapshot


def test_reconciliation_ok_when_broker_matches_persisted() -> None:
    persisted = PositionSnapshot(symbol="603236", held_qty=151400, settled_sellable_qty=120000, purchasable_qty=15100)
    broker = BrokerPositionSnapshot(
        market_source="A-share / Eastmoney",
        symbol="603236",
        total_qty=151400,
        sellable_qty=120000,
        purchasable_qty=15100,
        as_of="2026-06-20 10:00:00",
    )

    report = reconcile_position_state(persisted, broker)

    assert report.status == "OK"
    assert all(item.status == "OK" for item in report.items)


def test_reconciliation_blocks_when_persisted_overstates_sellable_qty() -> None:
    persisted = PositionSnapshot(symbol="603236", held_qty=151400, settled_sellable_qty=151400, purchasable_qty=15100)
    broker = BrokerPositionSnapshot(
        market_source="A-share / Eastmoney",
        symbol="603236",
        total_qty=151400,
        sellable_qty=100000,
        purchasable_qty=15100,
    )

    report = reconcile_position_state(persisted, broker)

    assert report.status == "BLOCKED"
    sellable = next(item for item in report.items if item.field == "settled_sellable_qty")
    assert sellable.delta == "51400"
    assert "higher than broker-confirmed" in sellable.operator_action


def test_reconciliation_warns_when_persisted_understates_capacity() -> None:
    persisted = PositionSnapshot(symbol="603236", held_qty=100000, settled_sellable_qty=90000, purchasable_qty=10000)
    broker = BrokerPositionSnapshot(
        market_source="A-share / Eastmoney",
        symbol="603236",
        total_qty=151400,
        sellable_qty=120000,
        purchasable_qty=15100,
    )

    report = reconcile_position_state(persisted, broker)

    assert report.status == "WARN"
    assert any(item.delta.startswith("-") and item.status == "WARN" for item in report.items)


def test_reconciliation_blocks_symbol_mismatch() -> None:
    persisted = PositionSnapshot(symbol="603236")
    broker = BrokerPositionSnapshot(
        market_source="A-share / Eastmoney",
        symbol="000001",
        total_qty=151400,
        sellable_qty=151400,
        purchasable_qty=15100,
    )

    report = reconcile_position_state(persisted, broker)

    assert report.status == "BLOCKED"
    assert next(item for item in report.items if item.field == "symbol").status == "BLOCKED"


def test_broker_snapshot_round_trips_to_json(tmp_path) -> None:
    path = tmp_path / "broker_position.json"
    snapshot = BrokerPositionSnapshot(
        market_source="Korea / Yahoo Finance",
        symbol="005930.KS",
        total_qty=1000,
        sellable_qty=800,
        purchasable_qty=120,
        cash_available=1_000_000.0,
        as_of="2026-06-20 10:00:00",
        note="manual check",
    )

    save_broker_position_snapshot(snapshot, path)
    loaded = load_broker_position_snapshot(path)

    assert loaded is not None
    assert loaded.symbol == "005930.KS"
    assert loaded.cash_available == 1_000_000.0
    assert loaded.recorded_at
