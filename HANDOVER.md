# Handover: NoCrashing / "Surviving Result Day"

Written 28 Oct 2026 at the end of a cloud Claude Code session, for a Claude Code
session on the author's own machine. Read this file fully before doing
anything. `CLAUDE.md` holds the short, durable rules; this file holds the
state, history and next steps.

Branch with all work: **`claude/awesome-fermi-7ckuzk`** on `K144U/NoCrashing`.

```bash
git fetch origin claude/awesome-fermi-7ckuzk
```

```bash
git checkout claude/awesome-fermi-7ckuzk
```

---

## 1. The project in one paragraph

Sankalp Pathak (M.Tech CSE, AKTU Lucknow) is writing a thesis on why
examination-result websites crash on result day and what fixes them. The
software, **ResultBench**, builds the same result portal in eleven designs
(database-backed, mirrors, cache-aside variants, pre-computed key-value,
pre-computed static files, and virtual waiting rooms in front of them), gives
every design the same 2-CPU budget, replays a result-day surge with an
open-loop load generator that models how students refresh, and checks every
response against ground truth. **The immediate goal is a paper, as fast as
possible.** The author has no time for RTI requests, and the 2027 field season
has not happened, so the paper is **lab-only**; the field study, RTI and
capacity-model validation are future work.

## 2. Repository map

| Path | What |
|---|---|
| `result-portal-research-plan.md` | Thesis plan v2 (problem, gap, RQs, three studies, timeline). The old v1 plan was deleted on request. |
| `reports/Result portal gap analysis check.md` | Literature/evidence check behind the gap statement. Key facts in section 6 below. |
| `research_notes/Result portal gap analysis check/` | Raw notes from that check. |
| `resultbench/` | All software. Start with `resultbench/README.md`. |
| `resultbench/docs/methodology.md` | Every design budget, server setting and workload assumption. **The source of truth for the paper's method section.** |
| `resultbench/docs/experiments.md` | Which grid answers which RQ; generator validation vs k6. |
| `resultbench/bench/rb.py` | Experiment runner (build, seed, calibrate, run, grid, down, monitor). |
| `resultbench/bench/designs.yaml` | Design definitions and CPU budgets. |
| `resultbench/bench/scenarios/paper.yaml` | **Scenario used for the paper** (200k students, compressed 90 s surge). |
| `resultbench/bench/experiments/paper/*.yaml` | **The five paper grids** (156 runs, 3 reps). |
| `resultbench/bench/paper-run.sh` | Runs calibration + all paper grids in priority order. Resumable. |
| `paper/` | The paper: `main.tex`, `sections/*.tex`, `refs.bib`, `make_figures.py`. |
| `resultbench/ci/github-workflow.yml` | CI workflow. **Not active**: the cloud session could not push to `.github/workflows/` (token lacked `workflow` scope). Copy it to `.github/workflows/resultbench.yml` to enable. |

Inside `resultbench/`: `cmd/rb` (one Go binary, subcommands `portal`,
`waitingroom`, `surge`, `calibrate`, `dbload`, `materialize`, `correct`,
`release`, `publish-csv`, `sample`, `fetch`), `internal/` (dataset, oracle, db,
portal, publish, wroom, surge, metrics), `deploy/compose` (one file per
design), `deploy/nginx`, `deploy/result-in-a-box` (production reference
deployment), `analysis/` (collect, bootstrap, report), `model/capacity.py`,
`monitor/` (field monitor), `k6/`, `tests/`.

## 3. Set up on the local machine

Requirements:

- Docker Engine or Docker Desktop with Compose v2. **At least 4 CPU cores** (2 for the system under test, 2 for the load generator), 8 GB RAM, about 10 GB disk.
  - Windows: run everything inside WSL2 (Ubuntu), with the repository on the WSL filesystem, not `/mnt/c`.
  - macOS: works, but `cpuset` pinning is approximate inside the Docker VM. Results are still comparable between designs on the same machine.
- Python 3.10+.
- Go 1.24 (only for unit tests outside Docker).
- TeX Live with `IEEEtran`, `siunitx`, `booktabs` and `latexmk`. On Ubuntu: `texlive-latex-recommended`, `texlive-latex-extra`, `texlive-fonts-recommended`, `texlive-publishers`, `texlive-science`, `latexmk`.

From `resultbench/`:

```bash
pip install -r requirements.txt
```

```bash
python bench/rb.py build
```

The Dockerfile uses `vendor/` if present (it is gitignored) and otherwise
downloads Go modules during the build, which is fine with normal internet.

If the machine has more than 4 cores, give the generator more of them and
**keep the same values for every run**:

```bash
export RB_SUT_CPUSET=0,1 RB_LOADGEN_CPUSET=2-7
```

