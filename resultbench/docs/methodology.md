# Methodology

This page documents every modelling choice in ResultBench, so the thesis can
state its assumptions and an examiner can check them. Section numbers refer to
the [research plan](../../result-portal-research-plan.md).

## 1. System under test

### 1.1 Same budget for every design (plan 7.5)

The read path of every design gets **2 CPUs and the same memory limits**, on the
same two cores (`SUT_CPUSET`, default `0,1`). The load generator runs on other
cores (`RB_LOADGEN_CPUSET`, default `2,3`); the runner refuses to start if they
overlap. The paper runs used `RB_SUT_CPUSET=2,3` (both hardware threads of one
physical core) and `RB_LOADGEN_CPUSET=4-15` on an 8-core, 16-thread machine,
leaving core 0 to the operating system; the values are recorded in
`runs/paper-cpuset.env`. The split per design is in [`bench/designs.yaml`](../bench/designs.yaml):

| Design | Allocation (CPUs) |
|---|---|
| A | app 1.0, PostgreSQL 1.0 |
| M | 2 × (app 0.5 + PostgreSQL 0.5) |
| B0–B3 | app 0.75, PostgreSQL 0.75, Redis 0.5 |
| C1 | app 1.0, Redis 1.0 (PostgreSQL 0.25, back office, idle during the run) |
| C2 | Nginx 2.0 (PostgreSQL 0.25, back office) |
| D-A | waiting room 0.25, app 0.875, PostgreSQL 0.875 |
| D-C1 | waiting room 0.25, app 0.875, Redis 0.875 |
| D-C2 | waiting room 0.25, Nginx 1.75 |

Back-office PostgreSQL in C designs is measured and reported in the cost
columns even though it is idle while students read results.

### 1.2 Server behaviour (fixed tuning budget, plan 7.5)

All application designs use one Go binary (`rb portal`) with the same settings:

| Setting | Value | Why |
|---|---|---|
| `MAX_WORKERS` | 256 | Bounded worker pool, as PHP-FPM `max_children` or Apache `MaxRequestWorkers`. Without it the server accepts unbounded work and is OOM-killed under overload. |
| `MAX_QUEUE` | 4096 | Requests waiting for a worker; beyond it the server answers 503 at once (a full listen backlog). |
| `PAGE_COST` | 5 ms CPU | **Assumption.** CPU to build one page from the database: framework, session handling, rendering. Real portal stacks spend milliseconds here; the Go server alone spends microseconds, which would make design A unrealistically cheap. Paid on every request in A and M, and on every cache miss in B; pre-computed designs store the finished page. Vary it (`PAGE_COST=0`, `2ms`, `10ms`) in a sensitivity run. |
| `CANCEL_ON_DISCONNECT` | false | Work already started continues after the student gives up, as in most stacks; requests still waiting for a worker are dropped when their client leaves. |
| `DB_MAX_CONNS` | 16 | Connection pool per app instance. |
| PostgreSQL | `shared_buffers=256MB`, `synchronous_commit=off` | Same for every design. |
| Cache TTL | 10 min | B designs; `TTL_JITTER=0.1` in B2. |
| Nginx | `open_file_cache_valid 30s` | C2; also a staleness source after corrections. |

Changing any of these is a configuration change recorded in `meta.json` for
the run.

### 1.3 Results data

Synthetic, deterministic: every student's record is a function of
`(seed, index)` ([`internal/dataset`](../internal/dataset/dataset.go)). One
million students by default; 1% receive a revised result (re-totalling) when
corrections are published. No real student data is used anywhere.

## 2. Workload (plan 7.2)

### 2.1 Open-loop arrivals

New students arrive as a Poisson process whose rate follows the surge curve,
independent of how fast the system answers (Schroeder, Wierman and
Harchol-Balter, NSDI 2006). With refreshes added, the workload is "partly
open" in their terms. Arrivals are Poisson by default (`surge.arrivals:
poisson`); `even` spaces them uniformly, as k6 does, for cross-checks. The
generator reports dropped arrivals when its own
limits are reached and marks a run as saturated if its CPU use exceeds 90%
of its cores or it runs out of local ports or file descriptors; such runs
are excluded from analysis.

The generator container uses local ports 1024–65535 and reuses ports in
TIME_WAIT (`net.ipv4.ip_local_port_range`, `net.ipv4.tcp_tw_reuse`, set in
`loadgen_cmd` in `bench/rb.py`). With Linux's default range (32768–60999),
all six paper waiting-room runs of D-A with token tickets at 5× ran out of
ports while draining (625 to 13,587 failed connections each) and were marked
saturated. The setting was added after `paper-core` and `paper-wr` had run;
`paper-correct`, `paper-cache` and `paper-refresh` used it, and the six
saturated runs were deleted and rerun with it. It cannot change a run that does
not run out of ports, so runs with and without it are comparable.

### 2.2 Surge shape

```
rate(t) = peak × (start_frac → end_frac)          for −pre_release_s ≤ t < 0   (linear ramp)
        = peak × (end_frac → 1)                   for 0 ≤ t < rise_s
        = floor + (peak − floor) × exp(−(t − rise_s)/τ)   afterwards
