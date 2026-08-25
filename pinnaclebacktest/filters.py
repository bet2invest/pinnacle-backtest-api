"""Helpers that build the filter tree the API expects.

A tree is a group node (`AND` / `OR` / `NOT`) whose children are leaves
`{"type": ..., "params": {...}}` or other groups. Every leaf below mirrors one
filter of the Strategy Builder; `leaf()` covers the ones without a helper.
The full catalog with each `params` schema: https://strategies.bet2invest.com/filters
"""

from __future__ import annotations

from typing import Any, Dict, Iterable, List, Optional

Node = Dict[str, Any]


def AND(*children: Node) -> Node:
    return {"operator": "AND", "children": list(children)}


def OR(*children: Node) -> Node:
    return {"operator": "OR", "children": list(children)}


def NOT(child: Node) -> Node:
    return {"operator": "NOT", "children": [child]}


def leaf(filter_type: str, **params: Any) -> Node:
    """Generic leaf, e.g. `leaf("vig_range", min=0, max=0.03)`."""
    return {"type": filter_type, "params": params}


def odds_range(designation: str, min: float, max: float) -> Node:
    """Moneyline closing price band on one side: `odds_range("home", 2.2, 3.4)`.

    `designation` is `home`, `away`, `draw`, `favorite` or `underdog`.
    """
    return leaf("odds_range", market="moneyline", designation=designation, min=min, max=max)


def total_odds_range(side: str, min: float, max: float, points: Optional[float] = None) -> Node:
    """Price band on `over` / `under`, on the main total unless `points` fixes the line."""
    return leaf("odds_range", market="total", side=side, min=min, max=max, **_line(points))


def spread_odds_range(
    designation: str, min: float, max: float, points: Optional[float] = None
) -> Node:
    """Price band on the `home` / `away` handicap, main line unless `points` is given."""
    return leaf(
        "odds_range", market="spread", designation=designation, min=min, max=max, **_line(points)
    )


def implied_probability(designation: str, min: float, max: float) -> Node:
    """De-vigged moneyline probability band, 0-1: `implied_probability("favorite", 0.6, 0.75)`."""
    return leaf(
        "implied_probability", market="moneyline", designation=designation, min=min, max=max
    )


def total_implied_probability(
    side: str, min: float, max: float, points: Optional[float] = None
) -> Node:
    """De-vigged probability band on `over` / `under`, main total unless `points` is given."""
    return leaf("implied_probability", market="total", side=side, min=min, max=max, **_line(points))


def _line(points: Optional[float]) -> Dict[str, Any]:
    if points is None:
        return {"lineMode": "main"}
    return {"lineMode": "fixed", "points": points}


def league(*league_ids: int) -> Node:
    """Restrict to leagues, ids from `Bet2Invest.leagues()` / `league_id()`."""
    return leaf("league", leagueIds=list(league_ids))


def favorite_side(expected: str) -> Node:
    """`home` or `away`: which side the market makes favorite."""
    return leaf("favorite_side", expected=expected)


def last_n_result_rate(
    side: str,
    metric: str,
    last: int,
    min: float,
    max: float,
    venue_scope: str = "allVenue",
    min_sample_size: Optional[int] = None,
) -> Node:
    """Form filter: share of `metric` (`win`, `draw`, `loss`, `nonWin`, ...) over the
    team's `last` matches (3, 5, 10, 20, 50 or 70). `side` is `home`, `away`,
    `favorite` or `underdog`; `venue_scope` is `allVenue`, `atHome` or `onRoad`.
    """
    params: Dict[str, Any] = {
        "side": side,
        "metric": metric,
        "last": last,
        "min": min,
        "max": max,
        "venueScope": venue_scope,
    }
    if min_sample_size is not None:
        params["minSampleSize"] = min_sample_size
    return leaf("last_n_result_rate", **params)


def rest_days(side: str, min_days: int, max_days: Optional[int] = None) -> Node:
    """Days since the side's previous match; `max_days=1` with `min_days=1` = back-to-back."""
    params: Dict[str, Any] = {"side": side, "minDays": min_days}
    if max_days is not None:
        params["maxDays"] = max_days
    return leaf("rest_days", **params)


def month(months: Iterable[int]) -> Node:
    """Calendar months, 1-12."""
    return leaf("month", months=list(months))


def league_liquidity(min: float, max: float) -> Node:
    """League closing liquidity band, in the sportsbook's units."""
    return leaf("league_liquidity", min=min, max=max)


# Bet selections, the `betSelection` of `create_strategy()`.


def moneyline(designation: str) -> Dict[str, Any]:
    """`home`, `away`, `draw`, `favorite` or `underdog` on the match winner market."""
    return {"market": "moneyline", "designation": designation}


def total(side: str, points: Optional[float] = None) -> Dict[str, Any]:
    """`over` or `under`; a fixed line with `points`, else the main line at match time."""
    if points is None:
        return {"market": "total", "side": side, "lineMode": "main"}
    return {"market": "total", "side": side, "points": points, "lineMode": "fixed"}


def spread(designation: str, points: Optional[float] = None) -> Dict[str, Any]:
    """`home` or `away` on the handicap; main line unless `points` is given."""
    if points is None:
        return {"market": "spread", "designation": designation, "lineMode": "main"}
    return {"market": "spread", "designation": designation, "points": points, "lineMode": "fixed"}


__all__: List[str] = [
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
