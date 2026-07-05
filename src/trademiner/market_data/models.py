from __future__ import annotations

from dataclasses import asdict, dataclass


@dataclass(frozen=True)
class Instrument:
    instrument_id: str
    symbol: str
    name: str
    instrument_type: str
    exchange: str | None = None

    def as_response(self) -> dict[str, object]:
        return asdict(self)


@dataclass(frozen=True)
class DailyBar:
    instrument_id: str
    trade_date: str
    adjustment: str
    open: float
    high: float
    low: float
    close: float
    volume: float
    amount: float | None = None

    def as_response(self) -> dict[str, object]:
        return asdict(self)


@dataclass(frozen=True)
class SyncCursor:
    provider: str
    data_type: str
    adjustment: str
    scope: str
    last_synced_trade_date: str

    def as_response(self) -> dict[str, object]:
        return asdict(self)
