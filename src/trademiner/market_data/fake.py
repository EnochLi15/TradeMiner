from __future__ import annotations

from copy import deepcopy

from trademiner.market_data.models import DailyBar, Instrument


class FakeMarketDataProvider:
    name = "fake"

    def __init__(
        self,
        instruments: list[Instrument],
        daily_bars: dict[str, list[DailyBar]],
        fail_on_fetch: bool = False,
    ):
        self._instruments = list(instruments)
        self._daily_bars = deepcopy(daily_bars)
        self.fail_on_fetch = fail_on_fetch
        self.instrument_requests: list[list[str]] = []
        self.daily_bar_requests: list[dict[str, str]] = []

    def fetch_instruments(self, instrument_types: list[str]) -> list[Instrument]:
        if self.fail_on_fetch:
            raise RuntimeError("fake provider failure")
        self.instrument_requests.append(list(instrument_types))
        requested = set(instrument_types)
        return [
            instrument
            for instrument in self._instruments
            if instrument.instrument_type in requested
        ]

    def fetch_daily_bars(
        self,
        instrument: Instrument,
        start_date: str,
        end_date: str,
        adjustment: str,
    ) -> list[DailyBar]:
        if self.fail_on_fetch:
            raise RuntimeError("fake provider failure")
        self.daily_bar_requests.append(
            {
                "instrument_id": instrument.instrument_id,
                "start_date": start_date,
                "end_date": end_date,
                "adjustment": adjustment,
            }
        )
        return [
            bar
            for bar in self._daily_bars.get(instrument.instrument_id, [])
            if start_date <= bar.trade_date <= end_date
            and bar.adjustment == adjustment
        ]

    def replace_daily_bars(
        self,
        instrument_id: str,
        daily_bars: list[DailyBar],
    ) -> None:
        self._daily_bars[instrument_id] = list(daily_bars)
