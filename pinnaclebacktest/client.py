"""Minimal client for the Bet2Invest public strategy API.

Pinnacle closed its public API to individuals in July 2025; this talks to the
Bet2Invest API, an official Pinnacle partner, which backtests rule sets over
years of archived Pinnacle opening and closing odds. Standard library only: one
file, no dependencies. The API reference lives at
https://api.bet2invest.com/v1/public/docs and every method below maps to one
endpoint of it.
"""

from __future__ import annotations

import json
import os
import time
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass, field
from typing import Any, Dict, Iterator, List, Optional

DEFAULT_BASE_URL = "https://api.bet2invest.com/v1/public"

# Sport ids accepted by the API, as shown by `GET /sports`.
SPORTS = {
    "soccer": 29,
    "basketball": 4,
    "tennis": 33,
    "american_football": 15,
    "baseball": 3,
    "ice_hockey": 19,
    "volleyball": 34,
    "esports": 12,
}


class Bet2InvestError(Exception):
    """HTTP error from the API, with the decoded body when there is one."""

    def __init__(self, status: int, payload: Any, url: str):
        self.status = status
        self.payload = payload
        self.url = url
        message = payload.get("message") if isinstance(payload, dict) else payload
        super().__init__(f"{status} on {url}: {message}")

    @property
    def issues(self) -> List[Dict[str, Any]]:
        """Per-node issues of a rejected filter tree (HTTP 422)."""
        if isinstance(self.payload, dict):
            return list(self.payload.get("issues") or [])
        return []


@dataclass
class BacktestResult:
    """Outcome of a finished backtest: KPIs plus the cumulative P&L curve."""

    stats: Dict[str, Any]
    cumulative_pnl: List[float] = field(default_factory=list)
    token: Optional[str] = None

    @property
    def total_bets(self) -> int:
        return int(self.stats.get("totalBets", 0))

    @property
    def yield_pct(self) -> float:
        """Profit per unit staked, in percent (yield 0.042 -> 4.2)."""
        return float(self.stats.get("yield", 0.0)) * 100

    @property
    def win_rate_pct(self) -> float:
        return float(self.stats.get("winRate", 0.0)) * 100

    @property
    def max_drawdown(self) -> float:
        return float(self.stats.get("maxDrawdown", 0.0))

    @property
    def total_profit(self) -> float:
        return float(self.stats.get("totalProfit", 0.0))

    @property
    def average_odds(self) -> float:
        return float(self.stats.get("averageOdds", 0.0))

    def summary(self) -> str:
        """Human-readable one-screen summary."""
        lines = [
            f"Bets           {self.total_bets}",
            f"Win rate       {self.win_rate_pct:.1f}%",
            f"Average odds   {self.average_odds:.2f}",
            f"Yield          {self.yield_pct:+.2f}%",
            f"Profit (units) {self.total_profit:+.2f}",
            f"Max drawdown   {self.max_drawdown:.2f}",
            f"Sharpe         {float(self.stats.get('sharpeRatio', 0.0)):.2f}",
        ]
        return "\n".join(lines)

    def to_dataframe(self):
        """Cumulative P&L as a pandas Series (pandas is optional)."""
        import pandas as pd  # noqa: WPS433 - optional dependency

        return pd.Series(self.cumulative_pnl, name="cumulative_pnl")


class Strategy:
    """One strategy owned by your API key. Created through `Bet2Invest`."""

    def __init__(self, client: "Bet2Invest", data: Dict[str, Any]):
        self._client = client
        self.data = data

    @property
    def id(self) -> str:
        return self.data["id"]

    @property
    def name(self) -> str:
        return self.data["name"]

    @property
    def status(self) -> str:
        return self.data["status"]

    def __repr__(self) -> str:
        return f"Strategy(id={self.id!r}, name={self.name!r}, status={self.status!r})"

    def _refresh(self, data: Dict[str, Any]) -> "Strategy":
        self.data = data
        return self

    def set_filters(self, tree: Dict[str, Any]) -> "Strategy":
        """Replace the filter tree. Raises `Bet2InvestError` (422) with `.issues` when invalid."""
        return self._refresh(
            self._client._request("PUT", f"/strategies/{self.id}/filters", {"tree": tree})
        )

    def update(self, **fields: Any) -> "Strategy":
        """Change `name`, `description` or `betSelection`."""
        return self._refresh(self._client._request("PUT", f"/strategies/{self.id}", fields))

    def backtest(self, poll_interval: float = 2.0, timeout: float = 900.0) -> BacktestResult:
        """Run the backtest and block until the result is ready."""
        started = self._client._request("POST", f"/strategies/{self.id}/backtest")
        if started["status"] == "ready":
            return _to_result(started["result"])
        job_id = started["jobId"]
        deadline = time.monotonic() + timeout
        while True:
            progress = self._client._request("GET", f"/strategies/backtests/{job_id}")
            status = progress["status"]
            if status == "ready":
                return _to_result(
                    self._client._request("GET", f"/strategies/backtests/{job_id}/result")
                )
            if status == "failed":
                raise Bet2InvestError(500, progress.get("reason") or "backtest failed", job_id)
            if time.monotonic() > deadline:
                raise TimeoutError(f"backtest {job_id} still {status} after {timeout}s")
            self._client.on_progress(progress)
            time.sleep(poll_interval)

    def save(self) -> "Strategy":
        """Freeze the filters and start live tracking (uses a plan slot)."""
        return self._refresh(self._client._request("POST", f"/strategies/{self.id}/save"))

    def archive(self) -> "Strategy":
        return self._refresh(self._client._request("POST", f"/strategies/{self.id}/archive"))

    def unarchive(self) -> "Strategy":
        return self._refresh(self._client._request("POST", f"/strategies/{self.id}/unarchive"))

    def delete(self) -> None:
        self._client._request("DELETE", f"/strategies/{self.id}")

    def stats(self) -> Dict[str, Any]:
        """KPI windows (`all` / `backtest` / `live`) and the robustness report."""
        return self._client._request("GET", f"/strategies/{self.id}/stats")

    def picks(self, category: str = "pending", limit: int = 100) -> Iterator[Dict[str, Any]]:
        """Iterate over `pending` or `historical` picks, page by page."""
        page = 1
        while True:
            response = self._client._request(
                "GET",
                f"/strategies/{self.id}/picks",
                params={"category": category, "page": page, "limit": limit},
            )
            items = response.get("data") or []
            for item in items:
                yield item
            if len(items) < limit:
                return
            page += 1


