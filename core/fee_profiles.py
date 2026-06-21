from __future__ import annotations

from dataclasses import dataclass

from core.fee_model import FeeConfig, FeeModel


DEFAULT_A_SHARE_FEE_PROFILE_ID = "a_share_conservative"
DEFAULT_KOREA_FEE_PROFILE_ID = "korea_prototype_conservative"
DEFAULT_US_FEE_PROFILE_ID = "us_prototype_conservative"
ZERO_FEE_PROFILE_ID = "zero_fee_research"
CUSTOM_FEE_PROFILE_ID = "custom_manual"


@dataclass(frozen=True)
class FeeProfile:
    profile_id: str
    label: str
    description: str
    config: FeeConfig
    research_only: bool = False

    def as_dict(self) -> dict:
        return {
            "profile_id": self.profile_id,
            "label": self.label,
            "description": self.description,
            "config": self.config.__dict__.copy(),
            "research_only": self.research_only,
        }


ZERO_FEE_CONFIG = FeeConfig(
    market="GENERIC",
    buy_commission_rate=0.0,
    sell_commission_rate=0.0,
    min_commission=0.0,
    stamp_tax_rate=0.0,
    transfer_fee_rate=0.0,
    other_fee_rate=0.0,
    buy_slippage_rate=0.0,
    sell_slippage_rate=0.0,
    a_share_handling_fee_bps=0.0,
    a_share_management_fee_bps=0.0,
    a_share_transfer_fee_bps=0.0,
    a_share_stamp_duty_sell_bps=0.0,
    a_share_broker_commission_bps=0.0,
    a_share_min_commission_cny=0.0,
    us_sec_fee_per_million=0.0,
    us_finra_taf_per_share=0.0,
    us_finra_taf_cap_per_trade=0.0,
    us_broker_commission_per_share=0.0,
    us_broker_min_commission=0.0,
    us_platform_fee_per_order=0.0,
)

FEE_PROFILES: dict[str, FeeProfile] = {
    DEFAULT_A_SHARE_FEE_PROFILE_ID: FeeProfile(
        profile_id=DEFAULT_A_SHARE_FEE_PROFILE_ID,
        label="A-share conservative default",
        description="Default costed A-share profile using official fees plus configurable broker commission; confirm broker-specific rates before live use.",
        config=FeeConfig(
            market="A_SHARE",
            buy_slippage_rate=0.0001,
            sell_slippage_rate=0.0001,
            a_share_broker_commission_bps=1.0,
            a_share_min_commission_cny=5.0,
        ),
    ),
    "a_share_low_cost": FeeProfile(
        profile_id="a_share_low_cost",
        label="A-share low-cost broker",
        description="Lower commission/slippage preset for sensitivity checks; still requires broker confirmation.",
        config=FeeConfig(
            market="A_SHARE",
            a_share_broker_commission_bps=0.8,
            a_share_min_commission_cny=5.0,
            buy_slippage_rate=0.00005,
            sell_slippage_rate=0.00005,
        ),
    ),
    DEFAULT_KOREA_FEE_PROFILE_ID: FeeProfile(
        profile_id=DEFAULT_KOREA_FEE_PROFILE_ID,
        label="Korea conservative prototype",
        description="Prototype Korea stock cost profile; verify current broker fees/taxes before relying on it.",
        config=FeeConfig(
            market="GENERIC",
            buy_commission_rate=0.00015,
            sell_commission_rate=0.00015,
            min_commission=0.0,
            stamp_tax_rate=0.0020,
            transfer_fee_rate=0.0,
            other_fee_rate=0.0,
            buy_slippage_rate=0.00010,
            sell_slippage_rate=0.00010,
        ),
    ),
    DEFAULT_US_FEE_PROFILE_ID: FeeProfile(
        profile_id=DEFAULT_US_FEE_PROFILE_ID,
        label="US stock conservative prototype",
        description="Prototype US stock cost profile; verify broker commissions, SEC/FINRA fees, FX, and settlement rules before live use.",
        config=FeeConfig(
            market="US_EQUITY",
            buy_commission_rate=0.0,
            sell_commission_rate=0.0,
            min_commission=0.0,
            stamp_tax_rate=0.0,
            transfer_fee_rate=0.0,
            other_fee_rate=0.0,
            buy_slippage_rate=0.00010,
            sell_slippage_rate=0.00010,
            us_broker_commission_per_share=0.0,
            us_broker_min_commission=0.0,
            us_platform_fee_per_order=0.0,
        ),
    ),
    ZERO_FEE_PROFILE_ID: FeeProfile(
        profile_id=ZERO_FEE_PROFILE_ID,
        label="Zero-fee research only",
        description="Zero fees and zero slippage; use only for mechanics/sensitivity checks, not live guidance.",
        config=ZERO_FEE_CONFIG,
        research_only=True,
    ),
}