```

`peak` is set per run as a **multiple of design A's calibrated capacity**
(0.5×, 1×, 2×, 5×, 10×), so results are relative and do not depend on the
machine. Anchors for choosing multiples: about 5× offered load over capacity
at JEE Advanced 2016 (10,000 vs 2,000 requests/s, per the chairman), 5–10×
pre-event ramps in the World Cup '98 trace, about 4× previous peak at UCAS 2011.

Time is compressed: τ = 90 s in the core scenario, against 30–60 minutes on a
real result day. Replace the shape with the fitted field-study curve once
Study 1 data exists.

### 2.3 Students (human refresh model)

Every value is an assumption; no study has measured refresh behaviour on
result day. The refresh grid varies them.

| Parameter | Default | Meaning |
|---|---|---|
| `patience_s` | 5–20 s | Wait before giving up on a response and refreshing (per student, uniform) |
| `retry_prob` | 0.8 | Refresh after an error page |
| `impatient_retry_prob` | 0.9 | Refresh after patience ran out |
| `retry_delay_s` | 1–5 s | Pause before refreshing |
| `max_attempts` | 20 | Then give up |
| `prerelease_poll_s` | 10–30 s | Reload interval for students who arrive before release |
| `queue_manual_refresh_per_min` | 0.5 | Manual refreshes while in a waiting room (naive tickets are lost on refresh) |
| `repeat_view_prob` | 0.1 | Look again later after seeing the result |
| Keys | uniform | Each arriving student is a different student (sampling without replacement); `zipf` makes some keys hot |
| `typo_rate` | 1% | Roll numbers that do not exist (correct answer: 404) |

### 2.4 Calibration

`rb calibrate` sends constant-rate steps (no refreshes, results already
released) and reports the highest rate at which 99% of students get a correct
result within 2 s, refined by bisection. If the generator saturates first, the
capacity is reported as a lower bound (`generator_limited`).

## 3. Correctness oracle (plan 7.3)

Every response is classified against ground truth
([`internal/oracle`](../internal/oracle/oracle.go)):

| Outcome | Meaning |
|---|---|
| correct | Expected current result (or 404 for a non-existent roll number) |
| stale | The old version after corrections were published |
| wrong | Another student's result or altered marks |
| missing | 404 for a roll number that exists (e.g. release before pre-computation finished) |
| soft_failure | HTTP 200 whose body is not a result |
| not_released / queued | Gate or waiting room, not a failure |
| rejected / server_error / timeout / net_error | Availability failures |

## 4. Metrics (plan 7.6)

| Metric | Definition |
|---|---|
| success within D | Share of students who got a correct answer within D seconds of their first request after release |
| served_ok | Share of students who got a correct answer at all |
| time to result | From first request after release to correct answer |
| amplification | Requests per student; `backend_amplification` excludes gate and queue responses |
| tail_amplification | Backend requests per new arrival in the last quarter of the run; well above 1 means a self-sustaining overload |
| recovery_s | First second after the rise from which the failure share stays below 1% for 10 s |
| cpu_s_per_1k_served | CPU-seconds of all containers per 1,000 students served |
| wait, Kendall's τ, refresh penalty | Waiting-room wait, arrival-vs-service order, extra wait of students who refreshed |
| staleness window | Last stale response minus correction publication time |
| miss types | First-time key, repeat key, concurrent duplicate (RQ5) |

Repetitions: 5 per configuration; tables report the median with a 95%
percentile-bootstrap interval. Run order within a grid is randomised.

## 5. Known limitations

See plan section 9. Specific to this implementation: one machine and one
generator; no real CDN or WAN; the page cost is a model, not a real framework;
the waiting room is a single in-memory instance; corrections change marks only
(ranks are not shown on the marksheet, so no other student's result changes).
