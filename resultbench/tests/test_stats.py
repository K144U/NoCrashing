import numpy as np
import pandas as pd

from analysis import stats


def test_bootstrap_contains_median():
    est, lo, hi = stats.bootstrap_ci([1, 2, 3, 4, 5, 6, 7])
    assert est == 4
    assert lo <= est <= hi
    assert stats.bootstrap_ci([3.0]) == (3.0, 3.0, 3.0)
    assert all(np.isnan(x) for x in stats.bootstrap_ci([]))


def _users(admitted):
    n = len(admitted)
    return pd.DataFrame({"arrival_ms": np.arange(n) * 10 - 500, "admitted_ms": admitted, "first_try_ms": 0,
                         "manual_refreshes": [1 if i % 2 else 0 for i in range(n)]})


def test_fairness_fifo_and_random():
    n = 400
    fifo = stats.fairness(_users(np.arange(n) * 5))
    assert fifo["kendall_tau"] > 0.99
    rng = np.random.default_rng(1)
    rand = stats.fairness(_users(rng.permutation(n) * 5))
    assert abs(rand["kendall_tau"]) < 0.15


def test_refresh_penalty():
    u = _users(np.arange(100) * 10)
    u.loc[u["manual_refreshes"] > 0, "admitted_ms"] += 5000
    assert stats.fairness(u)["refresh_penalty_ms"] > 4000


def test_recovery():
    t = np.arange(-10, 120)
    backend = np.full(len(t), 100)
    failed = np.where((t >= 5) & (t < 40), 60, 0)
    ts = pd.DataFrame({"t_s": t, "backend": backend, "timeout": failed, "arrivals": 50})
    r = stats.recovery(ts, rise_s=5)
    assert r["recovery_s"] == 40
    assert not r["never_recovered"]
    assert r["peak_failure_share"] == 0.6


def test_never_recovered():
    t = np.arange(0, 60)
    ts = pd.DataFrame({"t_s": t, "backend": 100, "timeout": 50, "arrivals": 10})
    r = stats.recovery(ts, rise_s=5)
    assert r["never_recovered"]
    assert r["tail_amplification"] == 10


def test_staleness():
    req = pd.DataFrame({"t_ms": [100_000, 125_000, 130_000, 200_000], "outcome": ["correct", "stale", "stale", "correct"]})
    s = stats.staleness(req, 120_000)
    assert s["stale_responses"] == 2
    assert s["staleness_window_s"] == 10