## 4. Verify before running experiments

Run these and confirm each one passes before doing anything else.

1. Unit tests (Go and Python):

   ```bash
   go test ./...
   ```

   ```bash
   python -m pytest -q tests
   ```

2. A 2-minute end-to-end run (this is what CI does):

   ```bash
   python bench/rb.py run --design c2 --capacity 100 --multiple 1 --scenario bench/scenarios/quick.yaml --experiment ci --name c2
   ```

   Expect `served_ok` ≈ 1.0, `wrong=0`, `stale=0`.

3. Optional: the smoke grid, every design once at 2×, about 25 minutes.

   ```bash
   make smoke
   ```

   **Run it before the paper grids, never while they run or between them.** It
   recalibrates design A on the small quick scenario and overwrites
   `runs/calibration/a/`. `paper-run.sh` notices and recalibrates on the paper
   scenario, but a grid half-run with one capacity and resumed with another
   mixes load levels.

What to look for in any run's `runs/<exp>/<run>/load/summary.json`:

- `wrong_requests` must be 0. Anything else is a bug: stop and investigate.
- `missing_requests` > 0 outside the early-release experiment means a bug (see the Nginx incident in section 7).
- `generator.saturated: true` means the run is invalid: the load generator, not the design, was the bottleneck. The analysis excludes such runs automatically. If many runs saturate, give the generator more cores.
- `meta.json` → `containers`: `oom_killed` or a non-running state means a service crashed. That is a legitimate outcome, but check it isn't a configuration error.

## 5. Run the paper experiments

```bash
cd resultbench
```

```bash
nohup bench/paper-run.sh > runs/paper.log 2>&1 &
```

It calibrates design A (whose capacity defines 1×) and design C1 on the paper
scenario, then runs the grids in priority order:

| Grid | Runs | Answers |
|---|---|---|
| `paper-core` | 60 | RQ1: A, M, B0, C1, C2 at 1×, 2×, 5×, 10×, no refreshes |
| `paper-wr` | 30 | RQ2: A and C1 alone vs D-A and D-C1 with 4 waiting-room configs (FIFO/random × naive/token tickets) at 5× |
| `paper-correct` | 24 | RQ3: corrections 30 s after release (invalidation on/off, Nginx file cache 30 s/1 s), release with only 90% pre-computed |
| `paper-cache` | 24 | RQ4a: B0–B3 at 2×, uniform vs Zipf keys, miss decomposition |
| `paper-refresh` | 18 | RQ4b: A and D-A at 2× with no / default / impatient refreshers |

About 2.5 minutes per run, so **about 6.5 hours** on a 4-core machine. It
is resumable: finished runs (those with `load/summary.json`) are skipped, so
kill it and rerun freely. Monitor with:

```bash
grep -E "progress|: users=|failed" runs/paper.log | tail
```

Do not change any design setting, scenario value or budget while a grid is
running. If one must change, delete the affected grid's `runs/<grid>/`
directory and rerun it, so every run in a comparison used the same settings.

## 6. Build the paper

```bash
python paper/make_figures.py
```

From `paper/`:

```bash
latexmk -pdf main.tex
```

`make_figures.py` collects `resultbench/runs/paper-*`, excludes saturated
runs, computes medians with 95% bootstrap intervals, and writes:

- `paper/figures/core.pdf`: success within 5 s and CPU per 1,000 served, against load multiple.
- `paper/figures/cache.pdf`: cache misses per student by type.
- `paper/figures/refresh.pdf`: requests reaching the server against new arrivals over time.
- `paper/generated/tab_core.tex`, `tab_wr.tex`, `tab_correct.tex`: tables.
- `paper/generated/*_summary.csv`: every aggregated number, for writing the text.
- `paper/generated/numbers.tex`: `\CapA`, `\CapCOne`.

### State of the paper

| Section | File | State |
|---|---|---|
| Title, author | `main.tex` | Done. **TODO:** add mentor as co-author and an email. |
| Abstract | `sections/abstract.tex` | **Placeholder.** Write last, from results. |
| I. Introduction | `sections/intro.tex` | Drafted. Check the contributions still match the results. |
| II. Related work | `sections/related.tex` | Drafted. |
| III. Designs | `sections/designs.tex` | Drafted (Table I). |
| IV. Methodology | `sections/method.tex` | Drafted. Uses `\CapA`. Update the testbed line (CPU model, cores, RAM, Docker version) for the local machine. Replace the k6 validation numbers with a re-run on the local machine (see `resultbench/docs/experiments.md`). |
| V. Results | `sections/results.tex` | **Placeholder.** Needs one subsection per RQ, each with `\input{generated/tab_*.tex}` or `\includegraphics{figures/*.pdf}`. It must define `\label{sec:refresh}`, which the method and threats sections reference. |
| VI. Discussion | `sections/discussion.tex` | **Placeholder.** Recommendations for boards, then `\input{sections/threats.tex}` (already written). |
| VII. Conclusion | `sections/conclusion.tex` | **Placeholder.** Include future work: 2027 field study, RTI data, validating the capacity model, real framework stacks. |

