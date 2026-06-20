from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any

from research.trigger_engine import RulesConfig


DEFAULT_RISK_LIMIT_PRESET_ID = "balanced"


@dataclass(frozen=True)
class RiskLimitPreset:
    preset_id: str
    label: str
    description: str
    max_daily_turnover_ratio: float
    max_open_pair_minutes: int
    max_same_day_capital_at_risk_ratio: float

    def as_dict(self) -> dict[str, Any]:
        return asdict(self)


RISK_LIMIT_PRESETS: dict[str, RiskLimitPreset] = {
    "defensive": RiskLimitPreset(
        preset_id="defensive",
        label="Defensive",
        description="Use when liquidity, volatility, or operator attention is uncertain; caps round-trip turnover and same-day risk tightly.",
        max_daily_turnover_ratio=0.10,
        max_open_pair_minutes=25,
        max_same_day_capital_at_risk_ratio=0.05,
    ),
    "balanced": RiskLimitPreset(
        preset_id="balanced",
        label="Balanced",
        description="Default professional guardrail: one round-trip pair can use up to 10% of target inventory and must be managed intraday.",
        max_daily_turnover_ratio=0.20,
        max_open_pair_minutes=45,
        max_same_day_capital_at_risk_ratio=0.10,
    ),
    "active": RiskLimitPreset(
        preset_id="active",
        label="Active",
        description="Higher-capacity review mode for liquid names; still caps same-day risk and open-pair waiting time explicitly.",
        max_daily_turnover_ratio=0.30,
        max_open_pair_minutes=60,
        max_same_day_capital_at_risk_ratio=0.15,
    ),
}


def risk_limit_preset_ids() -> tuple[str, ...]:
    return tuple(RISK_LIMIT_PRESETS)


def risk_limit_preset(preset_id: str | None) -> RiskLimitPreset:
    key = preset_id or DEFAULT_RISK_LIMIT_PRESET_ID
    try:
        return RISK_LIMIT_PRESETS[key]
    except KeyError as exc:
        allowed = ", ".join(risk_limit_preset_ids())
        raise ValueError(f"unknown risk limit preset: {preset_id}; allowed: {allowed}") from exc


def risk_limit_label(preset_id: str | None) -> str:
    preset = risk_limit_preset(preset_id)
    return preset.label


def risk_limit_description(preset_id: str | None) -> str:
    preset = risk_limit_preset(preset_id)
    return preset.description


def rules_with_risk_limit_preset(rules: RulesConfig, preset_id: str | None) -> RulesConfig:
    preset = risk_limit_preset(preset_id)
    payload = asdict(rules)
    payload["risk_preset_id"] = preset.preset_id
    payload["max_daily_turnover_ratio"] = preset.max_daily_turnover_ratio
    payload["max_wait_minutes"] = preset.max_open_pair_minutes
    payload["max_same_day_capital_at_risk_ratio"] = preset.max_same_day_capital_at_risk_ratio
    return RulesConfig(**payload)