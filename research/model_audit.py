from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

from core.fee_model import FeeModel
from research.dataset_registry import LOCKED_OOS_SCENARIOS, dataset_records_for_scenarios, load_dataset_bars
from research.trigger_engine import ActionType, PositionState, RulesConfig, TriggerEngine


DEFAULT_MODEL_AUDIT_BASELINE_PATH = Path("research") / "baselines" / "locked_oos_audit_baseline_v1.json"
AUDITED_RULE_FIELDS = (
    "start_time",
    "latest_open_time",
    "force_restore_time",
    "close_time",
    "price_limit_pct",
    "sb_trigger_deviation",
    "sb_watch_deviation",
    "bs_trigger_deviation",
    "bs_watch_deviation",
    "min_amount_ratio",
    "expected_reversion_pct",
    "risk_buffer_pct",
    "min_net_edge",
    "min_trigger_deviation_score",
    "trend_day_return_pct",
    "trend_recent_return_pct",
    "near_limit_buffer_pct",
    "max_wait_minutes",
)


@dataclass(frozen=True)
class ModelAuditBaseline:
    baseline_id: str
    locked_oos_scenarios: tuple[str, ...]
    trigger_thresholds: dict[str, Any]
    evaluation_metrics: dict[str, dict[str, Any]]
    note: str

    def as_dict(self) -> dict[str, Any]:
        return {
            "baseline_id": self.baseline_id,
            "locked_oos_scenarios": list(self.locked_oos_scenarios),
            "trigger_thresholds": self.trigger_thresholds,
            "evaluation_metrics": self.evaluation_metrics,
            "note": self.note,
        }

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> "ModelAuditBaseline":
        return cls(
            baseline_id=str(payload["baseline_id"]),
            locked_oos_scenarios=tuple(payload["locked_oos_scenarios"]),
            trigger_thresholds=dict(payload["trigger_thresholds"]),
            evaluation_metrics={key: dict(value) for key, value in payload["evaluation_metrics"].items()},
            note=str(payload.get("note") or ""),
        )


@dataclass(frozen=True)
class ModelAuditChange:
    category: str
    name: str
    baseline: Any
    current: Any
    delta: Any
    status: str

    def as_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class ModelChangeAuditReport:
    status: str
    summary: str
    baseline_id: str
    locked_oos_count: int
    threshold_changes: tuple[ModelAuditChange, ...]
    metric_changes: tuple[ModelAuditChange, ...]
    current_thresholds: dict[str, Any]
    current_metrics: dict[str, dict[str, Any]]
    review_guidance: str
    report_note: str

    def as_dict(self) -> dict[str, Any]:
        return {
            "status": self.status,
            "summary": self.summary,
            "baseline_id": self.baseline_id,
            "locked_oos_count": self.locked_oos_count,
            "threshold_changes": [change.as_dict() for change in self.threshold_changes],
            "metric_changes": [change.as_dict() for change in self.metric_changes],
            "current_thresholds": self.current_thresholds,
            "current_metrics": self.current_metrics,
            "review_guidance": self.review_guidance,
            "report_note": self.report_note,
        }


def build_model_audit_baseline(
    baseline_id: str = "locked_oos_audit_baseline_v1",
    rules: RulesConfig | None = None,
    target_qty: int = 151400,
    settled_sellable_qty: int = 151400,
    purchasable_qty: int = 15100,
    trade_qty: int = 15100,
    fee_model: FeeModel | None = None,
) -> ModelAuditBaseline:
    rules = rules or RulesConfig()
    return ModelAuditBaseline(
        baseline_id=baseline_id,
        locked_oos_scenarios=tuple(LOCKED_OOS_SCENARIOS),
        trigger_thresholds=trigger_threshold_snapshot(rules),
        evaluation_metrics=locked_oos_metric_snapshot(
            rules=rules,
            target_qty=target_qty,
            settled_sellable_qty=settled_sellable_qty,
            purchasable_qty=purchasable_qty,
            trade_qty=trade_qty,
            fee_model=fee_model,
        ),
        note=(
            "Initial locked-OOS audit baseline. It is used to detect trigger-threshold or signal-metric drift; "
            "it is not profitability evidence."
        ),
    )


