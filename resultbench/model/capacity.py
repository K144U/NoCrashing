"""Capacity-planning model (plan section 8.1).

A fluid queueing model of result day: students arrive following the surge
curve, requests queue first-come-first-served for a server of capacity mu
(requests per second), students give up when their patience runs out and
refresh with some probability, and refreshes join the queue again. The model
is deliberately simple so that a board's IT cell can use it; its accuracy is
measured against the lab runs instead of assumed.

    # predict one lab configuration
    python -m model.capacity simulate --scenario bench/scenarios/core.yaml --capacity 238 --peak 1190

    # fit the overload efficiency to lab runs and report prediction error
    python -m model.capacity fit runs/core runs/refresh --design a

    # planning table for real board sizes
    python -m model.capacity plan --cpu-costs runs/core/report/summary.csv --out planning.md
"""
from __future__ import annotations

import argparse
import json
import math
from collections import defaultdict
from dataclasses import dataclass, field
from pathlib import Path

import yaml


@dataclass
class Surge:
    peak: float
    pre_release_s: float = 60
    start_frac: float = 0.02
    end_frac: float = 0.2
    rise_s: float = 5
    decay_tau_s: float = 90
    floor_frac: float = 0.02
    post_release_s: float = 300

    def rate(self, t: float) -> float:
        """Same curve as surge.SurgeSpec.Rate in the Go generator."""
        p = self.peak
        if t > self.post_release_s or t < -self.pre_release_s:
            return 0.0
        if t < 0:
            f = (t + self.pre_release_s) / self.pre_release_s
            return p * (self.start_frac + (self.end_frac - self.start_frac) * f)
        if t < self.rise_s:
            return p * (self.end_frac + (1 - self.end_frac) * t / self.rise_s)
        floor = self.floor_frac * p
        return floor + (p - floor) * math.exp(-(t - self.rise_s) / max(self.decay_tau_s, 1e-9))


@dataclass
class Users:
    patience: tuple[float, float] = (5, 20)
    retry_prob: float = 0.8
    impatient_retry_prob: float = 0.9
    retry_delay: tuple[float, float] = (1, 5)
    max_attempts: int = 20
    prerelease_poll: tuple[float, float] = (10, 30)


@dataclass
class Result:
    users: float
    served: float
    requests: float
    success_within: dict = field(default_factory=dict)
    timeline: list = field(default_factory=list)

    @property
    def served_ok(self) -> float:
        return self.served / self.users if self.users else 0.0

    @property
    def amplification(self) -> float:
        return self.requests / self.users if self.users else 0.0


def _uniform_cdf(x: float, lo: float, hi: float) -> float:
    if hi <= lo:
        return 1.0 if x >= lo else 0.0
    return min(1.0, max(0.0, (x - lo) / (hi - lo)))


