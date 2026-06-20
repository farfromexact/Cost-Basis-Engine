from __future__ import annotations

from collections import defaultdict
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Iterable

from core.fee_model import FeeModel
from research.model_audit import (
    DEFAULT_MODEL_AUDIT_BASELINE_PATH,
    ModelAuditChange,
    build_model_change_audit_report,
    load_model_audit_baseline,
)
from research.trigger_engine import RulesConfig


@dataclass(frozen=True)
class ThresholdExperimentSpec:
    experiment_id: str
    label: str
    description: str
    overrides: dict[str, Any]

    def as_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class ThresholdExperimentResult:
    experiment_id: str
    label: str
    description: str
    audit_status: str
    threshold_overrides: dict[str, Any]
    threshold_changes: tuple[ModelAuditChange, ...]
    metric_changes: tuple[ModelAuditChange, ...]
    aggregate_metric_deltas: dict[str, float]
    interpretation_note: str

    def as_dict(self) -> dict[str, Any]:
        return {
            "experiment_id": self.experiment_id,
            "label": self.label,
            "description": self.description,
            "audit_status": self.audit_status,
            "threshold_overrides": self.threshold_overrides,
            "threshold_changes": [change.as_dict() for change in self.threshold_changes],
            "metric_changes": [change.as_dict() for change in self.metric_changes],
            "aggregate_metric_deltas": self.aggregate_metric_deltas,
            "interpretation_note": self.interpretation_note,
        }


@dataclass(frozen=True)
class ThresholdExperimentReport:
    baseline_id: str
    baseline_path: str
    locked_oos_count: int
    experiments: tuple[ThresholdExperimentResult, ...]
    report_note: str

    def as_dict(self) -> dict[str, Any]:
        return {
            "baseline_id": self.baseline_id,
            "baseline_path": self.baseline_path,
            "locked_oos_count": self.locked_oos_count,
            "experiments": [experiment.as_dict() for experiment in self.experiments],
            "report_note": self.report_note,
        }


BUILT_IN_THRESHOLD_EXPERIMENTS: tuple[ThresholdExperimentSpec, ...] = (
    ThresholdExperimentSpec(
        experiment_id="more_selective",
        label="More selective trigger gate",
        description="Require larger VWAP deviations and stronger turnover confirmation before actionable triggers.",
        overrides={
            "sb_trigger_deviation": 0.0075,
            "sb_watch_deviation": 0.0040,
            "bs_trigger_deviation": -0.0075,
            "bs_watch_deviation": -0.0040,
            "min_amount_ratio": 1.35,
            "min_trigger_deviation_score": 1.20,
        },
    ),
    ThresholdExperimentSpec(
        experiment_id="more_sensitive",
        label="More sensitive trigger gate",
        description="Lower deviation and turnover thresholds to see how many additional watch/trigger states appear.",
        overrides={
            "sb_trigger_deviation": 0.0045,
            "sb_watch_deviation": 0.0020,
            "bs_trigger_deviation": -0.0045,
            "bs_watch_deviation": -0.0020,
            "min_amount_ratio": 1.00,
            "min_trigger_deviation_score": 0.75,
        },
    ),
    ThresholdExperimentSpec(
        experiment_id="execution_strict",
        label="Execution strict edge gate",
        description="Demand a larger expected reversion and risk buffer so fragile post-cost setups are easier to reject.",
        overrides={
            "expected_reversion_pct": 0.0030,
            "risk_buffer_pct": 0.0015,
            "min_net_edge": 0.0005,
        },
    ),
)


def available_threshold_experiment_ids() -> tuple[str, ...]:
    return tuple(spec.experiment_id for spec in BUILT_IN_THRESHOLD_EXPERIMENTS)


