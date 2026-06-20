from core.fee_profiles import (
    CUSTOM_FEE_PROFILE_ID,
    DEFAULT_A_SHARE_FEE_PROFILE_ID,
    DEFAULT_KOREA_FEE_PROFILE_ID,
    ZERO_FEE_PROFILE_ID,
    default_fee_profile_id,
    fee_config_from_profile,
    fee_profile_choices,
    fee_profile_label,
    normalize_fee_profile_id,
)
from core.fee_model import FeeConfig


def test_default_fee_profiles_are_costed_not_zero_fee() -> None:
    config = fee_config_from_profile(default_fee_profile_id("A-share / Eastmoney"))

    assert default_fee_profile_id("A-share / Eastmoney") == DEFAULT_A_SHARE_FEE_PROFILE_ID
    assert config.buy_commission_rate > 0
    assert config.sell_commission_rate > 0
    assert config.buy_slippage_rate > 0
    assert config.sell_slippage_rate > 0


def test_korea_default_uses_non_zero_prototype_profile() -> None:
    profile_id = default_fee_profile_id("Korea / Yahoo Finance")
    config = fee_config_from_profile(profile_id)

    assert profile_id == DEFAULT_KOREA_FEE_PROFILE_ID
    assert config.sell_commission_rate > 0
    assert config.stamp_tax_rate > 0


def test_zero_fee_profile_is_explicit_and_all_zero() -> None:
    config = fee_config_from_profile(ZERO_FEE_PROFILE_ID)

    assert config == FeeConfig(
        buy_commission_rate=0.0,
        sell_commission_rate=0.0,
        min_commission=0.0,
        stamp_tax_rate=0.0,
        transfer_fee_rate=0.0,
        other_fee_rate=0.0,
        buy_slippage_rate=0.0,
        sell_slippage_rate=0.0,
    )


def test_custom_profile_uses_supplied_manual_config() -> None:
    custom = FeeConfig(buy_commission_rate=0.001, sell_commission_rate=0.002, min_commission=1.0)

    assert fee_config_from_profile(CUSTOM_FEE_PROFILE_ID, custom_config=custom) == custom
    assert "Custom" in fee_profile_label(CUSTOM_FEE_PROFILE_ID)


def test_fee_profile_choices_include_explicit_zero_fee_last() -> None:
    choices = fee_profile_choices("A-share / Eastmoney")

    assert choices[0] == DEFAULT_A_SHARE_FEE_PROFILE_ID
    assert ZERO_FEE_PROFILE_ID in choices
    assert normalize_fee_profile_id("zero") == ZERO_FEE_PROFILE_ID
