from __future__ import annotations

import hashlib
from dataclasses import dataclass
from pathlib import Path

from core.models import MinuteBar
from data.adapters import load_minute_csv
from research.scenarios import get_scenario


SPLIT_IN_SAMPLE = "in_sample"
SPLIT_OUT_OF_SAMPLE = "out_of_sample"
_ALLOWED_SPLITS = {SPLIT_IN_SAMPLE, SPLIT_OUT_OF_SAMPLE}
DATASET_KIND_SYNTHETIC = "synthetic"
DATASET_KIND_CSV = "csv"
_ALLOWED_KINDS = {DATASET_KIND_SYNTHETIC, DATASET_KIND_CSV}


@dataclass(frozen=True)
class DatasetRecord:
    dataset_id: str
    scenario: str
    split: str
    label: str
    source: str
    start_ts: str
    end_ts: str
    note: str
    kind: str = DATASET_KIND_SYNTHETIC
    data_path: str = ""
    content_sha256: str = ""
    locked: bool = False

    def __post_init__(self) -> None:
        if self.split not in _ALLOWED_SPLITS:
            raise ValueError(f"dataset split must be one of {_ALLOWED_SPLITS}: {self.split}")
        if self.kind not in _ALLOWED_KINDS:
            raise ValueError(f"dataset kind must be one of {_ALLOWED_KINDS}: {self.kind}")
        if self.kind == DATASET_KIND_CSV and not self.data_path:
            raise ValueError("csv dataset records require data_path")
        if self.locked and not self.content_sha256:
            raise ValueError("locked dataset records require content_sha256")

    def as_dict(self) -> dict:
        return {
            "dataset_id": self.dataset_id,
            "scenario": self.scenario,
            "split": self.split,
            "label": self.label,
            "source": self.source,
            "start_ts": self.start_ts,
            "end_ts": self.end_ts,
            "note": self.note,
            "kind": self.kind,
            "data_path": self.data_path,
            "content_sha256": self.content_sha256,
            "locked": self.locked,
            "is_out_of_sample": self.is_out_of_sample,
        }

    @property
    def is_out_of_sample(self) -> bool:
        return self.split == SPLIT_OUT_OF_SAMPLE


DATASET_REGISTRY: dict[str, DatasetRecord] = {
    "mean_revert": DatasetRecord(
        dataset_id="synthetic_mean_revert_v1",
        scenario="mean_revert",
        split=SPLIT_IN_SAMPLE,
        label="Synthetic mean-reversion fixture",
        source="research.scenarios",
        start_ts="2026-01-02 09:30:00",
        end_ts="2026-01-02 09:37:00",
        note="Synthetic research fixture used for mechanics and regression checks; not out-of-sample evidence.",
    ),
    "one_way_up": DatasetRecord(
        dataset_id="synthetic_one_way_up_v1",
        scenario="one_way_up",
        split=SPLIT_IN_SAMPLE,
        label="Synthetic one-way-up risk fixture",
        source="research.scenarios",
        start_ts="2026-01-02 09:30:00",
        end_ts="2026-01-02 09:37:00",
        note="Synthetic research fixture used to expose sell-fly/open-pair risk; not out-of-sample evidence.",
    ),
    "low_liquidity": DatasetRecord(
        dataset_id="synthetic_low_liquidity_v1",
        scenario="low_liquidity",
        split=SPLIT_IN_SAMPLE,
        label="Synthetic low-liquidity fixture",
        source="research.scenarios",
        start_ts="2026-01-02 09:30:00",
        end_ts="2026-01-02 09:34:00",
        note="Synthetic research fixture used to test liquidity blockers; not out-of-sample evidence.",
    ),
    "oos_000001_20260612_yahoo": DatasetRecord(
        dataset_id="locked_oos_000001_20260612_yahoo_v1",
        scenario="oos_000001_20260612_yahoo",
        split=SPLIT_OUT_OF_SAMPLE,
        label="Locked OOS Yahoo intraday sample: 000001.SZ on 2026-06-12",
        source="Yahoo public chart feed captured from query1.finance.yahoo.com",
        start_ts="2026-06-12 09:30:00",
        end_ts="2026-06-12 14:59:00",
        note=(
            "Real public-chart minute bars locked before inclusion in model evaluation. "
            "Turnover amount is approximated as close * volume; this is OOS regression data, not broker-confirmed market data."
        ),
        kind=DATASET_KIND_CSV,
        data_path="datasets/oos/000001_20260612_yahoo_intraday.csv",
        content_sha256="0470e0fce70e2a5dc13c71a3ce659a05ed7665f7452c994d37820a68791c0f3a",
        locked=True,
    ),
    "oos_300750_20260616_yahoo": DatasetRecord(
        dataset_id="locked_oos_300750_20260616_yahoo_v1",
        scenario="oos_300750_20260616_yahoo",
        split=SPLIT_OUT_OF_SAMPLE,
        label="Locked OOS Yahoo intraday sample: 300750.SZ on 2026-06-16",
        source="Yahoo public chart feed captured from query1.finance.yahoo.com",
        start_ts="2026-06-16 09:30:00",
        end_ts="2026-06-16 14:59:00",
        note=(
            "Real public-chart minute bars locked before inclusion in model evaluation. "
            "Turnover amount is approximated as close * volume; this is OOS regression data, not broker-confirmed market data."
        ),
        kind=DATASET_KIND_CSV,
        data_path="datasets/oos/300750_20260616_yahoo_intraday.csv",
        content_sha256="bd377511fb4281a87947ade46f01276afa4e4c8e6b35a577d2a74e61417e64f2",
        locked=True,
    ),
    "oos_000858_20260617_yahoo": DatasetRecord(
        dataset_id="locked_oos_000858_20260617_yahoo_v1",
        scenario="oos_000858_20260617_yahoo",
        split=SPLIT_OUT_OF_SAMPLE,
        label="Locked OOS Yahoo intraday sample: 000858.SZ on 2026-06-17",
        source="Yahoo public chart feed captured from query1.finance.yahoo.com",
        start_ts="2026-06-17 09:30:00",
        end_ts="2026-06-17 14:59:00",
        note=(
            "Real public-chart minute bars locked before inclusion in model evaluation. "
            "Turnover amount is approximated as close * volume; this is OOS regression data, not broker-confirmed market data."
        ),
        kind=DATASET_KIND_CSV,
        data_path="datasets/oos/000858_20260617_yahoo_intraday.csv",
        content_sha256="5b5a93def674502d3329b00300257e6a6f6f1d3bc17aeec8212d40e5e4c971e2",
        locked=True,
    ),    "oos_300750_20260618_eastmoney": DatasetRecord(
        dataset_id="locked_oos_300750_20260618_eastmoney_v1",
        scenario="oos_300750_20260618_eastmoney",
        split=SPLIT_OUT_OF_SAMPLE,
        label="Locked OOS Eastmoney intraday sample: 300750 on 2026-06-18",
        source="Eastmoney public quote endpoint captured via multi-day trends request",
        start_ts="2026-06-18 09:30:00",
        end_ts="2026-06-18 15:00:00",
        note=(
            "Real public-quote minute bars locked before inclusion in model evaluation. "
            "This adds symbol coverage but is still not sufficient for profitability or production-validity claims."
        ),
        kind=DATASET_KIND_CSV,
        data_path="datasets/oos/300750_20260618_eastmoney_intraday.csv",
        content_sha256="c31ec2034a3b3d80b3d0460cd6602b66413b33728795dbd6c3a2fa5e01d05f1b",
        locked=True,
    ),    "oos_000001_20260618_eastmoney": DatasetRecord(
        dataset_id="locked_oos_000001_20260618_eastmoney_v1",
        scenario="oos_000001_20260618_eastmoney",
        split=SPLIT_OUT_OF_SAMPLE,
        label="Locked OOS Eastmoney intraday sample: 000001 on 2026-06-18",
        source="Eastmoney public quote endpoint captured via data.eastmoney.fetch_intraday_minute_bars",
        start_ts="2026-06-18 09:30:00",
        end_ts="2026-06-18 15:00:00",
        note=(
            "Real public-quote minute bars locked before inclusion in model evaluation. "
            "This is one OOS sample only; it is not sufficient for profitability or production-validity claims."
        ),
        kind=DATASET_KIND_CSV,
        data_path="datasets/oos/000001_20260618_eastmoney_intraday.csv",
        content_sha256="f49358b32e3a8904ef5b2251d8a749ff79e9175bbc4d3767c5c643183751dc7d",
        locked=True,
    ),
}


