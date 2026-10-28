"""Field monitor for real result days (plan section 6.1).

A small, polite availability monitor. For every target it fetches the public
landing page (never submitting roll numbers) at most once every
`min_interval_s` seconds (15 s minimum, enforced), from about an hour before
release until a few hours after, and records timings, status, a content
fingerprint and CDN hints. Run it from at least two vantage points.

    python -m monitor.monitor run --config monitor/targets.yaml --event cbse-12-2027 --vantage home-lucknow
    python -m monitor.monitor summarize field/cbse-12-2027

Ethics (plan section 10): GET requests to public pages only, no form
submission, an identifying User-Agent with a contact address, robots.txt
respected, and a request rate far below one student's refresh rate.
"""
from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import json
import random
import re
import subprocess
import sys
import tempfile
import threading
import time
import urllib.robotparser
from pathlib import Path
from urllib.parse import urlsplit

import yaml

MIN_INTERVAL_S = 15.0  # hard floor; the config cannot go below this

CURL_FORMAT = json.dumps({
    "http_code": "%{http_code}", "time_namelookup": "%{time_namelookup}", "time_connect": "%{time_connect}",
    "time_appconnect": "%{time_appconnect}", "time_starttransfer": "%{time_starttransfer}",
    "time_total": "%{time_total}", "size_download": "%{size_download}", "remote_ip": "%{remote_ip}",
    "num_redirects": "%{num_redirects}", "url_effective": "%{url_effective}", "errormsg": "%{errormsg}",
})

# Phrases that mean "this is an error page", even when the status is 200.
SOFT_ERROR_PATTERNS = [
    r"service\s+(temporarily\s+)?unavailable", r"too\s+many\s+(requests|users)", r"server\s+is\s+(busy|overloaded)",
    r"try\s+again\s+(later|after)", r"under\s+maintenance", r"bad\s+gateway", r"gateway\s+time-?out",
    r"error\s+establishing\s+a\s+database\s+connection", r"heavy\s+traffic", r"internal\s+server\s+error",
    r"resource\s+limit", r"site\s+can.?t\s+be\s+reached", r"connection\s+timed\s+out",
]
_SOFT_RE = re.compile("|".join(SOFT_ERROR_PATTERNS), re.I)
_TITLE_RE = re.compile(rb"<title[^>]*>(.*?)</title>", re.I | re.S)
CDN_HEADERS = ["server", "via", "x-cache", "cf-ray", "cf-cache-status", "x-served-by", "x-akamai-transformed",
               "akamai-grn", "x-amz-cf-id", "x-azure-ref", "x-cdn", "age"]


def classify_body(body: bytes) -> dict:
    title = ""
    m = _TITLE_RE.search(body[:200_000])
    if m:
        title = re.sub(r"\s+", " ", m.group(1).decode("utf-8", "replace")).strip()[:200]
    text = body[:200_000].decode("utf-8", "replace")
    soft = _SOFT_RE.search(text)
    return {"title": title, "sha256": hashlib.sha256(body).hexdigest()[:16],
            "soft_error": soft.group(0).lower() if soft else ""}


def parse_headers(raw: str) -> dict:
    """Headers of the last response (after redirects), lower-cased."""
    blocks = [b for b in raw.replace("\r\n", "\n").split("\n\n") if b.strip()]
    if not blocks:
        return {}
    out = {}
    for line in blocks[-1].splitlines()[1:]:
        k, _, v = line.partition(":")
        if k.strip().lower() in CDN_HEADERS:
            out[k.strip().lower()] = v.strip()[:200]
    return out


def probe(url: str, user_agent: str, timeout_s: float) -> dict:
    with tempfile.TemporaryDirectory() as d:
        body_f, head_f = Path(d) / "body", Path(d) / "head"
        cmd = ["curl", "-sS", "-L", "--max-redirs", "5", "--max-time", str(timeout_s), "-A", user_agent,
               "-o", str(body_f), "-D", str(head_f), "-w", CURL_FORMAT, url]
        started = time.time()
        p = subprocess.run(cmd, capture_output=True, text=True)
        rec = {"ts": round(started, 3), "url": url, "curl_exit": p.returncode}
        try:
            rec.update(json.loads(p.stdout or "{}"))
        except json.JSONDecodeError:
            rec["errormsg"] = (p.stderr or "").strip()[:300]
        for k in ("time_namelookup", "time_connect", "time_appconnect", "time_starttransfer", "time_total"):
            if k in rec:
                rec[k] = float(rec[k])
        rec["http_code"] = int(rec.get("http_code", 0) or 0)
        body = body_f.read_bytes() if body_f.exists() else b""
        rec.update(classify_body(body))
        rec["headers"] = parse_headers(head_f.read_text(errors="replace")) if head_f.exists() else {}
    rec["ok"] = 200 <= rec["http_code"] < 400 and not rec["soft_error"] and rec["curl_exit"] == 0
    return rec


