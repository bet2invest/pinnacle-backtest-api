"""Backtest "home underdogs priced 2.2 to 3.4 in the Premier League" in 20 lines.

    export B2I_API_KEY=b2i_sk_...
    python examples/quickstart.py
"""

from pinnaclebacktest import AND, SPORTS, Bet2Invest, league, moneyline, odds_range

api = Bet2Invest()

strategy = api.create_strategy(
    name="EPL home underdogs",
    sport_id=SPORTS["soccer"],
    bet_selection=moneyline("home"),
)
strategy.set_filters(
    AND(
        league(api.league_id("Premier League", SPORTS["soccer"])),
        odds_range("home", 2.2, 3.4),
    )
)

result = strategy.backtest()
print(result.summary())

# The draft is yours: keep it (strategy.save()) or clean up.
strategy.delete()