def simulate(surge: Surge, users: Users, mu: float, eta: float = 1.0, dt: float = 0.25,
             deadlines=(2, 5, 10), drain_s: float = 90, queue_cap: float = 4096,
             keep_timeline: bool = False) -> Result:
    """Run the fluid model.

    mu: requests per second the design serves at saturation (its calibrated capacity).
    eta: share of mu that does useful work while the queue is long; the rest is
         spent on requests whose student has already left. 1.0 means no waste.
    queue_cap: requests that can wait; beyond that the server answers 503 at once.
    """
    steps_end = int((surge.post_release_s + drain_s) / dt)
    # Retries are grouped by first-try time in buckets of `bucket` steps, which
    # keeps the number of cohorts bounded without blurring the deadlines much.
    bucket = max(1, int(0.5 / dt))
    # Queue cohorts: [enqueue_step, first_try_step, attempt, amount]
    queue: list[list] = []
    pending: dict[int, dict[tuple[int, int], float]] = defaultdict(lambda: defaultdict(float))
    total_users = served = requests = 0.0
    within = {d: 0.0 for d in deadlines}
    timeline = []

    # Students who arrive before release reload the page every poll interval;
    # their first try after release is spread over one interval.
    pre_users = 0.0
    t = -surge.pre_release_s
    while t < 0:
        pre_users += surge.rate(t) * dt
        t += dt
    total_users += pre_users
    poll_mean = sum(users.prerelease_poll) / 2
    n_spread = max(1, int(poll_mean / dt))
    for k in range(n_spread):
        pending[k][(k, 1)] += pre_users / n_spread

    lo_d, hi_d = users.retry_delay
    n_delay = max(1, min(8, int((hi_d - lo_d) / dt)))
    delay_steps = [int((lo_d + (k + 0.5) * (hi_d - lo_d) / n_delay) / dt) for k in range(n_delay)]

    def schedule_retry(step: int, first: int, attempt: int, amount: float, prob: float) -> None:
        if attempt >= users.max_attempts or amount <= 1e-12 or prob <= 0:
            return
        fb = first - first % bucket
        share = amount * prob / n_delay
        for d in delay_steps:
            pending[step + max(1, d)][(fb, attempt + 1)] += share

    for step in range(steps_end):
        t = step * dt
        new = surge.rate(t) * dt if t <= surge.post_release_s else 0.0
        total_users += new
        arriving = [(step, 1, new)] if new > 0 else []
        for (first, attempt), amount in pending.pop(step, {}).items():
            arriving.append((first, attempt, amount))
        in_queue = sum(c[3] for c in queue)
        for first, attempt, amount in arriving:
            requests += amount
            room = max(0.0, queue_cap - in_queue)
            admitted = min(amount, room)
            rejected = amount - admitted
            if admitted > 0:
                queue.append([step, first, attempt, admitted])
                in_queue += admitted
            schedule_retry(step, first, attempt, rejected, users.retry_prob)

        # Serve FIFO from the head.
        long_queue = in_queue > mu * dt * 2
        budget = mu * dt * (eta if long_queue else 1.0)
        head = 0
        while budget > 1e-12 and head < len(queue):
            c = queue[head]
            take = min(budget, c[3])
            c[3] -= take
            budget -= take
            served += take
            age_s = (step - c[1]) * dt
            for d in deadlines:
                if age_s <= d:
                    within[d] += take
            if c[3] <= 1e-12:
                head += 1
        queue = queue[head:]

        # Impatient students leave the queue and may refresh.
        lo, hi = users.patience
        for c in queue:
            age = (step - c[0]) * dt
            f0, f1 = _uniform_cdf(age, lo, hi), _uniform_cdf(age + dt, lo, hi)
            if f1 <= f0:
                continue
            leaving = c[3] if f1 >= 1 else c[3] * (f1 - f0) / (1 - f0)
            c[3] -= leaving
            schedule_retry(step, c[1], c[2], leaving, users.impatient_retry_prob)
        queue = [c for c in queue if c[3] > 1e-9]
        if keep_timeline and step % max(1, int(1 / dt)) == 0:
            timeline.append({"t_s": t, "queue": sum(c[3] for c in queue), "arrivals_per_s": new / dt})

    return Result(users=total_users, served=served, requests=requests,
                  success_within={f"{d:g}s": within[d] / total_users if total_users else 0 for d in deadlines},
                  timeline=timeline)


def from_scenario(path_or_dict, peak: float | None = None) -> tuple[Surge, Users]:
    sc = path_or_dict if isinstance(path_or_dict, dict) else yaml.safe_load(Path(path_or_dict).read_text())
    s = sc.get("surge", {})
    u = sc.get("users", {})
    surge = Surge(peak=float(peak or s.get("peak_users_per_s", 100)), pre_release_s=s.get("pre_release_s", 60),
                  start_frac=s.get("pre_release_start_frac", 0.02), end_frac=s.get("pre_release_end_frac", 0.2),
                  rise_s=s.get("rise_s", 5), decay_tau_s=s.get("decay_tau_s", 90), floor_frac=s.get("floor_frac", 0.02),
                  post_release_s=s.get("post_release_s", 300))
    users = Users(patience=tuple(u.get("patience_s", (5, 20))), retry_prob=u.get("retry_prob", 0.8),
                  impatient_retry_prob=u.get("impatient_retry_prob", 0.9),
                  retry_delay=tuple(u.get("retry_delay_s", (1, 5))), max_attempts=u.get("max_attempts", 20),
                  prerelease_poll=tuple(u.get("prerelease_poll_s", (10, 30))))
    return surge, users


