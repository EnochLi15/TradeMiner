from __future__ import annotations

from typing import Any

from trademiner.market_data.models import DailyBar, Instrument


class AkShareMarketDataProvider:
    name = "akshare"

    def fetch_instruments(self, instrument_types: list[str]) -> list[Instrument]:
        ak = self._akshare()
        instruments: list[Instrument] = []

        if "stock" in instrument_types:
            stock_df = ak.stock_info_a_code_name()
            for record in stock_df.to_dict("records"):
                symbol = str(record["code"]).zfill(6)
                instruments.append(
                    Instrument(
                        instrument_id=f"stock:{symbol}",
                        symbol=symbol,
                        name=str(record["name"]),
                        instrument_type="stock",
                        exchange=_infer_a_share_exchange(symbol),
                    )
                )

        if "etf" in instrument_types:
            etf_df = ak.fund_etf_spot_em()
            for record in etf_df.to_dict("records"):
                symbol = str(record["代码"]).zfill(6)
                instruments.append(
                    Instrument(
                        instrument_id=f"etf:{symbol}",
                        symbol=symbol,
                        name=str(record["名称"]),
                        instrument_type="etf",
                        exchange=_infer_a_share_exchange(symbol),
                    )
                )

        return instruments

    def fetch_daily_bars(
        self,
        instrument: Instrument,
        start_date: str,
        end_date: str,
        adjustment: str,
    ) -> list[DailyBar]:
        ak = self._akshare()
        start = start_date.replace("-", "")
        end = end_date.replace("-", "")

        if instrument.instrument_type == "stock":
            frame = ak.stock_zh_a_hist(
                symbol=instrument.symbol,
                period="daily",
                start_date=start,
                end_date=end,
                adjust=adjustment,
            )
        elif instrument.instrument_type == "etf":
            frame = ak.fund_etf_hist_em(
                symbol=instrument.symbol,
                period="daily",
                start_date=start,
                end_date=end,
                adjust=adjustment,
            )
        else:
            return []

        return [_record_to_daily_bar(instrument, adjustment, record) for record in frame.to_dict("records")]

    def _akshare(self) -> Any:
        try:
            import akshare as ak
        except ImportError as error:
            raise RuntimeError(
                "AkShare is not installed. Install the TradeMiner Python dependencies "
                "before using the default data provider."
            ) from error
        return ak


def _record_to_daily_bar(
    instrument: Instrument,
    adjustment: str,
    record: dict[str, Any],
) -> DailyBar:
    return DailyBar(
        instrument_id=instrument.instrument_id,
        trade_date=str(record["日期"]),
        adjustment=adjustment,
        open=float(record["开盘"]),
        high=float(record["最高"]),
        low=float(record["最低"]),
        close=float(record["收盘"]),
        volume=float(record["成交量"]),
        amount=float(record.get("成交额", 0) or 0),
    )


def _infer_a_share_exchange(symbol: str) -> str | None:
    if symbol.startswith(("5", "6", "9")):
        return "SSE"
    if symbol.startswith(("0", "1", "2", "3")):
        return "SZSE"
    if symbol.startswith(("4", "8")):
        return "BSE"
    return None