**Writing rule: every number in the text must come from
`paper/generated/*_summary.csv` or the tables.** Do not use the cloud-session
numbers in section 8 in the paper; they are from a different machine and some
are from the short smoke scenario.

Suggested results structure (what each table or figure shows):

- **RQ1** (`tab_core`, `core.pdf`): at which multiple each design drops below 99% within 5 s, and CPU per 1,000 served. Also prep time for C1 and C2 (`prep_seconds`). M (mirrors) shows whether splitting the same budget across links helps.
- **RQ2** (`tab_wr`): whether D-A beats A at 5× (served at all, within 10 s); what D-C1 adds or costs over C1 (extra wait for no benefit is a valid finding); FIFO vs random (τ near 1 vs near 0); naive vs token (refresh penalty, abandoned tickets).
- **RQ3** (`tab_correct`): stale responses and staleness window per design. The expectation is that A is always fresh, B0 without invalidation stays stale until TTL, and C2 can be stale up to the Nginx `open_file_cache_valid`. Missing results under early release. Report whatever the data shows, not these expectations.
- **RQ4** (`cache.pdf`, `refresh.pdf`, `cache_summary.csv`, `refresh_summary.csv`): with uniform keys, misses should be almost all "first time for key", so coalescing (B1) and XFetch (B2) change little and only pre-warming (B3) helps; with Zipf keys, duplicates appear. Amplification (requests per student) and `tail_amplification` per refresh behaviour; whether D-A keeps backend load bounded.
- **Anecdote worth one paragraph** (section 7): the Nginx descriptor exhaustion that turned an overloaded static site into "404 for students who exist", caught only because of the correctness oracle. The run is preserved in `resultbench/runs/paper-anecdote/c2-x10-fd-exhaustion/` on the cloud machine only; reproduce it locally by setting `open_file_cache max=200000` in `deploy/nginx/result.conf.template` with a low `nofile` limit, if you want it in the paper.

### Bibliography: check before submission

Entries in `paper/refs.bib` marked `% check` were not read in full. Confirm them:
- The two Indonesian papers (Putranto & Pinandito 2026, J-PTIIK; Tofan et al. 2026, JIP) are the closest prior work. Read the full texts and confirm they do not test pre-computed designs, check correctness or measure cost; the intro's gap sentence depends on it.
- Fill in "and others" author lists (Nishtala, Zhou/DAGOR, Papadopoulos, Uta) from the publishers' pages.
- Press items (PaGaLGuY 2016, Hindustan Times 2021, The Standard/KNEC, ICIR/WAEC): open each, confirm wording and dates, and archive a copy.
- Target venue: unchosen. IEEEtran conference format is used. Candidates from the plan: ACM/SPEC ICPE, COMSNETS, ACM ICEGOV, or an arXiv preprint first.

## 7. Decisions and incidents so far (why things are the way they are)