def load_model_audit_baseline(path: str | Path = DEFAULT_MODEL_AUDIT_BASELINE_PATH) -> ModelAuditBaseline:
    baseline_path = Path(path)
    try:
        payload = json.loads(baseline_path.read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        raise ValueError(f"model audit baseline is missing: {baseline_path}") from exc
    except json.JSONDecodeError as exc:
        raise ValueError(f"invalid model audit baseline JSON: {baseline_path}") from exc
    if not isinstance(payload, dict):
        raise ValueError(f"model audit baseline must be a JSON object: {baseline_path}")
    return ModelAuditBaseline.from_dict(payload)


def save_model_audit_baseline(
    baseline: ModelAuditBaseline,
    path: str | Path = DEFAULT_MODEL_AUDIT_BASELINE_PATH,
) -> Path:
    baseline_path = Path(path)
    baseline_path.parent.mkdir(parents=True, exist_ok=True)
    baseline_path.write_text(json.dumps(baseline.as_dict(), ensure_ascii=False, indent=2, sort_keys=True), encoding="utf-8")
    return baseline_path


def build_model_change_audit_report(
    baseline_path: str | Path = DEFAULT_MODEL_AUDIT_BASELINE_PATH,
    rules: RulesConfig | None = None,
    target_qty: int = 151400,
    settled_sellable_qty: int = 151400,
    purchasable_qty: int = 15100,
    trade_qty: int = 15100,
    fee_model: FeeModel | None = None,
) -> ModelChangeAuditReport:
    baseline = load_model_audit_baseline(baseline_path)
    rules = rules or RulesConfig()
    current_thresholds = trigger_threshold_snapshot(rules)
    current_metrics = locked_oos_metric_snapshot(
        rules=rules,
        target_qty=target_qty,
        settled_sellable_qty=settled_sellable_qty,
        purchasable_qty=purchasable_qty,
        trade_qty=trade_qty,
        fee_model=fee_model,
    )
    threshold_changes = _compare_flat_dicts("threshold", baseline.trigger_thresholds, current_thresholds)
    metric_changes = _compare_metric_snapshots(baseline.evaluation_metrics, current_metrics)
    scenario_set_changed = set(baseline.locked_oos_scenarios) != set(LOCKED_OOS_SCENARIOS)
    status = "REVIEW" if threshold_changes or metric_changes or scenario_set_changed else "OK"
    summary = _summary(status, threshold_changes, metric_changes, scenario_set_changed)
    return ModelChangeAuditReport(
        status=status,
        summary=summary,
        baseline_id=baseline.baseline_id,
        locked_oos_count=len(LOCKED_OOS_SCENARIOS),
        threshold_changes=tuple(threshold_changes),
        metric_changes=tuple(metric_changes),
        current_thresholds=current_thresholds,
        current_metrics=current_metrics,
        review_guidance=_review_guidance(status, threshold_changes, metric_changes, scenario_set_changed),
        report_note=(
            "Model-change audit compares current trigger thresholds and locked-OOS signal metrics against a stored baseline. "
            "Deltas are review prompts only; no profitability claim, realized PnL, or production validity is implied."
        ),
    )


def trigger_threshold_snapshot(rules: RulesConfig) -> dict[str, Any]:
    payload = asdict(rules)
    return {field: payload[field] for field in AUDITED_RULE_FIELDS}


def locked_oos_metric_snapshot(
    rules: RulesConfig,
    target_qty: int,
    settled_sellable_qty: int,
    purchasable_qty: int,
    trade_qty: int,
    fee_model: FeeModel | None = None,
) -> dict[str, dict[str, Any]]:
    fee_model = fee_model or FeeModel()
    records = dataset_records_for_scenarios(LOCKED_OOS_SCENARIOS)
    audit_rules = _rules_with_position_sizing(rules, target_qty, trade_qty)
    snapshot: dict[str, dict[str, Any]] = {}
    for record in records:
        bars = load_dataset_bars(record)
        trigger = _trigger_signal_metrics(
            symbol=record.scenario,
            bars=bars,
            rules=audit_rules,
            target_qty=target_qty,
            settled_sellable_qty=settled_sellable_qty,
            purchasable_qty=purchasable_qty,
            fee_model=fee_model,
        )
        trigger["bar_count"] = len(bars)
        trigger["dataset_id"] = record.dataset_id
        snapshot[record.scenario] = trigger
    return snapshot


def _trigger_signal_metrics(
    symbol: str,
    bars,
    rules: RulesConfig,
    target_qty: int,
    settled_sellable_qty: int,
    purchasable_qty: int,
    fee_model: FeeModel,
) -> dict[str, Any]:
    engine = TriggerEngine(rules=rules, fee_model=fee_model)
    position = PositionState(
        target_qty=target_qty,
        current_total_qty=target_qty,
        settled_sellable_qty=settled_sellable_qty,
        purchasable_qty=purchasable_qty,
    )
    intents = [engine.evaluate(symbol, bars[: index + 1], position) for index in range(len(bars))]
    latest = intents[-1]
    return {
        "latest_action": latest.action_type.value,
        "trigger_count": sum(1 for intent in intents if intent.action_type in _TRIGGER_ACTIONS),
        "watch_count": sum(1 for intent in intents if intent.action_type in _WATCH_ACTIONS),
        "no_trade_count": sum(1 for intent in intents if intent.action_type is ActionType.NO_TRADE),
        "latest_blocker_count": len(latest.blockers),
        "latest_warning_count": len(latest.warnings),
    }


def _rules_with_position_sizing(rules: RulesConfig, target_qty: int, trade_qty: int) -> RulesConfig:
    payload = asdict(rules)
    payload["max_t_ratio"] = trade_qty / target_qty if target_qty else 0.0
    payload["max_single_trade_qty"] = trade_qty
    return RulesConfig(**payload)


def _compare_flat_dicts(category: str, baseline: dict[str, Any], current: dict[str, Any]) -> list[ModelAuditChange]:
    changes: list[ModelAuditChange] = []
    for key in sorted(set(baseline) | set(current)):
        before = baseline.get(key)
        after = current.get(key)
        if before != after:
            changes.append(ModelAuditChange(category, key, before, after, _delta(before, after), "CHANGED"))
    return changes


def _compare_metric_snapshots(
    baseline: dict[str, dict[str, Any]],
    current: dict[str, dict[str, Any]],
) -> list[ModelAuditChange]:
    changes: list[ModelAuditChange] = []
    for scenario in sorted(set(baseline) | set(current)):
        before_metrics = baseline.get(scenario, {})
        after_metrics = current.get(scenario, {})
        for metric in sorted(set(before_metrics) | set(after_metrics)):
            before = before_metrics.get(metric)
            after = after_metrics.get(metric)
            if before != after:
                changes.append(ModelAuditChange("locked_oos_metric", f"{scenario}.{metric}", before, after, _delta(before, after), "CHANGED"))
    return changes


def _delta(before: Any, after: Any) -> Any:
    if isinstance(before, (int, float)) and isinstance(after, (int, float)):
        return round(after - before, 10)
    if before is None:
        return "added"
    if after is None:
        return "removed"
    return "changed"


def _summary(
    status: str,
    threshold_changes: list[ModelAuditChange],
    metric_changes: list[ModelAuditChange],
    scenario_set_changed: bool,
) -> str:
    if status == "OK":
        return "Current trigger thresholds and locked-OOS signal metrics match the stored baseline."
    parts = []
    if threshold_changes:
        parts.append(f"{len(threshold_changes)} threshold change(s)")
    if metric_changes:
        parts.append(f"{len(metric_changes)} locked-OOS metric change(s)")
    if scenario_set_changed:
        parts.append("locked-OOS scenario set changed")
    return "Review required: " + "; ".join(parts) + "."


def _review_guidance(
    status: str,
    threshold_changes: list[ModelAuditChange],
    metric_changes: list[ModelAuditChange],
    scenario_set_changed: bool,
) -> str:
    if status == "OK":
        return "Current thresholds and locked-OOS signal metrics match the stored baseline; no baseline update is needed."
    parts = []
    if threshold_changes:
        parts.append(f"{len(threshold_changes)} threshold delta(s)")
    if metric_changes:
        parts.append(f"{len(metric_changes)} locked-OOS metric delta(s)")
    if scenario_set_changed:
        parts.append("locked-OOS scenario set changed")
    detail = f" ({', '.join(parts)})" if parts else ""
    return (
        f"Current model output differs from the stored locked baseline{detail}. "
        "Treat this as a human review gate, not as evidence of improvement; update the baseline only through the explicit review-token workflow."
    )


_TRIGGER_ACTIONS = {
    ActionType.TRIGGER_SELL_TO_BUY,
    ActionType.TRIGGER_BUY_TO_SELL,
}

_WATCH_ACTIONS = {
    ActionType.WATCH_SELL_TO_BUY,
    ActionType.WATCH_BUY_TO_SELL,
}



MODEL_AUDIT_BASELINE_REVIEW_TOKEN = "APPROVE_LOCKED_OOS_BASELINE_UPDATE"


@dataclass(frozen=True)
class ModelAuditBaselineUpdatePreview:
    status: str
    baseline_path: str
    baseline_id: str
    locked_oos_count: int
    threshold_change_count: int
    metric_change_count: int
    audit_summary: str
    required_review_token: str
    can_update: bool
    report_note: str

    def as_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class ModelAuditBaselineUpdateResult:
    status: str
    baseline_path: str
    baseline_id: str
    threshold_change_count: int
    metric_change_count: int
    audit_summary: str
    reviewer_note: str
    report_note: str

    def as_dict(self) -> dict[str, Any]:
        return asdict(self)


def build_model_audit_baseline_update_preview(
    baseline_path: str | Path = DEFAULT_MODEL_AUDIT_BASELINE_PATH,
    rules: RulesConfig | None = None,
    target_qty: int = 151400,
    settled_sellable_qty: int = 151400,
    purchasable_qty: int = 15100,
    trade_qty: int = 15100,
    fee_model: FeeModel | None = None,
) -> ModelAuditBaselineUpdatePreview:
    report = build_model_change_audit_report(
        baseline_path=baseline_path,
        rules=rules,
        target_qty=target_qty,
        settled_sellable_qty=settled_sellable_qty,
        purchasable_qty=purchasable_qty,
        trade_qty=trade_qty,
        fee_model=fee_model,
    )
    status = "REVIEW_REQUIRED" if report.status == "REVIEW" else "NO_UPDATE_NEEDED"
    return ModelAuditBaselineUpdatePreview(
        status=status,
        baseline_path=str(baseline_path),
        baseline_id=report.baseline_id,
        locked_oos_count=report.locked_oos_count,
        threshold_change_count=len(report.threshold_changes),
        metric_change_count=len(report.metric_changes),
        audit_summary=report.summary,
        required_review_token=MODEL_AUDIT_BASELINE_REVIEW_TOKEN,
        can_update=False,
        report_note=(
            "Baseline update preview only. A write requires audit deltas plus the exact review token; "
            "promotion still does not imply profitability, realized PnL, or production validity."
        ),
    )


def update_model_audit_baseline_after_review(
    baseline_path: str | Path = DEFAULT_MODEL_AUDIT_BASELINE_PATH,
    review_token: str | None = None,
    reviewer_note: str = "",
    rules: RulesConfig | None = None,
    target_qty: int = 151400,
    settled_sellable_qty: int = 151400,
    purchasable_qty: int = 15100,
    trade_qty: int = 15100,
    fee_model: FeeModel | None = None,
) -> ModelAuditBaselineUpdateResult:
    existing = load_model_audit_baseline(baseline_path)
    preview = build_model_audit_baseline_update_preview(
        baseline_path=baseline_path,
        rules=rules,
        target_qty=target_qty,
        settled_sellable_qty=settled_sellable_qty,
        purchasable_qty=purchasable_qty,
        trade_qty=trade_qty,
        fee_model=fee_model,
    )
    if preview.status != "REVIEW_REQUIRED":
        raise ValueError("baseline update requires audit deltas; current audit matches the stored baseline")
    if review_token != MODEL_AUDIT_BASELINE_REVIEW_TOKEN:
        raise ValueError(
            "baseline update requires explicit review token "
            f"{MODEL_AUDIT_BASELINE_REVIEW_TOKEN!r} after inspecting audit deltas"
        )
    new_baseline = build_model_audit_baseline(
        baseline_id=existing.baseline_id,
        rules=rules,
        target_qty=target_qty,
        settled_sellable_qty=settled_sellable_qty,
        purchasable_qty=purchasable_qty,
        trade_qty=trade_qty,
        fee_model=fee_model,
    )
    note_parts = [
        "Updated after explicit locked-OOS audit review.",
        "This baseline records reviewed thresholds and signal metrics only; it is not profitability evidence.",
    ]
    if reviewer_note.strip():
        note_parts.append(f"Reviewer note: {reviewer_note.strip()}")
    reviewed_baseline = ModelAuditBaseline(
        baseline_id=new_baseline.baseline_id,
        locked_oos_scenarios=new_baseline.locked_oos_scenarios,
        trigger_thresholds=new_baseline.trigger_thresholds,
        evaluation_metrics=new_baseline.evaluation_metrics,
        note=" ".join(note_parts),
    )
    saved_path = save_model_audit_baseline(reviewed_baseline, baseline_path)
    return ModelAuditBaselineUpdateResult(
        status="UPDATED",
        baseline_path=str(saved_path),
        baseline_id=reviewed_baseline.baseline_id,
        threshold_change_count=preview.threshold_change_count,
        metric_change_count=preview.metric_change_count,
        audit_summary=preview.audit_summary,
        reviewer_note=reviewer_note,
        report_note=(
            "Baseline updated only after explicit review token. This is a governance action, "
            "not evidence of profitability or production trading validity."
        ),
    )
