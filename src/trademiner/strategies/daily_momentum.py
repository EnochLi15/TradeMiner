from trademiner.strategy import Candidate, StrategyContext


STRATEGY = {
    "id": "daily_momentum_v1",
    "name": "Daily Momentum",
    "description": "Ranks instruments by recent adjusted-close momentum.",
    "params": {
        "lookback_days": {"type": "int", "default": 20, "min": 2, "max": 250},
        "top_n": {"type": "int", "default": 20, "min": 1, "max": 100},
        "include_etfs": {"type": "bool", "default": True},
    },
}


def select(ctx: StrategyContext, params: dict) -> list[Candidate]:
    lookback_days = int(params["lookback_days"])
    top_n = int(params["top_n"])
    instrument_types = ["stock", "etf"] if params["include_etfs"] else ["stock"]
    instruments = ctx.universe(types=instrument_types)
    instrument_ids = [instrument.instrument_id for instrument in instruments]
    bars = ctx.daily_bars(instruments=instrument_ids, lookback=lookback_days)

    bars_by_instrument: dict[str, list[dict]] = {}
    for bar in bars:
        bars_by_instrument.setdefault(str(bar["instrument_id"]), []).append(bar)

    candidates: list[Candidate] = []
    for instrument in instruments:
        instrument_bars = bars_by_instrument.get(instrument.instrument_id, [])
        if len(instrument_bars) < 2:
            continue

        first_close = float(instrument_bars[0]["close"])
        latest_close = float(instrument_bars[-1]["close"])
        if first_close == 0:
            continue

        momentum = latest_close / first_close - 1
        candidates.append(
            Candidate(
                instrument_id=instrument.instrument_id,
                score=momentum,
                explanation=(
                    f"{lookback_days}-day adjusted-close momentum "
                    f"is {momentum:.2%} as of {ctx.as_of}"
                ),
                rank_basis="adjusted_close_momentum",
                tags=["momentum", instrument.instrument_type],
                metrics={
                    "first_close": first_close,
                    "latest_close": latest_close,
                    "lookback_days": lookback_days,
                    "momentum": momentum,
                },
            )
        )

    return sorted(
        candidates,
        key=lambda candidate: candidate.score,
        reverse=True,
    )[:top_n]
