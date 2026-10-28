# Experiments

Each research question in the [plan](../../result-portal-research-plan.md)
maps to one experiment grid in [`bench/experiments/`](../bench/experiments).
Grids are resumable (finished runs are skipped) and run in random order.

| Grid | RQ | Designs | Varies | Key metrics | Runs (5 reps) |
|---|---|---|---|---|---|
| [`core`](../bench/experiments/core.yaml) | RQ2 | A, M, B0, C1, C2 | load 0.5×–10×; no refreshes | success within 2/5/10 s, CPU per 1k served, memory, prep time | 125 |
| [`cache`](../bench/experiments/cache.yaml) | RQ5 | B0, B1, B2, B3 | load 1×, 2×, 5×; uniform vs Zipf keys | miss types (first-time / repeat / concurrent duplicate), DB queries per student | 120 |
| [`waiting-room`](../bench/experiments/waiting-room.yaml) | RQ3 | A, C1, D-A, D-C1 (+A with double budget) | load 2×, 5×, 10×; FIFO/random × naive/token | success, wait p50/p95, Kendall's τ, refresh penalty, CPU per 1k | 165 |
| [`refresh`](../bench/experiments/refresh.yaml) | RQ6 | A, B0, C1, D-A | 4 refresh behaviours; load 2×, 5× | amplification, tail amplification, recovery time | 160 |
| [`correctness`](../bench/experiments/correctness.yaml) | RQ4 | all | corrections, invalidation, TTL, Nginx file cache, early release | wrong, stale, missing, soft failures, staleness window | 110 |
| [`faults`](../bench/experiments/faults.yaml) | robustness | B0, C1, D-C1, A | kill Redis; slow PostgreSQL 10× | recovery time, peak failure share | 25 |
| [`smoke`](../bench/experiments/smoke.yaml) | — | all | one run each | — | 9 |

## Order of work

1. Calibrate design A on the core scenario. Its capacity defines 1×.

   ```bash
   python bench/rb.py calibrate --design a
   ```

2. Calibrate the backends of the waiting-room designs (their admission rate is 80% of the backend's capacity).

   ```bash
   python bench/rb.py calibrate --design c1 --start 500 --step 500 --growth 2
   ```

3. Run the grids in the plan's priority order: core, waiting-room, correctness, cache, refresh, faults.

   ```bash
   python bench/rb.py grid bench/experiments/core.yaml
   ```

4. Analyse each grid.

   ```bash
   python -m analysis.report runs/core --recollect
   ```

## Time budget

A core-scenario run takes about 8 minutes (15 s lead, 60 s pre-release, 300 s
surge, up to 90 s drain, plus setup and materialization). The full set of
grids is about 700 runs, about 90 hours of machine time, which fits in the
Feb–Mar 2027 window of the plan with room for re-runs. Shrink factors, not
designs, if time runs short (plan section 12).

## Sensitivity runs

Assumptions in the [methodology](methodology.md) can be varied on any run:

```bash
python bench/rb.py run --design a --multiple 2 --env PAGE_COST=2ms --experiment sensitivity
```

```bash
python bench/rb.py run --design b0 --multiple 2 --set users.patience_s=[10,30] --experiment sensitivity
```

## Validating the load generator

Compare the Go generator with k6 on the same design and constant rate
([`k6/open_loop.js`](../k6/open_loop.js)). k6's arrival-rate executors space
requests evenly, so set `surge.arrivals: even` in the Go scenario for this
check (the experiments themselves use Poisson arrivals, which are burstier and
give higher tail latency at the same mean rate). With design A running:

```bash
docker run --rm --network rb-net -v "$PWD/k6:/scripts" grafana/k6:0.57.0 run -e TARGET=http://portal:8080 -e MODE=constant -e RATE=150 -e DURATION=30s -e N=50000 /scripts/open_loop.js
```

and the same load from ResultBench (`shape: constant`, `peak_users_per_s: 150`,
`arrivals: even`, no refreshes). A first check on the development machine
(design A, 50,000 students, 150 requests/s, 30 s, two repetitions each):

| Generator | p50 | p99 |
|---|---|---|
| ResultBench, even arrivals | 5.9 / 6.0 ms | 11.7 / 12.1 ms |
| k6 constant-arrival-rate | 5.9 / 6.0 ms | 12.7 / 14.0 ms |
| ResultBench, Poisson arrivals | 6.3 ms | 36.0 ms |

`bench/k6-check.sh` repeats this on the paper's machine (scenario
`bench/scenarios/k6check.yaml`: design A, 200,000 students, 150 requests/s,
30 s, no refreshes, two runs each); `paper/make_figures.py` writes the results
to `paper/generated/k6_check.csv`. On the paper's machine (Ryzen 7 5800X,
WSL2, same CPU split as the paper runs):

| Generator | p50 | p95 | p99 |
|---|---|---|---|
| ResultBench, even arrivals | 5.3 / 5.5 ms | 5.7 / 5.9 ms | 6.6 / 7.6 ms |
| k6 constant-arrival-rate | 5.4 / 5.4 ms | 5.8 / 5.8 ms | 6.2 / 6.3 ms |

## Capacity model

```bash
python -m model.capacity fit runs/core runs/refresh --design a --out runs/model-fit-a.json
```

```bash
python -m model.capacity plan --cpu-costs runs/core/report/summary.csv --out runs/planning.md
```

`fit` chooses the overload efficiency η and reports leave-one-multiple-out
prediction error; quote that error with the planning table.
