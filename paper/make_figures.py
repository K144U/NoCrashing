#!/usr/bin/env python3
"""Build the paper's figures, tables and numbers from the ResultBench runs.

    python paper/make_figures.py            # reads resultbench/runs/paper-*
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
RB = ROOT.parent / "resultbench"
sys.path.insert(0, str(RB))

import matplotlib  # noqa: E402

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402

from analysis import collect, stats  # noqa: E402

RUNS = RB / "runs"
FIG = ROOT / "figures"
GEN = ROOT / "generated"
FIG.mkdir(exist_ok=True)
GEN.mkdir(exist_ok=True)

plt.rcParams.update({"font.size": 8, "axes.titlesize": 8, "axes.labelsize": 8, "legend.fontsize": 7,
                     "xtick.labelsize": 7, "ytick.labelsize": 7, "figure.dpi": 200, "font.family": "serif"})
COLORS = {"a": "#c0392b", "m": "#e67e22", "b0": "#8e44ad", "b1": "#9b59b6", "b2": "#2980b9", "b3": "#16a085",
          "c1": "#27ae60", "c2": "#2c3e50", "d-a": "#d35400", "d-c1": "#1abc9c"}
NAMES = {"a": "A", "m": "M", "b0": "B0", "b1": "B1", "b2": "B2", "b3": "B3", "c1": "C1", "c2": "C2",
         "d-a": "D-A", "d-c1": "D-C1"}
COL_W = 3.45  # IEEE column width in inches


def load(exp: str) -> pd.DataFrame:
    d = RUNS / exp
    if not d.exists():
        return pd.DataFrame()
    df = collect.collect(d)
    if df.empty:
        return df
    df.to_csv(d / "runs.csv", index=False)
    df["label"] = df["label"].fillna("")
    n_sat = int(df["generator_saturated"].sum())
    if n_sat:
        print(f"{exp}: excluding {n_sat} generator-saturated runs")
    return df[~df["generator_saturated"]]


def ci(series) -> tuple[float, float, float]:
    return stats.bootstrap_ci(pd.to_numeric(series, errors="coerce").to_numpy(float))


def agg(df: pd.DataFrame, keys: list[str], metrics: list[str]) -> pd.DataFrame:
    rows = []
    for k, g in df.groupby(keys, dropna=False):
        k = k if isinstance(k, tuple) else (k,)
        row = dict(zip(keys, k))
        row["n"] = len(g)
        for m in metrics:
            if m in g:
                row[m], row[m + "_lo"], row[m + "_hi"] = ci(g[m])
        rows.append(row)
    return pd.DataFrame(rows)


def fmt(v, lo=None, hi=None, pct=False, digits=2):
    if v is None or (isinstance(v, float) and np.isnan(v)):
        return "--"
    if pct:
        s = f"{100 * v:.1f}"
        return s
    if abs(v) >= 100:
        return f"{v:,.0f}"
    return f"{v:.{digits}f}"


def write(name: str, text: str) -> None:
    (GEN / name).write_text(text)
    print(f"wrote {GEN / name}")


numbers = {}


def cap(design: str) -> float | None:
    f = RUNS / "calibration" / design / "capacity.json"
    if f.exists():
        return json.loads(f.read_text())["capacity_users_per_s"]
    return None


# ------------------------------------------------------------------ core ---
def core() -> None:
    df = load("paper-core")
    if df.empty:
        return
    s = agg(df, ["design", "multiple"], ["success_2s", "success_5s", "served_ok", "cpu_s_per_1k_served",
                                         "latency_p99_ms", "peak_mem_mb", "db_queries_per_user", "prep_seconds"])
    s.to_csv(GEN / "core_summary.csv", index=False)
    fig, axes = plt.subplots(1, 2, figsize=(COL_W * 2, 2.1))
    for d in ["a", "m", "b0", "c1", "c2"]:
        g = s[s["design"] == d].sort_values("multiple")
        if g.empty:
            continue
        for ax, m in zip(axes, ["success_5s", "cpu_s_per_1k_served"]):
            y = g[m].to_numpy(float)
            err = np.vstack([y - g[m + "_lo"].to_numpy(float), g[m + "_hi"].to_numpy(float) - y])
            ax.errorbar(g["multiple"], y, yerr=np.abs(np.nan_to_num(err)), marker="o", ms=3, capsize=2,
                        color=COLORS[d], label=NAMES[d])
    axes[0].set_ylabel("students served correctly\nwithin 5 s")
    axes[0].set_ylim(-0.03, 1.03)
    axes[1].set_ylabel("CPU-seconds per 1000\nstudents served")
    axes[1].set_yscale("log")
    for ax in axes:
        ax.set_xscale("log")
        ax.set_xticks([1, 2, 5, 10])
        ax.set_xticklabels(["1x", "2x", "5x", "10x"])
        ax.set_xlabel("peak arrival rate (multiple of A's capacity)")
        ax.grid(alpha=0.3)
    axes[0].legend(ncol=5, loc="lower left", frameon=False)
    fig.tight_layout()
    fig.savefig(FIG / "core.pdf")
    plt.close(fig)

    lines = [r"\begin{table}[t]", r"\caption{Students served correctly within 5\,s (\%) and CPU-seconds per 1000 served, median of 3 runs}",
             r"\label{tab:core}", r"\centering", r"\footnotesize", r"\setlength{\tabcolsep}{3pt}",
             r"\begin{tabular}{@{}l" + "rr" * 4 + "@{}}", r"\toprule"]
    mults = [1, 2, 5, 10]
    lines.append(" & " + " & ".join(rf"\multicolumn{{2}}{{c}}{{{m}$\times$}}" for m in mults) + r" \\")
    lines.append(" ".join(rf"\cmidrule(lr){{{2 + 2 * i}-{3 + 2 * i}}}" for i in range(4)))
    lines.append("Design & " + " & ".join(["5\\,s \\%", "CPU"] * 4) + r" \\")
    lines.append(r"\midrule")
    for d in ["a", "m", "b0", "c1", "c2"]:
        cells = []
        for m in mults:
            r = s[(s["design"] == d) & (s["multiple"] == m)]
            if r.empty:
                cells += ["--", "--"]
            else:
                r = r.iloc[0]
                cells += [fmt(r["success_5s"], pct=True), fmt(r["cpu_s_per_1k_served"], digits=1)]
        lines.append(NAMES[d] + " & " + " & ".join(cells) + r" \\")
    lines += [r"\bottomrule", r"\end{tabular}", r"\end{table}"]
    write("tab_core.tex", "\n".join(lines) + "\n")


# ------------------------------------------------------------ waiting room ---
def waiting_room() -> None:
    df = load("paper-wr")
    if df.empty:
        return
    s = agg(df, ["design", "label"], ["success_5s", "success_10s", "served_ok", "wait_p50_ms", "wait_p95_ms",
                                      "kendall_tau", "kendall_tau_prerelease", "refresh_penalty_ms",
                                      "backend_amplification", "amplification", "cpu_s_per_1k_served", "wr_abandoned",
                                      "time_to_result_p50_ms", "time_to_result_p95_ms"])
    s.to_csv(GEN / "wr_summary.csv", index=False)
    order = [("a", ""), ("d-a", "fifo-token"), ("d-a", "fifo-naive"), ("d-a", "random-token"), ("d-a", "random-naive"),
             ("c1", ""), ("d-c1", "fifo-token"), ("d-c1", "fifo-naive"), ("d-c1", "random-token"), ("d-c1", "random-naive")]
    lines = [r"\begin{table*}[t]", r"\caption{Waiting rooms at 5$\times$ load with refreshing students (median of 3 runs). "
             r"Wait: from first request after release until admitted. $\tau$: Kendall's rank correlation between arrival and admission order "
             r"(1 = first-come-first-served). Refresh penalty: median extra wait of students who pressed refresh.}",
             r"\label{tab:wr}", r"\centering", r"\footnotesize",
             r"\begin{tabular}{@{}llrrrrrrrr@{}}", r"\toprule",
             r"Backend & Waiting room & \multicolumn{3}{c}{Served correctly (\%)} & Wait p50 & Wait p95 & $\tau$ (early arrivals) & Refresh penalty & CPU s / 1000 \\",
             r"\cmidrule(lr){3-5}", r" & & 5\,s & 10\,s & at all & (s) & (s) & & (s) & \\", r"\midrule"]
    for d, lab in order:
        r = s[(s["design"] == d) & (s["label"] == lab)]
        if r.empty:
            continue
        r = r.iloc[0]
        backend = "A" if d in ("a", "d-a") else "C1"
        wr = "none" if lab == "" else lab.replace("-", ", ")
        tau = r.get("kendall_tau_prerelease")
        lines.append(f"{backend} & {wr} & {fmt(r['success_5s'], pct=True)} & {fmt(r['success_10s'], pct=True)} & "
                     f"{fmt(r['served_ok'], pct=True)} & {fmt(r['wait_p50_ms'] / 1000, digits=1)} & "
                     f"{fmt(r['wait_p95_ms'] / 1000, digits=1)} & {fmt(tau)} & "
                     f"{fmt(r['refresh_penalty_ms'] / 1000, digits=1)} & {fmt(r['cpu_s_per_1k_served'], digits=1)} \\\\")
        if (d, lab) == ("d-a", "random-naive"):
            lines.append(r"\midrule")
    lines += [r"\bottomrule", r"\end{tabular}", r"\end{table*}"]
    write("tab_wr.tex", "\n".join(lines) + "\n")


# ------------------------------------------------------------- correctness ---
def correctness() -> None:
    df = load("paper-correct")
    if df.empty:
        return
    for c in ["stale", "wrong", "missing", "soft_failures", "staleness_window_s", "stale_responses"]:
        if c not in df:
            df[c] = np.nan
    s = agg(df, ["design", "label"], ["stale", "wrong", "missing", "soft_failures", "staleness_window_s", "served_ok",
                                      "requests"])
    s.to_csv(GEN / "correct_summary.csv", index=False)
    order = [("a", "", "corrections"), ("b0", "invalidate", "corrections, entries deleted"),
             ("b0", "no-invalidate", "corrections, no invalidation (TTL 10 min)"), ("c1", "", "corrections, entries rewritten"),
             ("c2", "ofc-30s", "corrections, Nginx file cache 30 s"), ("c2", "ofc-1s", "corrections, Nginx file cache 1 s"),
             ("c1", "early-90", "release with 90\\% pre-computed"), ("c2", "early-90", "release with 90\\% pre-computed")]
    lines = [r"\begin{table}[t]", r"\caption{Correctness at 1$\times$ load, median of 3 runs. Corrections for 1\% of students are published 30\,s after release.}",
             r"\label{tab:correct}", r"\centering", r"\footnotesize", r"\setlength{\tabcolsep}{2.5pt}",
             r"\begin{tabular}{@{}lp{3.1cm}rrrr@{}}", r"\toprule",
             r"Design & Condition & Stale & Stale for (s) & Missing & Wrong \\", r"\midrule"]
    for d, lab, desc in order:
        r = s[(s["design"] == d) & (s["label"] == lab)]
        if r.empty:
            continue
        r = r.iloc[0]
        lines.append(f"{NAMES[d]} & {desc} & {fmt(r['stale'], digits=0)} & {fmt(r['staleness_window_s'], digits=1)} & "
                     f"{fmt(r['missing'], digits=0)} & {fmt(r['wrong'], digits=0)} \\\\")
    lines += [r"\bottomrule", r"\end{tabular}", r"\end{table}"]
    write("tab_correct.tex", "\n".join(lines) + "\n")


# ------------------------------------------------------------------ cache ---
def cache() -> None:
    df = load("paper-cache")
    if df.empty:
        return
    miss = ["portal_cache_miss_first_time_key", "portal_cache_miss_repeat_key", "portal_cache_miss_concurrent_duplicate"]
    s = agg(df, ["design", "label"], miss + ["success_5s", "served_ok", "db_queries_per_user", "portal_coalesced",
                                             "portal_cache_hits", "users", "cpu_s_per_1k_served"])
    s.to_csv(GEN / "cache_summary.csv", index=False)
    fig, axes = plt.subplots(1, 2, figsize=(COL_W * 2, 2.0))
    designs = ["b0", "b1", "b2", "b3"]
    x = np.arange(len(designs))
    for ax, lab in zip(axes, ["uniform", "zipf"]):
        bottom = np.zeros(len(designs))
        for col, name, color in zip(miss, ["first time for key", "repeat key", "concurrent duplicate"],
                                    ["#7f8c8d", "#2980b9", "#c0392b"]):
            vals = []
            for d in designs:
                r = s[(s["design"] == d) & (s["label"] == lab)]
                users = r["users"].iloc[0] if len(r) else np.nan
                vals.append(r[col].iloc[0] / users if len(r) and users else 0)
            ax.bar(x, vals, bottom=bottom, color=color, label=name, width=0.6)
            bottom += np.array(vals)
        ax.set_xticks(x)
        ax.set_xticklabels([NAMES[d] for d in designs])
        ax.set_title("uniform keys (each student once)" if lab == "uniform" else "Zipf keys (s = 1.2)")
        ax.set_ylabel("cache misses per student")
        ax.grid(axis="y", alpha=0.3)
    axes[0].legend(frameon=False, loc="upper right")
    fig.tight_layout()
    fig.savefig(FIG / "cache.pdf")
    plt.close(fig)


# ---------------------------------------------------------------- refresh ---
def refresh() -> None:
    df = load("paper-refresh")
    if df.empty:
        return
    s = agg(df, ["design", "label"], ["amplification", "backend_amplification", "tail_amplification", "served_ok",
                                      "success_10s", "recovery_s", "peak_failure_share"])
    s.to_csv(GEN / "refresh_summary.csv", index=False)
    # Time series of one run per behaviour for design A: backend requests vs arrivals.
    fig, axes = plt.subplots(1, 3, figsize=(COL_W * 2, 1.9), sharey=True)
    for ax, lab in zip(axes, ["no-refresh", "default", "impatient"]):
        for d, ls in [("a", "-"), ("d-a", "--")]:
            runs = df[(df["design"] == d) & (df["label"] == lab)].sort_values("rep")
            if runs.empty:
                continue
            ts = pd.read_csv(RUNS / "paper-refresh" / runs["run"].iloc[0] / "load" / "timeseries.csv")
            ts = ts[ts["t_s"] >= -5]
            ax.plot(ts["t_s"], ts["backend"].rolling(3, min_periods=1).mean(), ls, color=COLORS[d], lw=1,
                    label=f"{NAMES[d]}: requests reaching the server")
            if d == "a":
                ax.plot(ts["t_s"], ts["arrivals"].rolling(3, min_periods=1).mean(), ":", color="k", lw=1,
                        label="new students")
        ax.set_title({"no-refresh": "no refreshes", "default": "default students", "impatient": "impatient students"}[lab])
        ax.set_xlabel("seconds after release")
        ax.grid(alpha=0.3)
    axes[0].set_ylabel("per second")
    axes[0].legend(frameon=False, fontsize=6, loc="upper right")
    fig.tight_layout()
    fig.savefig(FIG / "refresh.pdf")
    plt.close(fig)


def main() -> None:
    core()
    waiting_room()
    correctness()
    cache()
    refresh()
    ca, cc = cap("a"), cap("c1")
    macros = [rf"\newcommand{{\CapA}}{{{ca:.0f}}}" if ca else r"\newcommand{\CapA}{??}",
              rf"\newcommand{{\CapCOne}}{{{cc:,.0f}}}" if cc else r"\newcommand{\CapCOne}{??}"]
    write("numbers.tex", "\n".join(macros) + "\n")


if __name__ == "__main__":
    main()
