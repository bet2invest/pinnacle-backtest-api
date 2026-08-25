# Pinnacle Backtest API

**The Pinnacle API is gone for individuals. Here is a Pinnacle odds API you can still backtest on.**

On 23 July 2025 Pinnacle closed its public API. The `/v1/odds` feed reached end of life on 1 January 2026, and access is now granted case by case to commercial partners and high-value accounts. Every homemade backtester built on that feed, every scraper, every `pinnacle.data`-style package went dark with it, and with them the one thing serious bettors relied on: testing an idea against the sharpest closing line in the market.

Bet2Invest is an official Pinnacle API partner and has been archiving Pinnacle opening and closing odds for years. This client puts that archive behind a backtesting endpoint you can call from Python with a plain API key: no Pinnacle account, no Pinnacle API access, no scraping. Zero dependencies, standard library only.

```python
from pinnaclebacktest import AND, SPORTS, Bet2Invest, league, moneyline, odds_range

api = Bet2Invest()  # reads B2I_API_KEY

strategy = api.create_strategy("EPL home underdogs", SPORTS["soccer"], moneyline("home"))
strategy.set_filters(AND(
    league(api.league_id("Premier League", SPORTS["soccer"])),
    odds_range("home", 2.2, 3.4),
))
print(strategy.backtest().summary())
```

```
Bets           1 184
Win rate       35.9%
Average odds   2.71
Yield          -2.64%
Profit (units) -31.30
Max drawdown   84.50
Sharpe         -0.21
```

Every one of those 1,184 bets was settled at the real Pinnacle closing price. The angle loses. Good to know before the bankroll finds out.

## What you lost, what you get back

| | Pinnacle public API (until July 2025) | Pinnacle Backtest API |
| --- | --- | --- |
| Access | Pinnacle account + API approval, now closed to individuals | Any Bet2Invest account with a Pro or Elite plan, key generated in one click |
| Historical odds | Live feed only; you had to record it yourself, every day, without gaps | Up to 10 years of soccer (20 years coming) and 5 years of 7 other sports, opening and closing prices, already cleaned and settled |
| Backtesting | Your own code, your own settlement logic, your own bugs | One endpoint: send a filter tree, get bets, yield, drawdown, win rate and the P&L curve |
| Markets | Whatever you captured | Moneyline and 1X2, spreads and Asian handicaps, totals and team totals, main or fixed lines |
| Placing bets | Your account, your bot | Optional: saved strategies can be automated on your own Pinnacle account through the official API, non-custodial |

This is not a raw odds dump. It is the layer people actually built on top of the old feed: a settled, queryable history of Pinnacle prices and an engine that runs rules over it.

## Install

```bash
pip install pinnacle-backtest-api
```

or copy `pinnaclebacktest/` into your project: two files, nothing outside the standard library. Python 3.9+.

## Get an API key