# ------------------------------------------------------------------- fit ---

def lab_points(exp_dirs: list[Path], design: str) -> list[dict]:
    """Observed outcomes and scenarios of every run of one design."""
    pts = []
    for exp in exp_dirs:
        for run in sorted(p for p in exp.iterdir() if p.is_dir()):
            meta_f, sum_f, sc_f = run / "meta.json", run / "load" / "summary.json", run / "scenario.yaml"
            if not (meta_f.exists() and sum_f.exists() and sc_f.exists()):
                continue
            meta = json.loads(meta_f.read_text())
            if meta.get("design") != design:
                continue
            s = json.loads(sum_f.read_text())
            if s["generator"]["saturated"]:
                continue
            pts.append({"run": str(run), "scenario": yaml.safe_load(sc_f.read_text()),
                        "multiple": meta.get("options", {}).get("multiple"),
                        "served_ok": s["user_served_ok"], "success_5s": s["user_success_within"].get("5s")})
    return pts


def fit(points: list[dict], mu: float, etas=None) -> dict:
    """Pick eta by grid search; report leave-one-multiple-out prediction error."""
    etas = etas or [round(0.3 + 0.05 * i, 2) for i in range(15)]

    def err(eta: float, pts: list[dict]) -> float:
        e = 0.0
        for p in pts:
            surge, users = from_scenario(p["scenario"])
            r = simulate(surge, users, mu, eta)
            e += (r.served_ok - p["served_ok"]) ** 2 + (r.success_within["5s"] - (p["success_5s"] or 0)) ** 2
        return e

    best = min(etas, key=lambda e: err(e, points))
    cv = []
    for m in sorted({p["multiple"] for p in points if p["multiple"] is not None}):
        train = [p for p in points if p["multiple"] != m]
        test = [p for p in points if p["multiple"] == m]
        if not train or not test:
            continue
        eta_m = min(etas, key=lambda e: err(e, train))
        for p in test:
            surge, users = from_scenario(p["scenario"])
            r = simulate(surge, users, mu, eta_m)
            cv.append({"multiple": m, "eta": eta_m, "observed_served_ok": p["served_ok"], "predicted_served_ok": r.served_ok,
                       "observed_success_5s": p["success_5s"], "predicted_success_5s": r.success_within["5s"]})
    mae = (sum(abs(c["observed_success_5s"] - c["predicted_success_5s"]) for c in cv) / len(cv)) if cv else None
    return {"mu": mu, "eta": best, "points": len(points), "cv": cv, "cv_mae_success_5s": mae}


# ------------------------------------------------------------------ plan ---

def required_capacity(surge: Surge, users: Users, target: float = 0.99, deadline: str = "5s", eta: float = 0.9,
                      dt: float = 1.0) -> float:
    """Smallest capacity (requests/s) for which `target` of students get a
    correct result within `deadline`."""
    lo, hi = 1.0, max(10.0, surge.peak * 4)
    while simulate(surge, users, hi, eta, dt=dt, drain_s=600).success_within[deadline] < target:
        hi *= 2
        if hi > 1e8:
            return math.inf
    for _ in range(30):
        mid = (lo + hi) / 2
        if simulate(surge, users, mid, eta, dt=dt, drain_s=600).success_within[deadline] >= target:
            hi = mid
        else:
            lo = mid
        if hi - lo < 0.01 * hi:
            break
    return hi


def plan(sizes, share_first_hour: float, tau_min: float, users: Users, cpu_costs: dict, eta: float,
         target: float, deadline: str) -> list[dict]:
    """Planning rows for real board sizes.

    The real-time surge: a share of all students checks within the first hour,
    arriving at release with an exponential decay of time constant tau_min.
    """
    rows = []
    tau = tau_min * 60
    for n in sizes:
        # Integral over the first hour of peak*exp(-t/tau) = peak*tau*(1-exp(-3600/tau)).
        peak = share_first_hour * n / (tau * (1 - math.exp(-3600 / tau)))
        surge = Surge(peak=peak, pre_release_s=600, start_frac=0.02, end_frac=0.2, rise_s=30,
                      decay_tau_s=tau, floor_frac=0.0, post_release_s=3600)
        mu = required_capacity(surge, users, target, deadline, eta)
        row = {"students": n, "peak_arrivals_per_s": round(peak, 1), "required_requests_per_s": round(mu, 1)}
        for design, cost in cpu_costs.items():
            row[f"cores_{design}"] = round(mu * cost, 2)
        rows.append(row)
    return rows


