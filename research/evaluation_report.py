from __future__ import annotations

from dataclasses import asdict, dataclass

from core.fee_model import FeeModel
from core.inventory_ledger import InventoryLedger
from core.models import MinuteBar
from research.dataset_registry import (
    DatasetRecord,
    LOCKED_OOS_SCENARIOS,
    dataset_records_for_scenarios,
    load_dataset_bars,
    split_summary,
)
from research.evaluation import compare_to_no_trade
from research.replay import replay_sell_then_buy
from research.strategies import SellThenBuyBaselineStrategy, SellThenBuyConfig
from research.trigger_engine import (
    ActionType,
    PositionState,
    RulesConfig,
    TriggerEngine,
)


DEFAULT_SCENARIOS = ("mean_revert", "one_way_up", "low_liquidity")
DEFAULT_LOCKED_OOS_SCENARIOS = LOCKED_OOS_SCENARIOS


@dataclass(frozen=True)
class TriggerSignalReport:
    latest_action: str
    trigger_count: int
    watch_count: int
    no_trade_count: int
    latest_blockers: list[str]
    latest_warnings: list[str]
    note: str

    def as_dict(self) -> dict:
        return asdict(self)


@dataclass(frozen=True)
class ScenarioEvaluationReport:
    scenario: str
    dataset_id: str
    dataset_split: str
    dataset_label: str
    dataset_note: str
    dataset_source: str
    dataset_kind: str
    dataset_path: str
    dataset_locked: bool
    dataset_content_sha256: str
    is_out_of_sample: bool
    bar_count: int
    no_trade_baseline: dict
    simple_interpretable_baseline: dict
    simple_vs_no_trade: dict
    trigger_engine_signal: TriggerSignalReport
    capability_note: str

    def as_dict(self) -> dict:
        return {
            "scenario": self.scenario,
            "dataset_id": self.dataset_id,
            "dataset_split": self.dataset_split,
            "dataset_label": self.dataset_label,
            "dataset_note": self.dataset_note,
            "dataset_source": self.dataset_source,
            "dataset_kind": self.dataset_kind,
            "dataset_path": self.dataset_path,
            "dataset_locked": self.dataset_locked,
            "dataset_content_sha256": self.dataset_content_sha256,
            "is_out_of_sample": self.is_out_of_sample,
            "bar_count": self.bar_count,
            "no_trade_baseline": self.no_trade_baseline,
            "simple_interpretable_baseline": self.simple_interpretable_baseline,
            "simple_vs_no_trade": self.simple_vs_no_trade,
            "trigger_engine_signal": self.trigger_engine_signal.as_dict(),
            "capability_note": self.capability_note,
        }


@dataclass(frozen=True)
class EvaluationReport:
    scenarios: list[ScenarioEvaluationReport]
    split_summary: dict
    report_note: str

    def as_dict(self) -> dict:
        return {
            "scenarios": [scenario.as_dict() for scenario in self.scenarios],
            "split_summary": self.split_summary,
            "report_note": self.report_note,
        }


def build_evaluation_report(
    scenario_names: list[str] | tuple[str, ...] = DEFAULT_SCENARIOS,
    target_qty: int = 1000,
    settled_sellable_qty: int = 1000,
    purchasable_qty: int | None = None,
    trade_qty: int = 100,
    fee_model: FeeModel | None = None,
) -> EvaluationReport:
    records = dataset_records_for_scenarios(scenario_names)
    reports = [
        build_scenario_evaluation_report(
            dataset=record,
            bars=load_dataset_bars(record),
            target_qty=target_qty,
            settled_sellable_qty=settled_sellable_qty,
            purchasable_qty=purchasable_qty if purchasable_qty is not None else target_qty,
            trade_qty=trade_qty,
            fee_model=fee_model,
        )
        for record in records
    ]
    summary = split_summary(records)
    return EvaluationReport(
        scenarios=reports,
        split_summary=summary,
        report_note=(
            "Research comparison only: every row is dataset-registry labeled as in-sample or out-of-sample, "
            "and locked rows are hash-checked before evaluation. "
            f"{summary['claim_scope']} Trigger engine rows are signal diagnostics, simple baseline rows are replay metrics, "
            "and no profitability claim is implied."
        ),
    )


