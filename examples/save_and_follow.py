"""Keep a strategy that backtests well, then read its live picks.

Saving freezes the filters and starts live tracking against Pinnacle closing
odds; picks show up in the app, by notification, and here.
"""

from pinnaclebacktest import AND, SPORTS, Bet2Invest, last_n_result_rate, rest_days, total, total_odds_range

api = Bet2Invest()

strategy = api.create_strategy(
    name="NBA rested unders",
    sport_id=SPORTS["basketball"],
    bet_selection=total("under"),
)
strategy.set_filters(
    AND(
        rest_days("home", min_days=3),
        last_n_result_rate("home", "win", last=10, min=0.6, max=1.0),
        total_odds_range("under", 1.85, 2.05),
    )
)

result = strategy.backtest()
print(result.summary())

if result.total_bets >= 300 and result.yield_pct > 2:
    strategy.save()
    for pick in strategy.picks("pending"):
        print(pick["matchDate"], pick["homeTeam"], "v", pick["awayTeam"], pick["bet"], pick["detectionOdds"])
else:
    print("Not convincing enough to follow.")
    strategy.delete()