def build_threshold_experiment_report(
    experiment_ids: Iterable[str] | None = None,
    baseline_path: str | Path = DEFAULT_MODEL_AUDIT_BASELINE_PATH,
    base_rules: RulesConfig | None = None,
    target_qty: int = 151400,
    settled_sellable_qty: int = 151400,
    purchasable_qty: int = 15100,
    trade_qty: int = 15100,
    fee_model: FeeModel | None = None,
) -> ThresholdExperimentReport:
    baseline = load_model_audit_baseline(baseline_path)
    selected_specs = _select_specs(experiment_ids)
    starting_rules = base_rules or RulesConfig()
    results = tuple(
        _run_single_experiment(
            spec=spec,
            baseline_path=baseline_path,
            base_rules=starting_rules,
            target_qty=target_qty,
            settled_sellable_qty=settled_sellable_qty,
            purchasable_qty=purchasable_qty,
            trade_qty=trade_qty,
            fee_model=fee_model,
        )
        for spec in selected_specs
    )
    return ThresholdExperimentReport(
        baseline_id=baseline.baseline_id,
        baseline_path=str(baseline_path),
        locked_oos_count=len(baseline.locked_oos_scenarios),
        experiments=results,
        report_note=(
            "Threshold experiments are what-if locked-OOS audit deltas only. "
            "The stored baseline is read but never modified, and no experiment is profitability evidence."
        ),
    )


def rules_with_threshold_overrides(base_rules: RulesConfig, overrides: dict[str, Any]) -> RulesConfig:
    payload = asdict(base_rules)
    unknown = sorted(set(overrides) - set(payload))
    if unknown:
        raise ValueError(f"unknown RulesConfig override field(s): {', '.join(unknown)}")
    payload.update(overrides)
    return RulesConfig(**payload)


def _run_single_experiment(
    spec: ThresholdExperimentSpec,
    baseline_path: str | Path,
    base_rules: RulesConfig,
    target_qty: int,
    settled_sellable_qty: int,
    purchasable_qty: int,
    trade_qty: int,
    fee_model: FeeModel | None,
) -> ThresholdExperimentResult:
    candidate_rules = rules_with_threshold_overrides(base_rules, spec.overrides)
    audit = build_model_change_audit_report(
        baseline_path=baseline_path,
        rules=candidate_rules,
        target_qty=target_qty,
        settled_sellable_qty=settled_sellable_qty,
        purchasable_qty=purchasable_qty,
        trade_qty=trade_qty,
        fee_model=fee_model,
    )
    return ThresholdExperimentResult(
        experiment_id=spec.experiment_id,
        label=spec.label,
        description=spec.description,
        audit_status=audit.status,
        threshold_overrides=spec.overrides,
        threshold_changes=audit.threshold_changes,
        metric_changes=audit.metric_changes,
        aggregate_metric_deltas=_aggregate_metric_deltas(audit.metric_changes),
        interpretation_note=(
            "Compare direction and size of deltas before any threshold change is promoted. "
            "More triggers are not automatically better, fewer triggers are not automatically safer, and the baseline file is unchanged."
        ),
    )


def _select_specs(experiment_ids: Iterable[str] | None) -> tuple[ThresholdExperimentSpec, ...]:
    specs_by_id = {spec.experiment_id: spec for spec in BUILT_IN_THRESHOLD_EXPERIMENTS}
    if experiment_ids is None:
        return BUILT_IN_THRESHOLD_EXPERIMENTS
    selected: list[ThresholdExperimentSpec] = []
    for experiment_id in experiment_ids:
        if experiment_id not in specs_by_id:
            allowed = ", ".join(sorted(specs_by_id))
            raise ValueError(f"unknown threshold experiment: {experiment_id}; allowed: {allowed}")
        selected.append(specs_by_id[experiment_id])
    return tuple(selected)


def _aggregate_metric_deltas(changes: tuple[ModelAuditChange, ...]) -> dict[str, float]:
    totals: defaultdict[str, float] = defaultdict(float)
    for change in changes:
        if not isinstance(change.delta, (int, float)):
            continue
        metric_name = str(change.name).split(".")[-1]
        totals[metric_name] += float(change.delta)
    return {key: totals[key] for key in sorted(totals)}