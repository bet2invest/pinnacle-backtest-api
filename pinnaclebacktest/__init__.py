"""Pinnacle Backtest API: a Pinnacle odds API for backtesting, now that Pinnacle's own is closed."""

from .client import SPORTS, BacktestResult, Bet2Invest, Bet2InvestError, Strategy
from .filters import (
    AND,
    NOT,
    OR,
    favorite_side,
    implied_probability,
    last_n_result_rate,
    leaf,
    league,
    league_liquidity,
    moneyline,
    month,
    odds_range,
    rest_days,
    spread,
    spread_odds_range,
    total,
    total_implied_probability,
    total_odds_range,
)

__version__ = "0.1.0"

__all__ = [
    "SPORTS",
    "BacktestResult",
    "Bet2Invest",
    "Bet2InvestError",
    "Strategy",
    "AND",
    "OR",
    "NOT",
    "leaf",
    "odds_range",
    "total_odds_range",
    "spread_odds_range",
    "implied_probability",
    "total_implied_probability",
    "league",
    "favorite_side",
    "last_n_result_rate",
    "rest_days",
    "month",
    "league_liquidity",
    "moneyline",
    "total",
    "spread",
]
