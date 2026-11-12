"""Second-round predictions for the refresh paper (P8 metastability, P5c room
capacity), written before any of these runs. Same model code and CPU costs as
the first round (make_predictions.py); nothing is fitted to an outcome.

- P8: after a surge, does the collapse persist at a load the server could
  carry from a fresh start? Impatient students (patience 3-8 s, pause
  0.5-2 s), one refresh probability p for errors and time-outs.
  Derivation condition (8): metastable if (1 - p)(b - a) < S.
- P5c: the waiting room alone (admitting 1 student/s), with only queued
  students polling. The room's CPU limit over its cost per queued answer
  predicts how many queued answers per second it can give.

    cd ~/NoCrashing && source ~/venvs/resultbench/bin/activate
    taskset -c 0,1 nice -n 19 python refresh-paper/make_predictions2.py
"""
from __future__ import annotations

import csv
import math
import subprocess
import sys
from dataclasses import replace
from pathlib import Path

HERE = Path(__file__).resolve().parent
RB = HERE.parent / "resultbench"
sys.path.insert(0, str(RB))
sys.path.insert(0, str(HERE))

import yaml  # noqa: E402

from make_predictions import CAP_1X, DT  # noqa: E402
from model.capacity import cpu_costs, from_scenario, lab_runs, recovery_s, room_cpu_costs, simulate  # noqa: E402

HOLD = (150, 300)      # seconds after release over which the steady (post-surge) load is judged
POST_RELEASE_S = 300   # arrivals continue for 300 s after release
ROOM_CPUS = 0.25       # design D-A's waiting room limit


def hold_ok(by_send: dict, lo: int, hi: int) -> float:
    """Share of the requests sent in [lo, hi) that were answered in time."""
    sent = sum(by_send.get(t, {}).get("sent", 0.0) for t in range(lo, hi))
    ok = sum(by_send.get(t, {}).get("correct", 0.0) for t in range(lo, hi))
    return ok / sent if sent > 1e-9 else math.nan


def main() -> None:
    runs = RB / "runs"
    exps = [runs / e for e in ("paper-core", "paper-refresh", "paper-wr", "paper-sens") if (runs / e).exists()]
    costs = cpu_costs(lab_runs(exps, "a"))
    ans = costs["answer"]["5ms"]
    mu = (1.0 - costs["idle_cpus"]) / ans
    other = costs["other"] / ans

    sc = yaml.safe_load((RB / "bench" / "scenarios" / "paper.yaml").read_text())
    base_surge, base_users = from_scenario(sc)
    rows = []

    # P8: metastability.
    profiles = {
        "surge 2x to 0.5x": replace(base_surge, peak=2.0 * CAP_1X, floor_frac=0.25, post_release_s=POST_RELEASE_S),
        "steady 0.5x": replace(base_surge, peak=0.5 * CAP_1X, floor_frac=1.0, post_release_s=POST_RELEASE_S),
    }
    for p in (0.5, 0.95):
        users = replace(base_users, patience=(3.0, 8.0), retry_prob=p, impatient_retry_prob=p, retry_delay=(0.5, 2.0))
        for name, surge in profiles.items():
            r = simulate(surge, users, mu, dt=DT, drain_s=45, other_cost=other, keep_timeline=True)
            rec = recovery_s(r.by_send, surge.rise_s)
            rows.append({"block": "P8", "refresh_prob": p, "profile": name,
                         "served_ok": r.served_ok, "useful_share": r.useful_share,
                         "amplification": r.amplification,
                         "hold_ok_share": hold_ok(r.by_send, *HOLD),
                         "recovery_s": rec,
                         "recovers_while_arriving": (not math.isnan(rec)) and rec <= POST_RELEASE_S})

    # Closed form, derivation (7)-(9): lambda_exit = (b - a) mu / (N S), S = W / mu.
    S = 256 / mu
    closed = {}
    for p in (0.5, 0.95):
        n = (1 - p ** 20) / (1 - p)
        closed[p] = {"N": n, "S": S, "metastable_(8)": (1 - p) * 5.0 < S,
                     "lambda_exit_per_s": 5.0 * mu / (n * S),
                     "lambda_exit_x": 5.0 * mu / (n * S) / CAP_1X}

    # P5c: the room's own capacity.
    rc = room_cpu_costs(lab_runs([runs / e for e in ("paper-wr", "paper-wr-long", "paper-refresh")
                                  if (runs / e).exists()], "d-a"))
    room_q = ROOM_CPUS / rc[0] if rc else math.nan

    with (HERE / "predictions2.csv").open("w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0]))
        w.writeheader()
        w.writerows(rows)
    commit = subprocess.run(["git", "-C", str(HERE.parent), "describe", "--always", "--dirty"],
                            capture_output=True, text=True).stdout.strip()
    md = ["# Second-round predictions (generated)", "",
          f"Model code: `resultbench/model/capacity.py` at commit `{commit}`; time step {DT} s; "
          f"mu = {mu:.1f} answers/s; 1x = {CAP_1X} students/s.", "",
          "## P8: metastability (impatient students, patience 3-8 s, pause 0.5-2 s; arrivals for 300 s after "
          f"release, runs end 45 s later; 'hold' = requests sent {HOLD[0]}-{HOLD[1]} s after release)", "",
          "| p | Arrivals | Served | Useful work | Requests/student | Answered in hold | Recovery | Recovers while students arrive |",
          "|---|---|---|---|---|---|---|---|"]
    for r in rows:
        rec = "never" if math.isnan(r["recovery_s"]) else f"{r['recovery_s']:.0f} s"
        md.append(f"| {r['refresh_prob']:g} | {r['profile']} | {r['served_ok']:.1%} | {r['useful_share']:.1%} | "
                  f"{r['amplification']:.2f} | {r['hold_ok_share']:.1%} | {rec} | "
                  f"{'yes' if r['recovers_while_arriving'] else 'no'} |")
    md += ["", "Closed form (derivation (7)-(9), M = 20, b - a = 5 s, S = W/mu):", ""]
    for p, c in closed.items():
        md.append(f"- p = {p:g}: N = {c['N']:.2f}, S = {c['S']:.2f} s, metastable by (8): "
                  f"{'yes' if c['metastable_(8)'] else 'no'}, collapse persists while first requests >= "
                  f"{c['lambda_exit_per_s']:.0f}/s ({c['lambda_exit_x']:.2f}x)")
    md += ["", "## P5c: the waiting room alone", "",
           f"- Room CPU costs fitted to the saturated seconds of the earlier D-A runs: "
           f"{rc[0] * 1e6:.1f} us per queued answer, {rc[1] * 1e6:.0f} us per passed-through request." if rc else
           "- Room CPU costs: not enough saturated runs.",
           f"- Predicted capacity of the {ROOM_CPUS} CPU room with nobody admitted: {room_q:,.0f} queued answers/s.", ""]
    (HERE / "predictions2-tables.md").write_text("\n".join(md) + "\n")
    print("\n".join(md))


if __name__ == "__main__":
    main()