LOCKED_OOS_SCENARIOS = tuple(
    scenario for scenario, record in DATASET_REGISTRY.items() if record.split == SPLIT_OUT_OF_SAMPLE and record.locked
)


def get_dataset_record(scenario: str) -> DatasetRecord:
    try:
        return DATASET_REGISTRY[scenario]
    except KeyError as exc:
        raise ValueError(f"scenario is not registered in dataset registry: {scenario}") from exc


def dataset_records_for_scenarios(scenarios: list[str] | tuple[str, ...]) -> list[DatasetRecord]:
    return [get_dataset_record(scenario) for scenario in scenarios]


def load_dataset_bars(record: DatasetRecord, root: str | Path = ".") -> list[MinuteBar]:
    if record.kind == DATASET_KIND_SYNTHETIC:
        return get_scenario(record.scenario)
    path = _resolve_data_path(record, root)
    verify_dataset_lock(record, root=root)
    return load_minute_csv(path)


def verify_dataset_lock(record: DatasetRecord, root: str | Path = ".") -> str:
    if not record.locked:
        return ""
    path = _resolve_data_path(record, root)
    actual = file_sha256(path)
    expected = record.content_sha256.lower()
    if actual != expected:
        raise ValueError(
            f"locked dataset hash mismatch for {record.scenario}: expected {expected}, got {actual}"
        )
    return actual


def file_sha256(path: str | Path) -> str:
    digest = hashlib.sha256()
    with Path(path).open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def split_summary(records: list[DatasetRecord]) -> dict:
    counts = {SPLIT_IN_SAMPLE: 0, SPLIT_OUT_OF_SAMPLE: 0}
    locked_oos = 0
    for record in records:
        counts[record.split] += 1
        if record.split == SPLIT_OUT_OF_SAMPLE and record.locked:
            locked_oos += 1
    return {
        "in_sample": counts[SPLIT_IN_SAMPLE],
        "out_of_sample": counts[SPLIT_OUT_OF_SAMPLE],
        "locked_out_of_sample": locked_oos,
        "has_out_of_sample": counts[SPLIT_OUT_OF_SAMPLE] > 0,
        "claim_scope": (
            "Locked out-of-sample rows are present, but profitability still requires many independent OOS samples and full metric review."
            if locked_oos > 0
            else "No locked out-of-sample dataset is registered; do not make profitability or production-validity claims."
        ),
    }


def _resolve_data_path(record: DatasetRecord, root: str | Path) -> Path:
    path = Path(record.data_path)
    if not path.is_absolute():
        path = Path(root) / path
    if not path.exists():
        raise ValueError(f"dataset file is missing for {record.scenario}: {path}")
    return path