1. Create an account on [strategies.bet2invest.com](https://strategies.bet2invest.com).
2. The developer API is included in the Pro and Elite plans.
3. Generate a key in *Settings > API* and export it:

```bash
export B2I_API_KEY=b2i_sk_...
```

Keys are shown once. Revoke them from the same page.

## What is in the archive

- **8 sports**: soccer (up to 10 years, 20 coming), basketball, tennis, American football, baseball, ice hockey, volleyball, esports (5 years each).
- **Both prices**: opening and closing Pinnacle odds on every matchup, so line movement from open to close is part of the data, not something you reconstruct.
- **Settled results**, matched to the odds that were actually offered.
- **37 filters** to slice it: price bands, de-vigged implied probability, vig and league liquidity, league line movement, form and streaks, scoring rates, rest days, standings, season phase, market-implied expected goals. Each one is documented with its parameters in the [filter catalog](https://strategies.bet2invest.com/filters).

Backtests are cached server-side, so re-running an unchanged strategy is instant. Runs are limited to 10 per minute per key.

## Building a filter tree

Filters combine with `AND`, `OR` and `NOT`:

```python
from pinnaclebacktest import AND, OR, NOT, favorite_side, last_n_result_rate, rest_days, odds_range, leaf

tree = AND(
    favorite_side("away"),
    odds_range("away", 1.5, 1.9),
    last_n_result_rate("away", "win", last=10, min=0.6, max=1.0),
    NOT(rest_days("away", min_days=1, max_days=1)),   # skip back-to-backs
    OR(leaf("month", months=[9, 10, 11]), leaf("month", months=[3, 4, 5])),
)
```

Helpers cover the common filters; `leaf(type, **params)` builds any other one straight from the catalog, e.g. `leaf("vig_range", min=0, max=0.03)`. Invalid trees come back as a 422 listing the offending nodes:

```python
try:
    strategy.set_filters(tree)
except Bet2InvestError as error:
    for issue in error.issues:
        print(issue["path"], issue["message"])
```

## Sweep a parameter

[`examples/odds_bands.py`](examples/odds_bands.py) runs the same angle across price bands and prints a table like this:

```
        band   bets   win%    yield   max DD
 1.20-1.50    3 917  67.9%   -1.12%     41.0
 1.50-1.80    5 402  55.1%   +0.84%     58.5
 1.80-2.20    4 118  46.3%   +2.31%     47.2
 2.20-2.80    2 655  36.0%   +0.47%     63.9
 2.80-3.60    1 201  27.9%   -3.80%     71.4
```

This is the loop most people were running against their own Pinnacle capture. It now takes six requests.

## From backtest to live picks

```python
if result.total_bets >= 300 and result.yield_pct > 2:
    strategy.save()                       # freezes the filters, starts live tracking
    for pick in strategy.picks("pending"):
        print(pick["homeTeam"], "v", pick["awayTeam"], pick["bet"], pick["detectionOdds"])
```

Saved strategies keep running on live Pinnacle prices: picks arrive by email or Telegram, `strategy.stats()` tracks them against the Pinnacle close, and the app can place them on your own Pinnacle account through the official API if you have one. If you do not, you still get the picks.

## API surface

| Method | Endpoint |
| --- | --- |
| `api.sports()` / `api.leagues(query, sport_id)` | `GET /sports`, `GET /leagues` |
| `api.create_strategy(...)` / `api.strategies()` / `api.strategy(id)` | `POST /strategies`, `GET /strategies`, `GET /strategies/{id}` |
| `strategy.set_filters(tree)` | `PUT /strategies/{id}/filters` |
| `strategy.backtest()` | `POST /strategies/{id}/backtest` + polling |
| `strategy.save()` / `archive()` / `unarchive()` / `delete()` | the matching `POST` / `DELETE` |
| `strategy.stats()` / `strategy.picks(category)` | `GET /strategies/{id}/stats`, `GET /strategies/{id}/picks` |

Full reference with schemas: [api.bet2invest.com/v1/public/docs](https://api.bet2invest.com/v1/public/docs). Set `B2I_API_BASE` to point the client at another host.

## Why the Pinnacle close, specifically

Pinnacle runs some of the lowest margins in the industry and takes winning action, so its closing line is the best public estimate of an outcome's probability: every sharp bet placed before kick-off has pushed it toward the truth. That is why the whole industry, Pinnacle included, judges bettors by closing line value. A strategy with a positive yield at Pinnacle closing prices survived the market's best guess. One that only works at opening or soft-book prices did not find an edge, it found a discrepancy nobody could bet at scale. More on [closing line value](https://strategies.bet2invest.com/closing-line-value), [backtesting](https://strategies.bet2invest.com/backtesting) and the [Pinnacle historical odds](https://strategies.bet2invest.com/pinnacle-historical-odds) behind this client.

## Development

```bash
python -m unittest discover tests
```

Tests stub the HTTP layer and run offline.

## Disclaimer

Past performance on historical odds does not guarantee future results. Bet responsibly and within the laws of your jurisdiction. Pinnacle is a trademark of its owner; this client is maintained by [Bet2Invest](https://bet2invest.com), an official Pinnacle API partner, and released under the MIT license.
