#!/usr/bin/env python3
"""Animated replay of one 5x run of design A and of design C2, from their measured data.

    python paper/make_replay.py     # writes paper/figures/replay.mp4 (needs ffmpeg) and replay.gif

Uses the same paper-core runs as the paper (no refreshes): per-second counts
from load/timeseries.csv and per-student outcomes from load/users.csv.gz.
"""
from __future__ import annotations

import json
import shutil
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402
from matplotlib.animation import FFMpegWriter, FuncAnimation, PillowWriter  # noqa: E402

ROOT = Path(__file__).resolve().parent
RUNS = ROOT.parent / "resultbench" / "runs" / "paper-core"
OUT = ROOT / "figures"
FAILED = ["timeout", "server_error", "net_error", "rejected", "client_error", "missing", "wrong", "soft_failure"]
DESIGNS = [("a", "Design A: page built from the database"), ("c2", "Design C2: pre-computed static files")]
FPS, SPEED = 10, 4  # 10 frames per second of video, 4 seconds of run per second of video


def load(design: str) -> dict:
    run = sorted(RUNS.glob(f"{design}-x5-*-r1"))[0]
    ts = pd.read_csv(run / "load" / "timeseries.csv").sort_values("t_s")
    ts["failed"] = ts[[c for c in FAILED if c in ts]].sum(axis=1)
    users = pd.read_csv(run / "load" / "users.csv.gz")
    # final_ms is -1 for students who gave up; they gave up when their last
    # request ended, which the per-request log records.
    q = pd.read_csv(run / "load" / "requests.csv.gz", usecols=["user", "t_ms", "latency_ms"])
    last = (q["t_ms"] + q["latency_ms"]).groupby(q["user"]).max()
    users["end_ms"] = np.where(users["final_ms"] >= 0, users["final_ms"], users["user"].map(last))
    summary = json.loads((run / "load" / "summary.json").read_text())
    return {"run": run.name, "ts": ts, "users": users, "n": len(users),
            "served_final": summary["user_served_ok"]}


def main() -> None:
    data = {d: load(d) for d, _ in DESIGNS}
    t_min = min(v["ts"]["t_s"].min() for v in data.values())
    t_max = max(v["ts"]["t_s"].max() for v in data.values())
    times = np.arange(t_min, t_max + 1, SPEED / FPS)
    ymax = max(max(v["ts"][["arrivals", "correct", "failed"]].max()) for v in data.values()) * 1.1

    plt.rcParams.update({"font.family": "serif", "font.size": 9})
    fig, axes = plt.subplots(2, 2, figsize=(10, 5.6), gridspec_kw={"height_ratios": [3, 1.3]})
    fig.suptitle("Result day at 5$\\times$ load, same 2 CPUs: replay of two measured runs", fontsize=12)
    artists = []
    for col, (d, title) in enumerate(DESIGNS):
        top, bottom = axes[0][col], axes[1][col]
        top.set_title(title, fontsize=10)
        top.set_xlim(t_min, t_max)
        top.set_ylim(0, ymax)
        top.set_ylabel("per second")
        top.axvline(0, color="#c0392b", lw=0.8, ls="--")
        top.text(1, ymax * 0.95, "release", color="#c0392b", fontsize=8)
        top.grid(alpha=0.3)
        arr, = top.plot([], [], ":", color="k", lw=1.2, label="new students")
        ok, = top.plot([], [], "-", color="#27ae60", lw=1.6, label="correct answers")
        bad, = top.plot([], [], "-", color="#c0392b", lw=1.6, label="failed requests")
        if col == 0:
            top.legend(loc="upper right", frameon=False, fontsize=8)
        bottom.set_xlim(0, 100)
        bottom.set_yticks([])
        bottom.set_xlabel("students so far (%)")
        bars = bottom.barh([0, 0, 0], [0, 0, 0], left=[0, 0, 0], color=["#27ae60", "#c0392b", "#bdc3c7"], height=0.6)
        label = bottom.text(0.5, 1.04, "", ha="center", va="bottom", fontsize=9, transform=bottom.transAxes)
        clock = top.text(t_min + 2, ymax * 0.82, "", fontsize=10, fontweight="bold")
        artists.append((d, arr, ok, bad, bars, label, clock))
    fig.tight_layout(rect=(0, 0.04, 1, 0.95), h_pad=3.0)
    fig.text(0.5, 0.01, "Bars: green = got their result, red = gave up, grey = still waiting. "
             "Data: ResultBench paper-core runs, no refreshes.", ha="center", fontsize=8, color="#555")

    def frame(t: float):
        drawn = []
        for d, arr, ok, bad, bars, label, clock in artists:
            v = data[d]
            ts = v["ts"][v["ts"]["t_s"] <= t]
            arr.set_data(ts["t_s"], ts["arrivals"])
            ok.set_data(ts["t_s"], ts["correct"])
            bad.set_data(ts["t_s"], ts["failed"])
            u = v["users"]
            t_ms = t * 1000
            arrived = (u["arrival_ms"] <= t_ms).sum()
            done = u["end_ms"].notna() & (u["end_ms"] <= t_ms)
            served = (done & u["final"].isin(["correct", "correct_notfound"])).sum()
            gave_up = (done & ~u["final"].isin(["correct", "correct_notfound"])).sum()
            waiting = max(arrived - served - gave_up, 0)
            n = v["n"]
            widths = [100 * served / n, 100 * gave_up / n, 100 * waiting / n]
            left = 0.0
            for bar, w in zip(bars, widths):
                bar.set_x(left)
                bar.set_width(w)
                left += w
            label.set_text(f"got result {widths[0]:.0f}%   gave up {widths[1]:.0f}%   waiting {widths[2]:.0f}%")
            clock.set_text(f"t = {t:+.0f} s")
            drawn += [arr, ok, bad, *bars, label, clock]
        return drawn

    # Hold the last frame for 3 seconds of video.
    frames = list(times) + [times[-1]] * (3 * FPS)
    anim = FuncAnimation(fig, frame, frames=frames, blit=False)
    OUT.mkdir(exist_ok=True)
    if shutil.which("ffmpeg"):
        anim.save(OUT / "replay.mp4", writer=FFMpegWriter(fps=FPS, bitrate=1800))
        print("wrote", OUT / "replay.mp4")
    anim.save(OUT / "replay.gif", writer=PillowWriter(fps=FPS))
    print("wrote", OUT / "replay.gif")
    for d, _ in DESIGNS:
        print(d, data[d]["run"], "served at end of run:", round(100 * data[d]["served_final"], 1), "%")


if __name__ == "__main__":
    main()