class Bet2Invest:
    """Entry point. Pass your key or set `B2I_API_KEY`; `B2I_API_BASE` overrides the host."""

    def __init__(
        self,
        api_key: Optional[str] = None,
        base_url: Optional[str] = None,
        timeout: float = 30.0,
    ):
        self.api_key = api_key or os.environ.get("B2I_API_KEY")
        if not self.api_key:
            raise ValueError("Pass api_key= or set the B2I_API_KEY environment variable")
        self.base_url = (base_url or os.environ.get("B2I_API_BASE") or DEFAULT_BASE_URL).rstrip("/")
        self.timeout = timeout

    def on_progress(self, progress: Dict[str, Any]) -> None:
        """Called on every poll while a backtest runs. Override or reassign to log."""

    # Reference data

    def sports(self) -> List[Dict[str, Any]]:
        return self._request("GET", "/sports")

    def leagues(self, query: str, sport_id: Optional[int] = None) -> List[Dict[str, Any]]:
        params: Dict[str, Any] = {"query": query}
        if sport_id is not None:
            params["sportId"] = sport_id
        return self._request("GET", "/leagues", params=params)

    def league_id(self, query: str, sport_id: Optional[int] = None) -> int:
        """Id of the first league matching `query`; raises when nothing matches."""
        matches = self.leagues(query, sport_id)
        if not matches:
            raise LookupError(f"no league matches {query!r}")
        return int(matches[0]["id"])

    # Strategies

    def create_strategy(
        self,
        name: str,
        sport_id: int,
        bet_selection: Dict[str, Any],
        description: Optional[str] = None,
    ) -> Strategy:
        body: Dict[str, Any] = {"name": name, "sportId": sport_id, "betSelection": bet_selection}
        if description:
            body["description"] = description
        return Strategy(self, self._request("POST", "/strategies", body))

    def strategies(self, sport_id: Optional[int] = None, active: bool = False) -> List[Strategy]:
        """Your strategies; `active=True` keeps only the saved, live-tracked ones."""
        params: Dict[str, Any] = {}
        if sport_id is not None:
            params["sportId"] = sport_id
        if active:
            params["isActive"] = "true"
        return [Strategy(self, row) for row in self._request("GET", "/strategies", params=params)]

    def strategy(self, strategy_id: str) -> Strategy:
        return Strategy(self, self._request("GET", f"/strategies/{strategy_id}"))

    # Transport

    def _request(
        self,
        method: str,
        path: str,
        body: Optional[Dict[str, Any]] = None,
        params: Optional[Dict[str, Any]] = None,
    ) -> Any:
        url = self.base_url + path
        if params:
            url += "?" + urllib.parse.urlencode(params)
        data = json.dumps(body).encode() if body is not None else None
        request = urllib.request.Request(url, data=data, method=method)
        request.add_header("Authorization", f"Bearer {self.api_key}")
        request.add_header("Accept", "application/json")
        request.add_header("User-Agent", "pinnacle-backtest-api/0.1")
        if data is not None:
            request.add_header("Content-Type", "application/json")
        try:
            with urllib.request.urlopen(request, timeout=self.timeout) as response:
                raw = response.read()
        except urllib.error.HTTPError as error:
            raise Bet2InvestError(error.code, _decode(error.read()), url) from None
        return _decode(raw)


def _decode(raw: bytes) -> Any:
    if not raw:
        return None
    try:
        return json.loads(raw)
    except ValueError:
        return raw.decode(errors="replace")


def _to_result(payload: Dict[str, Any]) -> BacktestResult:
    return BacktestResult(
        stats=payload.get("stats") or {},
        cumulative_pnl=list(payload.get("cumulativePnl") or []),
        token=payload.get("token"),
    )
