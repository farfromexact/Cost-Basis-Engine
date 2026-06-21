from __future__ import annotations

from dataclasses import dataclass

from core.models import Side


@dataclass(frozen=True)
class FeeConfig:
    buy_commission_rate: float = 0.00025
    sell_commission_rate: float = 0.00025
    min_commission: float = 5.0
    stamp_tax_rate: float = 0.0005
    transfer_fee_rate: float = 0.00001
    other_fee_rate: float = 0.0
    buy_slippage_rate: float = 0.0001
    sell_slippage_rate: float = 0.0001
    market: str = "A_SHARE"
    a_share_handling_fee_bps: float = 0.341
    a_share_management_fee_bps: float = 0.200
    a_share_transfer_fee_bps: float = 0.100
    a_share_stamp_duty_sell_bps: float = 5.000
    a_share_broker_commission_bps: float = 1.0
    a_share_min_commission_cny: float = 5.0
    us_sec_fee_per_million: float = 20.60
    us_finra_taf_per_share: float = 0.000195
    us_finra_taf_cap_per_trade: float = 9.79
    us_broker_commission_per_share: float = 0.0
    us_broker_min_commission: float = 0.0
    us_platform_fee_per_order: float = 0.0


@dataclass(frozen=True)
class FeeBreakdown:
    commission: float
    stamp_tax: float
    transfer_fee: float
    other_fee: float
    slippage: float

    @property
    def total_fees(self) -> float:
        return self.commission + self.stamp_tax + self.transfer_fee + self.other_fee