def cpu_costs_from_summary(path: Path, multiple: float = 1.0) -> dict:
    """CPU-seconds per served student for each design at a given load multiple,
    from analysis/report.py output (runs/core/report/summary.csv)."""
    import pandas as pd
    df = pd.read_csv(path)
    df = df[(df["multiple"] == multiple) & (df["label"].fillna("") == "")]
    return {r["design"]: r["cpu_s_per_1k_served"] / 1000 for _, r in df.iterrows()
            if not math.isnan(r.get("cpu_s_per_1k_served", math.nan))}


def main() -> None:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = p.add_subparsers(dest="cmd", required=True)
    s = sub.add_parser("simulate")
    s.add_argument("--scenario", required=True)
    s.add_argument("--capacity", type=float, required=True, help="requests/s at saturation")
    s.add_argument("--peak", type=float)
    s.add_argument("--eta", type=float, default=1.0)
    f = sub.add_parser("fit")
    f.add_argument("experiments", nargs="+", type=Path)
    f.add_argument("--design", required=True)
    f.add_argument("--capacity", type=float, help="default: runs/calibration/<design>/capacity.json")
    f.add_argument("--out", type=Path)
    pl = sub.add_parser("plan")
    pl.add_argument("--sizes", default="100000,500000,1000000,1500000,2500000")
    pl.add_argument("--share-first-hour", type=float, default=0.6)
    pl.add_argument("--tau-min", type=float, default=15)
    pl.add_argument("--eta", type=float, default=0.9)
    pl.add_argument("--target", type=float, default=0.99)
    pl.add_argument("--deadline", default="5s")
    pl.add_argument("--scenario", default=None, help="take the user-behaviour assumptions from this scenario")
    pl.add_argument("--cpu-costs", type=Path, help="runs/core/report/summary.csv")
    pl.add_argument("--out", type=Path)
    a = p.parse_args()

    if a.cmd == "simulate":
        surge, users = from_scenario(a.scenario, a.peak)
        r = simulate(surge, users, a.capacity, a.eta)
        print(json.dumps({"users": round(r.users), "served_ok": round(r.served_ok, 4), "amplification": round(r.amplification, 2),
                          "success_within": {k: round(v, 4) for k, v in r.success_within.items()}}, indent=2))
    elif a.cmd == "fit":
        mu = a.capacity
        if mu is None:
            cal = Path("runs/calibration") / a.design / "capacity.json"
            mu = json.loads(cal.read_text())["capacity_users_per_s"]
        res = fit(lab_points(a.experiments, a.design), mu)
        text = json.dumps(res, indent=2)
        print(text)
        if a.out:
            a.out.write_text(text + "\n")
    elif a.cmd == "plan":
        users = from_scenario(a.scenario)[1] if a.scenario else Users()
        costs = cpu_costs_from_summary(a.cpu_costs) if a.cpu_costs else {}
        rows = plan([int(x) for x in a.sizes.split(",")], a.share_first_hour, a.tau_min, users, costs, a.eta,
                    a.target, a.deadline)
        cols = list(rows[0].keys())
        md = ["| " + " | ".join(cols) + " |", "|" + "---|" * len(cols)]
        md += ["| " + " | ".join(f"{r[c]:,}" if isinstance(r[c], (int, float)) else str(r[c]) for c in cols) + " |"
               for r in rows]
        note = (f"\nAssumptions: {a.share_first_hour:.0%} of students check within the first hour, arrivals decay with "
                f"a {a.tau_min:g}-minute time constant, target {a.target:.0%} served correctly within {a.deadline}, "
                f"overload efficiency {a.eta}. Cores = required requests/s x measured CPU-seconds per served student.\n")
        text = "\n".join(md) + "\n" + note
        print(text)
        if a.out:
            a.out.write_text(text)


if __name__ == "__main__":
    main()
