from __future__ import annotations

import os
from pathlib import Path

from trademiner.api.app import create_app
from trademiner.market_data.fake import FakeMarketDataProvider
from trademiner.market_data.models import DailyBar, Instrument


def _bar(instrument_id: str, trade_date: str, close: float) -> DailyBar:
    return DailyBar(
        instrument_id=instrument_id,
        trade_date=trade_date,
        adjustment="hfq",
        open=close,
        high=close,
        low=close,
        close=close,
        volume=1000,
        amount=close * 1000,
    )


provider = FakeMarketDataProvider(
    instruments=[
        Instrument(
            instrument_id="stock:000001",
            symbol="000001",
            name="Ping An Bank",
            instrument_type="stock",
            exchange="SZSE",
        ),
        Instrument(
            instrument_id="stock:000002",
            symbol="000002",
            name="Vanke",
            instrument_type="stock",
            exchange="SZSE",
        ),
        Instrument(
            instrument_id="etf:510300",
            symbol="510300",
            name="CSI 300 ETF",
            instrument_type="etf",
            exchange="SSE",
        ),
    ],
    daily_bars={
        "stock:000001": [
            _bar("stock:000001", "2024-01-01", 10),
            _bar("stock:000001", "2024-01-02", 12),
            _bar("stock:000001", "2024-01-03", 14),
            _bar("stock:000001", "2024-01-04", 16),
            _bar("stock:000001", "2024-01-05", 20),
        ],
        "stock:000002": [
            _bar("stock:000002", "2024-01-01", 10),
            _bar("stock:000002", "2024-01-02", 11),
            _bar("stock:000002", "2024-01-03", 12),
            _bar("stock:000002", "2024-01-04", 13),
            _bar("stock:000002", "2024-01-05", 14),
        ],
        "etf:510300": [
            _bar("etf:510300", "2024-01-01", 10),
            _bar("etf:510300", "2024-01-02", 10.5),
            _bar("etf:510300", "2024-01-03", 11),
            _bar("etf:510300", "2024-01-04", 11.5),
            _bar("etf:510300", "2024-01-05", 12),
        ],
    },
)


app = create_app(
    data_dir=Path(os.environ["TRADEMINER_E2E_DATA_DIR"]),
    data_providers={"akshare": provider},
)
