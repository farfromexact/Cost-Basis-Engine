from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class SourceDisclosureItem:
    topic: str
    status: str
    detail: str
    operator_action: str

    def as_dict(self) -> dict[str, str]:
        return {
            "topic": self.topic,
            "status": self.status,
            "detail": self.detail,
            "operator_action": self.operator_action,
        }


@dataclass(frozen=True)
class DataSourceDisclosure:
    source_name: str
    source_grade: str
    broker_confirmed: bool
    delay_status: str
    licensing_status: str
    items: tuple[SourceDisclosureItem, ...]

    def summary(self) -> str:
        broker_text = "broker-confirmed" if self.broker_confirmed else "not broker-confirmed"
        return (
            f"{self.source_name} is a {self.source_grade}; it is {broker_text}. "
            "Treat dashboard guidance as research decision support until price, availability, holdings, "
            "and order status are checked in the broker system."
        )

    def as_table_rows(self) -> list[dict[str, str]]:
        return [item.as_dict() for item in self.items]


def build_data_source_disclosure(market_source: str) -> DataSourceDisclosure:
    if market_source.startswith("Korea"):
        return DataSourceDisclosure(
            source_name="Yahoo Finance public chart feed",
            source_grade="research/prototype feed",
            broker_confirmed=False,
            delay_status="unverified delay and possible revisions",
            licensing_status="public-finance terms; operational redistribution not verified",
            items=(
                SourceDisclosureItem(
                    topic="Delay",
                    status="WARN",
                    detail="Minute bars may be delayed, corrected, or missing the current forming bar; they are not exchange-direct broker data.",
                    operator_action="Confirm the latest bid/ask and tradable price in the broker before acting.",
                ),
                SourceDisclosureItem(
                    topic="Licensing",
                    status="WARN",
                    detail="Yahoo Finance data is suitable here only as a research/prototype input; trading-desk or redistribution rights are not established.",
                    operator_action="Use a licensed market-data source before relying on this app in a professional workflow.",
                ),
                SourceDisclosureItem(
                    topic="Turnover amount",
                    status="WARN",
                    detail="Korea/Yahoo turnover is approximated from close * volume, so amount-ratio liquidity checks are lower confidence.",
                    operator_action="Downgrade signal confidence when liquidity confirmation depends on turnover amount.",
                ),
                SourceDisclosureItem(
                    topic="Broker confirmation",
                    status="REQUIRED",
                    detail="The app does not verify account holdings, order acceptance, partial fills, cancels, or settlement state.",
                    operator_action="Use broker-confirmed holdings and executions as the source of truth.",
                ),
            ),
        )
    return DataSourceDisclosure(
        source_name="Eastmoney public quote endpoint",
        source_grade="research feed",
        broker_confirmed=False,
        delay_status="unverified delay and possible vendor filtering",
        licensing_status="public website/API terms; professional use not verified",
        items=(
            SourceDisclosureItem(
                topic="Delay",
                status="WARN",
                detail="Minute bars are fetched from a public quote endpoint, not a broker or exchange-certified live feed.",
                operator_action="Confirm the latest executable price in the broker before placing or modifying an order.",
            ),
            SourceDisclosureItem(
                topic="Licensing",
                status="WARN",
                detail="The app has not verified Eastmoney licensing terms for professional trading-desk use or redistribution.",
                operator_action="Treat this feed as personal research unless a licensed data agreement is in place.",
            ),
            SourceDisclosureItem(
                topic="A-share sellability",
                status="REQUIRED",
                detail="The feed cannot prove which shares are settled and sellable; today-bought shares remain locked under T+1 constraints.",
                operator_action="Check broker-confirmed sellable quantity before any sell-first SB action.",
            ),
            SourceDisclosureItem(
                topic="Broker confirmation",
                status="REQUIRED",
                detail="The app does not verify holdings, cash, order acceptance, partial fills, cancels, or final execution price.",
                operator_action="Use broker-confirmed market data and fills as the source of truth.",
            ),
        ),
    )
