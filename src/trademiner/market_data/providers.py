from __future__ import annotations

from typing import Protocol

from trademiner.market_data.models import DailyBar, Instrument


class MarketDataProvider(Protocol):
    name: str

    def fetch_instruments(self, instrument_types: list[str]) -> list[Instrument]:
        """Return Instruments for the requested first-version universe."""

    def fetch_daily_bars(
        self,
        instrument: Instrument,
        start_date: str,
        end_date: str,
        adjustment: str,
    ) -> list[DailyBar]:
        """Return daily adjusted bars for one Instrument within a date range."""


def default_data_providers() -> dict[str, MarketDataProvider]:
    from trademiner.market_data.akshare_provider import AkShareMarketDataProvider

    provider = AkShareMarketDataProvider()
    return {provider.name: provider}