def build_locked_oos_evaluation_report(
    target_qty: int = 1000,
    settled_sellable_qty: int = 1000,
    purchasable_qty: int | None = None,
    trade_qty: int = 100,
    fee_model: FeeModel | None = None,
) -> EvaluationReport:
    return build_evaluation_report(
        scenario_names=DEFAULT_LOCKED_OOS_SCENARIOS,
        target_qty=target_qty,
        settled_sellable_qty=settled_sellable_qty,
        purchasable_qty=purchasable_qty,
        trade_qty=trade_qty,
        fee_model=fee_model,
    )


def build_scenario_evaluation_report(
    dataset: DatasetRecord,
    bars: list[MinuteBar],
    target_qty: int,
    settled_sellable_qty: int,
    purchasable_qty: int,
    trade_qty: int,
    fee_model: FeeModel | None = None,
) -> ScenarioEvaluationReport:
    fee_model = fee_model or FeeModel()
    simple_result = replay_sell_then_buy(
        bars=bars,
        ledger=InventoryLedger(target_qty=target_qty, settled_sellable_qty=settled_sellable_qty),
        strategy=SellThenBuyBaselineStrategy(
            SellThenBuyConfig(trade_qty=trade_qty, min_amount_ratio=1.0)
        ),
        fee_model=fee_model,
    )
    trigger_report = _trigger_signal_report(
        bars=bars,
        target_qty=target_qty,
        settled_sellable_qty=settled_sellable_qty,
        purchasable_qty=purchasable_qty,
        trade_qty=trade_qty,
        fee_model=fee_model,
    )
    return ScenarioEvaluationReport(
        scenario=dataset.scenario,
        dataset_id=dataset.dataset_id,
        dataset_split=dataset.split,
        dataset_label=dataset.label,
        dataset_note=dataset.note,
        dataset_source=dataset.source,
        dataset_kind=dataset.kind,
        dataset_path=dataset.data_path,
        dataset_locked=dataset.locked,
        dataset_content_sha256=dataset.content_sha256,
        is_out_of_sample=dataset.is_out_of_sample,
        bar_count=len(bars),
        no_trade_baseline=_no_trade_baseline(),
        simple_interpretable_baseline=simple_result.metrics.as_dict(),
        simple_vs_no_trade=asdict(compare_to_no_trade(simple_result.metrics)),
        trigger_engine_signal=trigger_report,
        capability_note=(
            f"Dataset split={dataset.split}; locked={dataset.locked}. Trigger engine is evaluated as closed-minute signal diagnostics only; "
            "fills and realized PnL are not inferred from trigger signals."
        ),
    )


def _trigger_signal_report(
    bars: list[MinuteBar],
    target_qty: int,
    settled_sellable_qty: int,
    purchasable_qty: int,
    trade_qty: int,
    fee_model: FeeModel,
) -> TriggerSignalReport:
    rules = RulesConfig(
        max_t_ratio=trade_qty / target_qty if target_qty else 0.0,
        max_single_trade_qty=trade_qty,
        start_time="09:30",
        min_amount_ratio=1.0,
    )
    engine = TriggerEngine(rules=rules, fee_model=fee_model)
    position = PositionState(
        target_qty=target_qty,
        current_total_qty=target_qty,
        settled_sellable_qty=settled_sellable_qty,
        purchasable_qty=purchasable_qty,
    )
    intents = [engine.evaluate("scenario", bars[: index + 1], position) for index in range(len(bars))]
    latest = intents[-1]
    trigger_count = sum(1 for intent in intents if intent.action_type in _TRIGGER_ACTIONS)
    watch_count = sum(1 for intent in intents if intent.action_type in _WATCH_ACTIONS)
    no_trade_count = sum(1 for intent in intents if intent.action_type is ActionType.NO_TRADE)
    return TriggerSignalReport(
        latest_action=latest.action_type.value,
        trigger_count=trigger_count,
        watch_count=watch_count,
        no_trade_count=no_trade_count,
        latest_blockers=latest.blockers,
        latest_warnings=latest.warnings,
        note="Signal scan uses only bars closed at each evaluated minute; no same-minute fill is assumed.",
    )


def _no_trade_baseline() -> dict:
    return {
        "label": "no_trade",
        "closed_t_net_pnl": 0.0,
        "excess_pnl_vs_hold": 0.0,
        "ending_quantity_delta": 0,
        "trade_count": 0,
    }


_TRIGGER_ACTIONS = {
    ActionType.TRIGGER_SELL_TO_BUY,
    ActionType.TRIGGER_BUY_TO_SELL,
}

_WATCH_ACTIONS = {
    ActionType.WATCH_SELL_TO_BUY,
    ActionType.WATCH_BUY_TO_SELL,
}