1. **Gap analysis** (`reports/`): the original "nobody compared result-portal architectures" claim was too broad. Two 2026 Indonesian papers compare DB vs Redis cache-aside on university portals. Classic work compared on-demand, cached and pre-generated pages (Labrinidis & Roussopoulos, SIGMOD 2000). Retry collapse is well studied (Huang et al., OSDI 2022). What remains new: waiting-room evaluation (no peer-reviewed study found), correctness under load, miss-ratio vs stampede for per-student keys, the combination in one reproducible harness, and (later) field data. The NIC Odisha figures, the "Baroro" paper and a LinkedIn "post" from the v1 plan could not be verified and were removed.
2. **Same budget**: 2 CPUs for every design's read path; the split is in `designs.yaml`. Back-office PostgreSQL in C designs gets 0.25 CPU, idle, and is still counted in cost.
3. **`PAGE_COST=5ms`**: without it, design A served about 5,000 students/s on 2 CPUs (a Go server is far leaner than real PHP/ASP.NET portals), and 10× of that was beyond what one load generator can produce. It is spent where a page is built from the database (every request in A/M, every miss in B). It is an explicit, documented assumption; a sensitivity run with `--env PAGE_COST=2ms` and `0` would strengthen the paper.
4. **Worker pool 256, queue 4096**: without a bound, design A accepted unlimited work under overload and was OOM-killed at 512 MB. Real servers bound workers; requests waiting for a worker are dropped when the client leaves, while started work continues (`CANCEL_ON_DISCONNECT=false`).
5. **Deadlines are measured from a student's first request after release**, not from arrival: early arrivals only see results at their next reload, which is not the portal's doing.
6. **Generator validation**: with evenly spaced arrivals (`surge.arrivals: even`), ResultBench and k6 agreed: p50 5.9 ms for both, p99 11.7–12.1 ms against 12.7–14.0 ms, on design A at 150 req/s. Experiments use Poisson arrivals (burstier, higher tail).
7. **Nginx descriptor exhaustion** (fixed, commit "Bound Nginx open_file_cache…"): with `open_file_cache max=200000` and a container `nofile` limit of about 20,000, C2 at 10× returned 404 for 34,471 lookups of existing students, starting 15 s after release. The fix caps the cache at 4096 in both the lab and result-in-a-box configs. **Verified:** the same run after the fix served 100% of 75,093 students (99.96% within 2 s), with no missing results and no descriptor errors in the Nginx log.
8. **Generator-limited capacities**: C1's calibrated capacity (7,500/s) is where the *generator* saturated, so it is a lower bound (at least 33× design A). Say so in the paper.
9. **Waiting-room admission rate** = 80% of the backend's calibrated capacity (`designs.yaml`, `waiting_room.admit_fraction`). In a smoke run, D-A at 2× still overloaded A: admitted students timed out, refreshed, and pushed it over. That is part of RQ2/RQ4, not a bug.
10. **Cloud-environment workarounds you do not need locally**: Docker Hub rate limits (images were pulled from `mirror.gcr.io` and retagged), a `nofile` hard limit of 20,000 (hence no `--ulimit` by default; set `RB_LOADGEN_NOFILE` if you want one), and the vendored Go modules for offline builds.
11. **Small runner bug fixed after the cloud run started**: `paper-run.sh` re-ran calibration on restart because its check looked for the wrong text format. Fixed. Calibration of A gave 223.4 users/s both times, a nice reproducibility point.

## 8. Cloud-session state at handover (reference only, not for the paper)

- Calibration on the paper scenario, cloud VM with 4 vCPUs: **A = 223.4 students/s** (identical on two calibrations); **C1 ≥ 7,500/s** (generator-limited).
- `paper-run.sh` was running on the cloud VM. Its results live in that ephemeral container under `resultbench/runs/` (gitignored) and will be lost when the session ends unless explicitly exported. **Plan on re-running everything locally**; the paper should use one machine's results.
- Smoke-scenario observations (50k students, 1 run each, not paper data): A at 2× served 71% at all and 8% within 2 s; C2 at 2× served 100% at 0.4 CPU-s per 1,000 against 12 for A; B3 (pre-warmed) 100% vs B0 (cold) about 72–74%; corrections produced 7 stale responses in C2 (Nginx file cache) and 3 in B0 without invalidation; release with half the results pre-computed gave 12 "missing".

## 9. Suggested order of work for the local session

1. Check out the branch and set up (section 3). Run every check in section 4.
2. Start `bench/paper-run.sh` (section 5). While it runs:
   - Re-run the k6 comparison locally and update `sections/method.tex`.
   - Fill in the testbed details in `sections/method.tex`.
   - Fix the bibliography items in section 6.
3. As each grid finishes, run `python paper/make_figures.py` and write the matching results subsection from `paper/generated/*.csv`.
4. Write the discussion (recommendations for boards; include `threats.tex`), conclusion and abstract.
5. Compile, read the PDF end to end, and check every number against the CSVs.
6. Commit to `claude/awesome-fermi-7ckuzk` and push. Do not commit `resultbench/runs/`. If results must be archived, commit only `paper/generated/*.csv` and the figures.
7. Optional, if time allows: the sensitivity run for `PAGE_COST`; the full-size grids in `resultbench/bench/experiments/` (several days) for the thesis.

## 10. Useful commands

| Task | Command (from `resultbench/`) |
|---|---|
| One run | `python bench/rb.py run --design d-a --multiple 5 --scenario bench/scenarios/paper.yaml --env WR_POLICY=random` |
| Dry-run a grid | `python bench/rb.py grid bench/experiments/paper/paper-wr.yaml --dry-run` |
| Report one grid | `python -m analysis.report runs/paper-core --recollect` |
| Stop everything | `python bench/rb.py down` (add `--volumes` to drop the datasets) |
| Live dashboard | `python bench/rb.py monitor`, then open Grafana on port 3000 |
| Capacity model | `python -m model.capacity simulate --scenario bench/scenarios/paper.yaml --capacity 223 --peak 1117` |
