from trademiner.strategy import Candidate


STRATEGY = {
    "id": "e2e_close_ranker",
    "name": "E2E Close Ranker",
    "description": "Ranks instruments by latest close for E2E discovery coverage.",
    "params": {
        "top_n": {"type": "int", "default": 1, "min": 1, "max": 10},
    },
}


def select(ctx, params):
    candidates = []
    for instrument in ctx.universe(types=["stock"]):
        bars = ctx.daily_bars(instruments=[instrument.instrument_id], lookback=1)
        if not bars:
            continue
        close = bars[-1]["close"]
        candidates.append(
            Candidate(
                instrument_id=instrument.instrument_id,
                score=close,
                explanation=f"latest close is {close}",
                rank_basis="latest_close",
                tags=["e2e"],
                metrics={"close": close},
            )
        )
    return candidates[: params["top_n"]]