def robots_allows(url: str, user_agent: str) -> bool:
    parts = urlsplit(url)
    rp = urllib.robotparser.RobotFileParser(f"{parts.scheme}://{parts.netloc}/robots.txt")
    try:
        rp.read()
    except Exception:
        return True  # no robots.txt reachable: nothing disallows us
    return rp.can_fetch(user_agent, url)


def parse_time(s: str) -> float:
    return dt.datetime.fromisoformat(s).timestamp()


def run(config: dict, event_id: str, vantage: str, out_dir: Path, dry_run: bool = False) -> None:
    event = next((e for e in config["events"] if e["id"] == event_id), None)
    if event is None:
        raise SystemExit(f"event {event_id} not in config")
    targets = {t["id"]: t for t in config["targets"]}
    interval = max(MIN_INTERVAL_S, float(config.get("min_interval_s", MIN_INTERVAL_S)))
    contact = config.get("contact", "").strip()
    if not contact or "example" in contact:
        raise SystemExit("set `contact` in the config (it goes into the User-Agent so site owners can reach you)")
    ua = f"ResultBench-FieldMonitor/1.0 (academic availability study; {contact})"
    release = parse_time(event["release"])
    start = release - float(event.get("before_s", 3600))
    stop = release + float(event.get("after_s", 3 * 3600))
    out = out_dir / event_id
    out.mkdir(parents=True, exist_ok=True)
    (out / "event.json").write_text(json.dumps({**event, "vantage": vantage, "interval_s": interval,
                                                "user_agent": ua}, indent=2) + "\n")
    chosen = [targets[t] for t in event["targets"]]
    allowed = []
    for t in chosen:
        if robots_allows(t["url"], ua):
            allowed.append(t)
        else:
            print(f"robots.txt disallows {t['url']}; skipping", file=sys.stderr)
    if dry_run:
        for t in allowed:
            print(json.dumps(probe(t["url"], ua, 30)))
        return
    lock = threading.Lock()
    log_f = open(out / f"{vantage}.jsonl", "a")

    def loop(t: dict) -> None:
        # Random phase so targets are not probed in lockstep.
        time.sleep(max(0.0, start - time.time()) + random.uniform(0, interval))
        while time.time() < stop:
            rec = probe(t["url"], ua, min(30.0, interval - 1))
            rec.update({"target": t["id"], "group": t.get("group", ""), "vantage": vantage,
                        "t_rel_s": round(rec["ts"] - release, 1)})
            with lock:
                log_f.write(json.dumps(rec) + "\n")
                log_f.flush()
            time.sleep(max(0.0, interval - (time.time() - rec["ts"])))

    if time.time() < start:
        print(f"waiting until {dt.datetime.fromtimestamp(start).isoformat()} ({(start - time.time()) / 60:.0f} min)")
    threads = [threading.Thread(target=loop, args=(t,), daemon=True) for t in allowed]
    for th in threads:
        th.start()
    for th in threads:
        th.join()
    log_f.close()
    print(f"done: {out / (vantage + '.jsonl')}")


def main() -> None:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = p.add_subparsers(dest="cmd", required=True)
    r = sub.add_parser("run", help="monitor one event")
    r.add_argument("--config", type=Path, default=Path("monitor/targets.yaml"))
    r.add_argument("--event", required=True)
    r.add_argument("--vantage", required=True, help="name of this vantage point, e.g. home-lucknow")
    r.add_argument("--out", type=Path, default=Path("field"))
    r.add_argument("--dry-run", action="store_true", help="probe each target once and print")
    s = sub.add_parser("summarize", help="summarise one event directory")
    s.add_argument("event_dir", type=Path)
    a = p.parse_args()
    if a.cmd == "run":
        run(yaml.safe_load(a.config.read_text()), a.event, a.vantage, a.out, a.dry_run)
    else:
        from monitor.summarize import summarize
        print(summarize(a.event_dir))


if __name__ == "__main__":
    main()
