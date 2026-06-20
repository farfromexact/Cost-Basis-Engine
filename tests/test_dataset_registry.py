from research.dataset_registry import (
    DATASET_REGISTRY,
    LOCKED_OOS_SCENARIOS,
    SPLIT_IN_SAMPLE,
    SPLIT_OUT_OF_SAMPLE,
    get_dataset_record,
    load_dataset_bars,
    split_summary,
    verify_dataset_lock,
)
from research.evaluation_report import DEFAULT_SCENARIOS


EXPECTED_LOCKED_OOS = {
    "oos_000001_20260612_yahoo": ("000001", "20260612", 330),
    "oos_300750_20260616_yahoo": ("300750", "20260616", 330),
    "oos_000858_20260617_yahoo": ("000858", "20260617", 330),
    "oos_300750_20260618_eastmoney": ("300750", "20260618", 240),
    "oos_000001_20260618_eastmoney": ("000001", "20260618", 241),
}


def test_dataset_registry_labels_default_scenarios_as_in_sample() -> None:
    records = [get_dataset_record(name) for name in DEFAULT_SCENARIOS]

    assert {record.scenario for record in records} == set(DEFAULT_SCENARIOS)
    assert {record.split for record in records} == {SPLIT_IN_SAMPLE}
    assert all(record.dataset_id for record in records)
    assert split_summary(records)["out_of_sample"] == 0
    assert "No locked out-of-sample dataset" in split_summary(records)["claim_scope"]


def test_locked_oos_datasets_are_registered_across_symbols_and_dates() -> None:
    assert set(LOCKED_OOS_SCENARIOS) == set(EXPECTED_LOCKED_OOS)
    records = [get_dataset_record(name) for name in LOCKED_OOS_SCENARIOS]

    assert {record.split for record in records} == {SPLIT_OUT_OF_SAMPLE}
    assert all(record.locked for record in records)
    assert len({record.data_path for record in records}) == len(records)
    assert len({meta[0] for meta in EXPECTED_LOCKED_OOS.values()}) >= 3
    assert len({meta[1] for meta in EXPECTED_LOCKED_OOS.values()}) >= 4


def test_locked_oos_dataset_hashes_and_bar_counts_are_verified() -> None:
    for scenario, (_symbol, _date, expected_count) in EXPECTED_LOCKED_OOS.items():
        record = get_dataset_record(scenario)

        assert verify_dataset_lock(record) == record.content_sha256
        bars = load_dataset_bars(record)
        assert len(bars) == expected_count
        assert str(bars[0].ts) == record.start_ts
        assert str(bars[-1].ts) == record.end_ts


def test_unregistered_scenario_is_rejected() -> None:
    try:
        get_dataset_record("unknown")
    except ValueError as exc:
        assert "not registered" in str(exc)
    else:
        raise AssertionError("unregistered scenario should fail")


def test_registry_contains_only_unique_dataset_ids() -> None:
    ids = [record.dataset_id for record in DATASET_REGISTRY.values()]

    assert len(ids) == len(set(ids))

