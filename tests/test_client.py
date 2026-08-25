"""Offline tests: the HTTP layer is stubbed, everything else runs for real.

    python -m unittest discover tests
"""

import json
import unittest
from unittest import mock

from pinnaclebacktest import (
    AND,
    NOT,
    OR,
    BacktestResult,
    Bet2Invest,
    Bet2InvestError,
    favorite_side,
    league,
    moneyline,
    odds_range,
    total,
    total_odds_range,
)


class FakeResponse:
    def __init__(self, payload):
        self._raw = json.dumps(payload).encode()

    def read(self):
        return self._raw

    def close(self):
        pass

    def __enter__(self):
        return self

    def __exit__(self, *args):
        return False


def stub(responses):
    """Patch urlopen with a queue of payloads; records (method, url, body)."""
    calls = []
    queue = list(responses)

    def fake_urlopen(request, timeout=None):
        body = request.data.decode() if request.data else None
        calls.append((request.get_method(), request.full_url, body))
        return FakeResponse(queue.pop(0))

    patcher = mock.patch("urllib.request.urlopen", side_effect=fake_urlopen)
    return patcher, calls


class FilterTreeTests(unittest.TestCase):
    def test_groups_and_leaves(self):
        tree = AND(league(1980), OR(odds_range("home", 2.2, 3.4), NOT(favorite_side("home"))))
        self.assertEqual(tree["operator"], "AND")
        self.assertEqual(tree["children"][0], {"type": "league", "params": {"leagueIds": [1980]}})
        self.assertEqual(tree["children"][1]["children"][1]["operator"], "NOT")
        self.assertEqual(
            tree["children"][1]["children"][0]["params"],
            {"market": "moneyline", "designation": "home", "min": 2.2, "max": 3.4},
        )

    def test_bet_selections(self):
        self.assertEqual(moneyline("favorite"), {"market": "moneyline", "designation": "favorite"})
        self.assertEqual(total("over"), {"market": "total", "side": "over", "lineMode": "main"})
        self.assertEqual(total("under", 2.5)["points"], 2.5)

    def test_total_odds_range_uses_side_and_line_mode(self):
        main = total_odds_range("under", 1.85, 2.05)
        self.assertEqual(
            main["params"],
            {"market": "total", "side": "under", "min": 1.85, "max": 2.05, "lineMode": "main"},
        )
        fixed = total_odds_range("over", 1.8, 2.1, points=2.5)
        self.assertEqual(fixed["params"]["lineMode"], "fixed")
        self.assertEqual(fixed["params"]["points"], 2.5)


class ClientTests(unittest.TestCase):
    def test_requires_an_api_key(self):
        with mock.patch.dict("os.environ", {}, clear=True):
            with self.assertRaises(ValueError):
                Bet2Invest()

    def test_backtest_polls_until_ready(self):
        patcher, calls = stub(
            [
                {"id": "s1", "name": "x", "status": "draft"},
                {"status": "queued", "jobId": "j1", "token": "t"},
                {"status": "waiting", "queuePosition": 1, "estimatedStartMs": 0},
                {"status": "ready"},
                {"stats": {"totalBets": 412, "yield": 0.031, "winRate": 0.44}, "cumulativePnl": [1, 2], "token": "t"},
            ]
        )
        with patcher, mock.patch("time.sleep"):
            api = Bet2Invest(api_key="b2i_sk_test", base_url="https://example.test/v1/public")
            strategy = api.create_strategy("x", 29, moneyline("home"))
            result = strategy.backtest(poll_interval=0)

        self.assertIsInstance(result, BacktestResult)
        self.assertEqual(result.total_bets, 412)
        self.assertAlmostEqual(result.yield_pct, 3.1)
        self.assertEqual(result.cumulative_pnl, [1, 2])
        self.assertEqual([c[0] for c in calls], ["POST", "POST", "GET", "GET", "GET"])
        self.assertTrue(calls[-1][1].endswith("/strategies/backtests/j1/result"))
        self.assertIn("Yield          +3.10%", result.summary())

    def test_cache_hit_returns_immediately(self):
        patcher, calls = stub(
            [{"status": "ready", "result": {"stats": {"totalBets": 9}, "cumulativePnl": [], "token": "t"}}]
        )
        with patcher:
            api = Bet2Invest(api_key="k", base_url="https://example.test")
            from pinnaclebacktest import Strategy

            result = Strategy(api, {"id": "s1", "name": "x", "status": "draft"}).backtest()
        self.assertEqual(result.total_bets, 9)
        self.assertEqual(len(calls), 1)

    def test_http_errors_carry_the_payload(self):
        import urllib.error

        error = urllib.error.HTTPError(
            "https://example.test/v1/public/strategies/s1/filters",
            422,
            "Unprocessable",
            {},
            FakeResponse({"message": "invalid tree", "issues": [{"path": "children.0", "message": "min < max"}]}),
        )
        with mock.patch("urllib.request.urlopen", side_effect=error):
            api = Bet2Invest(api_key="k", base_url="https://example.test/v1/public")
            from pinnaclebacktest import Strategy

            with self.assertRaises(Bet2InvestError) as raised:
                Strategy(api, {"id": "s1", "name": "x", "status": "draft"}).set_filters(AND())
        self.assertEqual(raised.exception.status, 422)
        self.assertEqual(raised.exception.issues[0]["path"], "children.0")

    def test_sends_bearer_and_json(self):
        patcher, calls = stub([[{"id": 29, "name": "Soccer", "historyYears": 10}]])
        with patcher:
            api = Bet2Invest(api_key="b2i_sk_abc", base_url="https://example.test/v1/public/")
            sports = api.sports()
        self.assertEqual(sports[0]["id"], 29)
        self.assertEqual(calls[0][1], "https://example.test/v1/public/sports")


if __name__ == "__main__":
    unittest.main()
