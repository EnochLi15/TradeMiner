from __future__ import annotations

from dataclasses import dataclass

from trademiner.jobs import JobRecord, JobRepository
from trademiner.market_data.cache import MarketDataCache
from trademiner.market_data.models import SyncCursor
from trademiner.market_data.providers import MarketDataProvider


@dataclass(frozen=True)
class MarketDataSyncRequest:
    provider: str
    instrument_types: list[str]
    adjustment: str
    start_date: str
    end_date: str
    overlap_days: int = 5
    trigger: str = "manual"


class MarketDataSyncService:
    def __init__(
        self,
        cache: MarketDataCache,
        jobs: JobRepository,
        providers: dict[str, MarketDataProvider],
    ):
        self.cache = cache
        self.jobs = jobs
        self.providers = providers

    def sync(self, request: MarketDataSyncRequest) -> JobRecord:
        provider = self.providers.get(request.provider)
        job = self.jobs.create_pending(
            "sync_market_data",
            {
                "provider": request.provider,
                "instrument_types": request.instrument_types,
                "adjustment": request.adjustment,
                "start_date": request.start_date,
                "end_date": request.end_date,
                "overlap_days": request.overlap_days,
                "trigger": request.trigger,
            },
        )

        if provider is None:
            return self.jobs.fail(job.id, f"Unknown data provider: {request.provider}")

        self.jobs.start(job.id)
        try:
            instruments = provider.fetch_instruments(request.instrument_types)
            instrument_count = self.cache.upsert_instruments(instruments)
            daily_bar_count = 0

            for instrument in instruments:
                start_date = self.cache.incremental_start_date(
                    provider=request.provider,
                    adjustment=request.adjustment,
                    instrument_id=instrument.instrument_id,
                    requested_start_date=request.start_date,
                    overlap_days=request.overlap_days,
                )
                bars = provider.fetch_daily_bars(
                    instrument=instrument,
                    start_date=start_date,
                    end_date=request.end_date,
                    adjustment=request.adjustment,
                )
                daily_bar_count += self.cache.upsert_daily_bars(bars)
                latest_trade_date = _latest_trade_date(bars)
                if latest_trade_date is not None:
                    self.cache.upsert_cursor(
                        SyncCursor(
                            provider=request.provider,
                            data_type="daily_bars",
                            adjustment=request.adjustment,
                            scope=instrument.instrument_id,
                            last_synced_trade_date=latest_trade_date,
                        )
                    )

            return self.jobs.succeed(
                job.id,
                progress={
                    "instrument_count": instrument_count,
                    "daily_bar_count": daily_bar_count,
                    "synced_through": request.end_date,
                },
            )
        except Exception as error:
            return self.jobs.fail(job.id, str(error))


def _latest_trade_date(bars: list[object]) -> str | None:
    trade_dates = [getattr(bar, "trade_date") for bar in bars]
    if not trade_dates:
        return None
    return max(trade_dates)