class FeeModel:
    def __init__(self, config: FeeConfig | None = None) -> None:
        self.config = config or FeeConfig()

    def calculate(self, side: Side, price: float, qty: int) -> FeeBreakdown:
        if price <= 0:
            raise ValueError("price must be positive")
        if qty <= 0:
            raise ValueError("qty must be positive")

        market = _normalize_market(self.config.market)
        if market == "A_SHARE":
            if _uses_legacy_zero_fee_profile(self.config):
                return self._calculate_generic(side, price, qty)
            return self._calculate_a_share(side, price, qty)
        if market == "US_EQUITY":
            return self._calculate_us_equity(side, price, qty)
        return self._calculate_generic(side, price, qty)

    def estimate_buy_cost(self, market: str, price: float, shares: int) -> float:
        return self._cost_for_market(market, Side.BUY, price, shares)

    def estimate_sell_cost(self, market: str, price: float, shares: int) -> float:
        return self._cost_for_market(market, Side.SELL, price, shares)

    def estimate_round_trip_cost(self, market: str, price: float, shares: int, side: str) -> float:
        side_text = str(side or "").upper()
        if side_text not in {"B_TO_S", "S_TO_B"}:
            raise ValueError("side must be B_TO_S or S_TO_B")
        return self.estimate_buy_cost(market, price, shares) + self.estimate_sell_cost(market, price, shares)

    def estimate_break_even_bps(self, market: str, price: float, shares: int, side: str) -> float:
        if price <= 0:
            raise ValueError("price must be positive")
        if shares <= 0:
            raise ValueError("shares must be positive")
        cost = self.estimate_round_trip_cost(market, price, shares, side)
        return cost / (price * shares) * 10000.0

    def _cost_for_market(self, market: str, side: Side, price: float, qty: int) -> float:
        if price <= 0:
            raise ValueError("price must be positive")
        if qty <= 0:
            raise ValueError("shares must be positive")
        normalized = _normalize_market(market)
        if normalized == "A_SHARE":
            if _uses_legacy_zero_fee_profile(self.config):
                return self._calculate_generic(side, price, qty).total_fees
            return self._calculate_a_share(side, price, qty).total_fees
        if normalized == "US_EQUITY":
            return self._calculate_us_equity(side, price, qty).total_fees
        return self._calculate_generic(side, price, qty).total_fees

    def _calculate_generic(self, side: Side, price: float, qty: int) -> FeeBreakdown:
        gross = price * qty
        commission_rate = (
            self.config.buy_commission_rate
            if side is Side.BUY
            else self.config.sell_commission_rate
        )
        commission = max(gross * commission_rate, self.config.min_commission)
        stamp_tax = gross * self.config.stamp_tax_rate if side is Side.SELL else 0.0
        transfer_fee = gross * self.config.transfer_fee_rate
        other_fee = gross * self.config.other_fee_rate
        slippage_rate = (
            self.config.buy_slippage_rate
            if side is Side.BUY
            else self.config.sell_slippage_rate
        )
        slippage = gross * slippage_rate
        return FeeBreakdown(
            commission=commission,
            stamp_tax=stamp_tax,
            transfer_fee=transfer_fee,
            other_fee=other_fee,
            slippage=slippage,
        )

    def _calculate_a_share(self, side: Side, price: float, qty: int) -> FeeBreakdown:
        gross = price * qty
        official_bps = (
            self.config.a_share_handling_fee_bps
            + self.config.a_share_management_fee_bps
            + self.config.a_share_transfer_fee_bps
        )
        commission = max(
            gross * self.config.a_share_broker_commission_bps / 10000.0,
            self.config.a_share_min_commission_cny,
        )
        stamp_tax = gross * self.config.a_share_stamp_duty_sell_bps / 10000.0 if side is Side.SELL else 0.0
        transfer_fee = gross * official_bps / 10000.0
        slippage_rate = (
            self.config.buy_slippage_rate
            if side is Side.BUY
            else self.config.sell_slippage_rate
        )
        return FeeBreakdown(
            commission=commission,
            stamp_tax=stamp_tax,
            transfer_fee=transfer_fee,
            other_fee=0.0,
            slippage=gross * slippage_rate,
        )

    def _calculate_us_equity(self, side: Side, price: float, qty: int) -> FeeBreakdown:
        gross = price * qty
        broker_commission = max(
            qty * self.config.us_broker_commission_per_share,
            self.config.us_broker_min_commission,
        )
        platform_fee = self.config.us_platform_fee_per_order
        sec_fee = gross * self.config.us_sec_fee_per_million / 1_000_000.0 if side is Side.SELL else 0.0
        taf = min(qty * self.config.us_finra_taf_per_share, self.config.us_finra_taf_cap_per_trade) if side is Side.SELL else 0.0
        slippage_rate = (
            self.config.buy_slippage_rate
            if side is Side.BUY
            else self.config.sell_slippage_rate
        )
        return FeeBreakdown(
            commission=broker_commission,
            stamp_tax=0.0,
            transfer_fee=0.0,
            other_fee=platform_fee + sec_fee + taf,
            slippage=gross * slippage_rate,
        )


def _normalize_market(market: str | None) -> str:
    text = str(market or "GENERIC").upper()
    aliases = {
        "A-SHARE": "A_SHARE",
        "ASHARE": "A_SHARE",
        "CN": "A_SHARE",
        "CHINA": "A_SHARE",
        "US": "US_EQUITY",
        "US_STOCK": "US_EQUITY",
        "US_EQUITIES": "US_EQUITY",
        "US / YAHOO FINANCE": "US_EQUITY",
        "KOREA": "GENERIC",
        "GENERIC": "GENERIC",
    }
    return aliases.get(text, text)


def _uses_legacy_zero_fee_profile(config: FeeConfig) -> bool:
    return (
        _normalize_market(config.market) == "A_SHARE"
        and config.buy_commission_rate == 0.0
        and config.sell_commission_rate == 0.0
        and config.min_commission == 0.0
        and config.stamp_tax_rate == 0.0
        and config.transfer_fee_rate == 0.0
        and config.other_fee_rate == 0.0
        and config.buy_slippage_rate == 0.0
        and config.sell_slippage_rate == 0.0
    )
