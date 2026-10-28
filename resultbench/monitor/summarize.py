"""Summarise the monitor's readings for one event: per-minute availability
and time to first byte per target and vantage point, failure onset,
duration and recovery, and CDN hints."""
from __future__ import annotations

import json
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import pandas as pd  # noqa: E402


def load(event_dir: Path) -> pd.DataFrame:
    rows = []
    for f in sorted(event_dir.glob("*.jsonl")):
        for line in f.read_text().splitlines():
            if line.strip():
                rows.append(json.loads(line))
    df = pd.DataFrame(rows)
    if not df.empty:
        df["minute"] = (df["t_rel_s"] // 60).astype(int)
    return df


def episodes(per_min: pd.DataFrame, threshold: float = 0.5) -> dict:
    """Failure onset (first minute at or after release with availability below
    threshold), total minutes below it, and recovery (first minute after onset
    from which availability stays at or above threshold for 5 minutes)."""
    post = per_min[per_min["minute"] >= 0].sort_values("minute")
    bad = post[post["availability"] < threshold]
    out = {"onset_min": None, "minutes_degraded": int(len(bad)), "recovered_min": None}
    if bad.empty:
        return out
    onset = int(bad["minute"].iloc[0])
    out["onset_min"] = onset
    after = post[post["minute"] > onset]
    good = (after["availability"] >= threshold).to_numpy()
    mins = after["minute"].to_numpy()
    for i in range(len(good) - 4):
        if good[i:i + 5].all():
            out["recovered_min"] = int(mins[i])
            break
    return out


def summarize(event_dir: Path) -> Path:
    df = load(event_dir)
    if df.empty:
        raise SystemExit(f"no readings in {event_dir}")
    report = event_dir / "report"
    report.mkdir(exist_ok=True)
    df["ttfb_s"] = df["time_starttransfer"].where(df["http_code"] > 0)
    per_min = (df.groupby(["target", "vantage", "minute"])
                 .agg(probes=("ok", "size"), availability=("ok", "mean"), ttfb_median_s=("ttfb_s", "median"),
                      soft_errors=("soft_error", lambda s: int((s != "").sum())),
                      status_5xx=("http_code", lambda s: int(((s >= 500) & (s < 600)).sum())),
                      no_response=("http_code", lambda s: int((s == 0).sum())))
                 .reset_index())
    per_min.to_csv(report / "per_minute.csv", index=False)

    rows = []
    for (target, vantage), g in per_min.groupby(["target", "vantage"]):
        raw = df[(df["target"] == target) & (df["vantage"] == vantage)]
        pre = raw[raw["t_rel_s"] < 0]
        post = raw[(raw["t_rel_s"] >= 0) & (raw["t_rel_s"] < 3600)]
        headers = {}
        for h in raw["headers"]:
            headers.update({k: v for k, v in (h or {}).items() if k in ("server", "via", "cf-cache-status", "x-cache")})
        rows.append({"target": target, "vantage": vantage, "probes": len(raw),
                     "availability_pre": round(pre["ok"].mean(), 3) if len(pre) else None,
                     "availability_first_hour": round(post["ok"].mean(), 3) if len(post) else None,
                     "ttfb_median_pre_s": round(pre["ttfb_s"].median(), 3) if len(pre) else None,
                     "ttfb_median_first_hour_s": round(post["ttfb_s"].median(), 3) if len(post) else None,
                     "soft_errors": int((raw["soft_error"] != "").sum()), **episodes(g),
                     "hosting_hints": "; ".join(f"{k}={v}" for k, v in headers.items())})
    summary = pd.DataFrame(rows)
    summary.to_csv(report / "summary.csv", index=False)

    for target, g in per_min.groupby("target"):
        fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(8, 5), sharex=True)
        for vantage, v in g.groupby("vantage"):
            ax1.plot(v["minute"], v["availability"], marker=".", label=vantage)
            ax2.plot(v["minute"], v["ttfb_median_s"], marker=".", label=vantage)
        for ax in (ax1, ax2):
            ax.axvline(0, color="k", ls="--", lw=1)
            ax.grid(alpha=0.3)
        ax1.set_ylabel("availability")
        ax1.set_ylim(-0.05, 1.05)
        ax2.set_ylabel("median TTFB (s)")
        ax2.set_xlabel("minutes from release")
        ax1.legend(fontsize=8)
        ax1.set_title(f"{event_dir.name}: {target}")
        fig.tight_layout()
        fig.savefig(report / f"{target}.png", dpi=150)
        plt.close(fig)

    md = [f"# {event_dir.name}\n", "Availability = share of probes with HTTP 2xx/3xx and no error-page text.\n",
          markdown_table(summary)]
    md += [f"\n![{t}]({t}.png)" for t in per_min["target"].unique()]
    (report / "README.md").write_text("\n".join(md) + "\n")
    return report


def markdown_table(df: pd.DataFrame) -> str:
    cols = list(df.columns)
    lines = ["| " + " | ".join(cols) + " |", "|" + "---|" * len(cols)]
    for _, r in df.iterrows():
        lines.append("| " + " | ".join("" if pd.isna(r[c]) else str(r[c]) for c in cols) + " |")
    return "\n".join(lines)