def default_fee_profile_id(market_source: str | None = None) -> str:
    source = str(market_source or "")
    if source.startswith("Korea"):
        return DEFAULT_KOREA_FEE_PROFILE_ID
    if source.startswith("US"):
        return DEFAULT_US_FEE_PROFILE_ID
    return DEFAULT_A_SHARE_FEE_PROFILE_ID


def fee_profile_choices(market_source: str | None = None) -> list[str]:
    preferred = default_fee_profile_id(market_source)
    ordered = [preferred]
    for profile_id in (DEFAULT_A_SHARE_FEE_PROFILE_ID, "a_share_low_cost", DEFAULT_KOREA_FEE_PROFILE_ID, DEFAULT_US_FEE_PROFILE_ID, ZERO_FEE_PROFILE_ID, CUSTOM_FEE_PROFILE_ID):
        if profile_id not in ordered:
            ordered.append(profile_id)
    return ordered


def fee_profile_label(profile_id: str) -> str:
    if profile_id == CUSTOM_FEE_PROFILE_ID:
        return "Custom manual rates"
    return FEE_PROFILES[normalize_fee_profile_id(profile_id)].label


def fee_profile_description(profile_id: str) -> str:
    if profile_id == CUSTOM_FEE_PROFILE_ID:
        return "Manual user-entered rates for this run; verify against broker statement."
    return FEE_PROFILES[normalize_fee_profile_id(profile_id)].description


def normalize_fee_profile_id(profile_id: str | None, market_source: str | None = None) -> str:
    if profile_id in (None, ""):
        return default_fee_profile_id(market_source)
    text = str(profile_id)
    aliases = {
        "zero": ZERO_FEE_PROFILE_ID,
        "zero_fee": ZERO_FEE_PROFILE_ID,
        "ignore_fees": ZERO_FEE_PROFILE_ID,
        "custom": CUSTOM_FEE_PROFILE_ID,
    }
    text = aliases.get(text, text)
    if text == CUSTOM_FEE_PROFILE_ID:
        return text
    if text not in FEE_PROFILES:
        raise ValueError(f"Unknown fee profile: {profile_id}")
    return text


def fee_config_from_profile(
    profile_id: str | None,
    custom_config: FeeConfig | None = None,
    market_source: str | None = None,
) -> FeeConfig:
    normalized = normalize_fee_profile_id(profile_id, market_source)
    if normalized == CUSTOM_FEE_PROFILE_ID:
        return custom_config or FeeConfig()
    return FEE_PROFILES[normalized].config


def fee_model_from_profile(
    profile_id: str | None,
    custom_config: FeeConfig | None = None,
    market_source: str | None = None,
) -> FeeModel:
    return FeeModel(fee_config_from_profile(profile_id, custom_config=custom_config, market_source=market_source))


def is_zero_fee_profile(profile_id: str | None) -> bool:
    return normalize_fee_profile_id(profile_id) == ZERO_FEE_PROFILE_ID
