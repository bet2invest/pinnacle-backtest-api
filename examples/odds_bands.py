"""Sweep price bands and print a yield table: where does an angle actually pay?

Backtests are cached server-side, so re-running a band is instant. The API
allows 10 backtest runs per minute; the sweep below stays under that.
"""

from pinnaclebacktest import AND, SPORTS, Bet2Invest, favorite_side, moneyline, odds_range

BANDS = [(1.2, 1.5), (1.5, 1.8), (1.8, 2.2), (2.2, 2.8), (2.8, 3.6), (3.6, 5.0)]

api = Bet2Invest()
strategy = api.create_strategy(
    name="Away favorites by price band",
    sport_id=SPORTS["soccer"],
    bet_selection=moneyline("away"),
)

print(f"{'band':>12} {'bets':>6} {'win%':>6} {'yield':>8} {'max DD':>8}")
for low, high in BANDS:
    strategy.set_filters(AND(favorite_side("away"), odds_range("away", low, high)))
    r = strategy.backtest()
    print(
        f"{low:>5.2f}-{high:<5.2f} {r.total_bets:>6} {r.win_rate_pct:>5.1f}% "
        f"{r.yield_pct:>+7.2f}% {r.max_drawdown:>8.1f}"
    )

strategy.delete()
