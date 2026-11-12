# When Refreshing Breaks the Site: predictions before any new run

Written 12 November 2026, before any experiment for this paper. Revised the
same day, still before any run:
- the waiting room was added to the model (P5);
- requests that reach the server in the same 0.1 s step are now treated as
  simultaneous;
- a request-by-request simulator was added as a second check (section 2b).

Every number below comes from `make_predictions.py`. The full grids are in
`predictions-tables.md` and the values in `predictions.csv`. Report every
prediction that fails.

## 1. The model

`resultbench/model/capacity.py` models the same server and the same students as
ResultBench.

**Server** (`rb portal`):
- At most 256 requests are in service, together finishing `mu` answers per
  second.
- At most 4,096 more wait for a worker; any request beyond that gets a 503 at
  once.

**What happens to a request when its student's patience runs out:**
- If it is still waiting, the server drops it at almost no cost.
- If a worker has already taken it, the server finishes it anyway
  (`CANCEL_ON_DISCONNECT` is off). Nobody receives that answer: the work is
  wasted.

**Students:**
- Each student has a fixed patience, and every request times out after it.
- After a 503 or a time-out, a student refreshes with some probability after
  a short pause, and gives up after 20 failures.
- Students who arrive before release poll; 10% look again after seeing their
  result.

**Waiting room** (`Room`):
- It admits at a fixed rate, in arrival order.
- An admitted student reaches the server directly for 60 s.
- Naive tickets are lost on a manual refresh, and the room still admits the
  lost ticket until it has gone unseen for 30 s.
- The room has its own CPU, so polling can saturate it.

**Parameters.** None is fitted to student outcomes. The server's rate comes
from the CPU accounting of the existing runs, using least squares and leaving
out the run being predicted:
- 4.76 ms of CPU per answer;
- 0.07 ms per rejected or dropped request;
- 0.045 CPU of constant use.

With these costs, design A finishes about 200.6 answers per second. That is
less than the calibrated "1×" of 223.4 students per second, because the
calibration steps last only 10 seconds, and a queue can absorb a short excess.

## 2. What already holds: P1 on the existing runs

The model predicted 69 existing runs from their configuration alone.

Mean absolute error, with the largest error in brackets:

| Measure | Design A (30 runs) | Mirrors M (12 runs) |
|---|---|---|
| Served at all | 1.6 points (8.9) | 0.9 points (4.7) |
| Served within 5 s | 0.7 points (2.9) | 0.3 points (1.7) |
| Requests per student | 0.07 (0.52) | 0.002 (0.009) |
| Useful share of answers | 1.8 points (5.1) | 1.1 points (6.5) |
| Recovery time | 2.6 s (10 s, 24 runs) | 0.9 s (2 s, 8 runs) |
| Recovered within the run, or not | right in 30 of 30 | right in 11 of 12 |

**Waiting room D-A** (27 runs):
- **Naive tickets** are predicted well:
  - served at 5×: 41.7% measured, 40.4% predicted;
  - median wait: 59.5 s against 55 s;
  - long runs: 98.5% against 96.7% served.
- **Token tickets** are predicted too optimistically:
  - 5×: 35.7% measured, 56.2% predicted;
  - long runs: 71.2% against 93.2%;
  - impatient students at 2×: 44.5% against 91.2%.

**Wasted work, measured.** The useful share is the number of answers a student
received, divided by the number of answers the portal finished (from the
portal's own counters):

| Design A at 2× | Answers built per run | Useful share |
|---|---|---|
| Students never refresh | about 13,600 | 92–93% |
| Default refreshing | about 19,300 | 74–78% |
| Impatient refreshing | about 25,000 | 13–14% |

With impatient students, the answers that did get through while the server
was overloaded (requests sent 20–80 s after release) took 7.5–8.0 s, and
patience ends at 8 s. So only students with more than 7.5 s of patience were
served, each within half a second of giving up.

At 10×, M's useful share was 52.1% (model: 53.2%), against 83% for A.

## 2b. Second check: a request-by-request simulator

`resultbench/model/des.py` simulates the same server and students request by
request:
- Poisson arrivals;
- each student's own patience;
- exact pauses before a refresh;
- three ways the CPU can serve started requests: in start order, sharing it
  equally, or at random.

**On the existing design A runs**, it agrees with the fluid model to within
about 2 points, with any of the three. That includes the impatient regime: it
predicts 29–31% served, while the lab measured 22%.
- So the model's known error there does **not** come from the fluid
  approximation, from random arrivals, or from the CPU's service order.
- Random order even makes it *better* (67%).
- The gap therefore lies in the real system: something in the server, the
  network or the load generator that queueing models of this kind do not
  contain. The server traces (`TRACE_EVERY`) should locate it.

**On the predictions:**
- P4 agrees to within about 2 points on served, served within 5 s and useful
  share in all 18 configurations. The fluid model's former bias in the share
  served within 5 s was fixed by treating requests of one step as simultaneous.
- In P6, served and useful share agree, but the share served within 5 s
  differs by up to 10 points. Treat that column as uncertain.

## 3. Predictions for new runs

### Tolerances and rules

The tolerances come from the P1 errors above:
- served: ±5 points;
- served within 5 s: ±3 points (±10 for P6);
- useful share: ±7 points;
- requests per student: ±10%;
- recovery time: ±10 s.

The exception is the known-failure regime (oldest-first, a long queue, and
patience of 3–8 s), where the model may over-predict "served" by up to 10
points.

How a prediction is judged:
- A number holds if the median of three runs falls within its tolerance.
- A direction ("X beats Y") holds if the observed difference has the
  predicted sign and at least half the predicted size.

All loads are multiples of design A's calibrated capacity, as in ResultBench.

### P2. Tipping point: load against patience

Settings: default refreshing (0.8 after an error, 0.9 after a time-out, pause
1–5 s). Runs end 240 s after arrivals stop. "Overload outlasts arrivals" means
the recovery time is later than 90 s, when arrivals stop. The test points
below are new. In five of the six, the predicted recovery time is more than
10 s from 90 s, so the tolerance cannot flip the answer.

| Patience | Load | Served | Useful | Recovery | Overload outlasts arrivals? |
|---|---|---|---|---|---|
| 3–8 s | 1.25× | 89.5% | 53.1% | 79 s | no |
| 3–8 s | 1.5× | 72.5% | 38.7% | 109 s | yes |
| 5–20 s | 1.5× | 97.9% | 89.1% | 48 s | no |
| 5–20 s | 3× | 69.4% | 76.2% | 102 s | yes |
| 10–30 s | 2× | 96.9% | 89.6% | 66 s | no |
| 10–30 s | 5× | 47.9% | 85.7% | 98 s | no margin: report only |

The boundary moves with patience:
- 3–8 s: between 1.25× and 1.5×;
- 5–20 s: between 2× and 2.5×;
- 10–30 s: between 2.5× and 3×.

With 3–8 s patience, more than half the server's work is wasted already at
1.25×.

### P3. Recovery against refresh probability

Settings: 2×, patience 5–20 s, the same probability after errors and
time-outs, runs ending 240 s after arrivals stop.

| Refresh probability | Served | Useful | Requests per student | Recovery |
|---|---|---|---|---|
| 0 | 79.1% | 94.3% | 1.17 | 46 s |
| 0.5 | 81.4% | 90.4% | 1.36 | 55 s |
| 0.8 | 86.4% | 83.5% | 1.72 | 72 s |
| 0.95 | 94.5% | 77.4% | 2.23 | 89 s |

Recovery time rises steadily with the refresh probability, from 46 to 89 s.
Refreshing helps the student who refreshes (more are served in the end) while
it costs the system (less useful work and a later recovery).

### P4. Queue length and order

Runs end 45 s after arrivals stop. Rows marked FIFO serve the oldest waiting
request first, as `rb portal` does by default; LIFO serves the newest first
(`QUEUE_ORDER=lifo`).

| Students | Load | Queue | Order | Served | Within 5 s | Useful |
|---|---|---|---|---|---|---|
| default | 2× | 4,096 | FIFO | 90.7% | 14.3% | 78.8% |
| default | 2× | 4,096 | LIFO | 93.5% | 57.0% | 99.7% |
| default | 2× | 1,100 | FIFO | 80.5% | 24.4% | 87.3% |
| default | 2× | 256 | FIFO | 79.2% | 57.0% | 100% |
| impatient | 2× | 4,096 | FIFO | 29.6% | 12.4% | 17.7% |
| impatient | 2× | 4,096 | LIFO | 92.9% | 43.8% | 99.7% |
| impatient | 2× | 1,100 | FIFO | 55.7% | 14.8% | 42.3% |
| impatient | 2× | 256 | FIFO | 77.6% | 55.5% | 100% |
| default | 5× | 4,096 | FIFO | 44.0% | 3.8% | 76.3% |
| default | 5× | 4,096 | LIFO | 50.9% | 17.6% | 99.6% |
| default | 5× | 256 | FIFO | 41.0% | 18.7% | 100% |

What the table predicts:
- **Serving newest first removes the wasted work and serves the most students
  in every setting.**
  - With patient students it is as fast as the short queue: 57.0% within 5 s
    at 2×.
  - With impatient students it is somewhat slower: 43.8% against 55.5%.
- **A short queue (256) also removes the waste,** and raises the share served
  within 5 s about four-fold:
  - 14.3% to 57.0%;
  - 12.4% to 55.5%;
  - 3.8% to 18.7%.
- **But with patient students, the short queue serves fewer in total:** 79.2%
  against 90.7% at 2×. More students get a 503, and some give up. With
  impatient students it serves far more: 77.6% against 29.6%.
- **A queue of 1,100 is only a halfway house.** The idea note expected a sharp
  gain at that length; the model puts it at newest-first, or at a queue as
  short as the worker pool.
- **Newest-first with a short queue** gives nothing over the short queue
  alone (`predictions-tables.md`).

### P5. Waiting room with token tickets

Written on 12 November, before any waiting-room run for this paper.

**What the existing data shows**, measured rather than modelled:
- **The room admitted almost as fast as its server could answer.** It admitted
  178.8 students per second: 80% of the 223.4 measured for design A with
  1 CPU. Behind the room, A had 0.875 CPU and sustains about 181 answers per
  second (174 by A's own CPU costs). So it admitted at 99% of the sustained
  rate. The portal was at its CPU limit from 10 s onward in the token runs.
- **Naive tickets protected the server by accident.** Lost tickets used up 36%
  of the admissions, so the server saw about 125 requests per second.
- **The room ran out of CPU at 5× in every run,** at its 0.25 CPU limit. A
  queued answer costs 48.7 µs and a passed-through request 303 µs (measured in
  the room's saturated seconds). Its "queued" answers slowed from under 0.1 s
  to 6–7 s.

**Predictions** (token tickets, room 0.25 CPU, server 0.875 CPU):

| Students | Load | Room | Admitted per s | Served | Useful work | Server requests per student | Median wait |
|---|---|---|---|---|---|---|---|
| default | 5× | as in ResultBench | 178.8 | 56.0% | 95.2% | 0.74 | 57 s |
| default | 5× | admit at 80% of the sustained rate | 144.6 | 51.1% | 100% | 0.56 | 59 s |
| default | 5× | cap of 2 server requests | 178.8 | 56.1% | 95.3% | 0.71 | 57 s |
| impatient | 2× | as in ResultBench | 178.8 | 90.4% | 62.2% | 2.12 | 18 s |
| impatient | 2× | admit at 80% of the sustained rate | 144.6 | 100% | 100% | 1.10 | 29 s |
| impatient | 2× | cap of 2 server requests | 178.8 | 89.4% | 61.4% | 2.05 | 18 s |

What to test:
- **P5a.** Admitting at 80% of the server's *sustained* rate removes the wasted
  work and the collapse, at the cost of a longer wait. This is a direction
  prediction. Because the model under-predicts the collapse at the current
  rate, the measured gain should be at least as large as predicted.
- **P5b.** A cap on server requests per admission changes little while the
  admission rate stays at 99%. This is the weakest prediction, given the
  model's error for token rooms. It needs a code change in `rb waitingroom`,
  so it can wait until P5a is known.
- **P5c (calibration).** Measure the room's own capacity directly before these
  runs: a room alone, with only queued students polling.

### P6. Stop the work when the student leaves

`CANCEL_ON_DISCONNECT=true` now stops the page building too. All rows are at
2× unless marked. The "within 5 s" column is uncertain by ±10 points (see 2b).

| Students | Work stops when the student leaves | Served | Within 5 s | Useful | Recovery |
|---|---|---|---|---|---|
| never refresh | no | 79.1% | 30.5% | 94.3% | 46 s |
| never refresh | yes | 82.0% | 37.6% | 100% | 42 s |
| default | no | 90.7% | 14.3% | 78.8% | 83 s |
| default | yes | 94.6% | 27.9% | 100% | 60 s |
| impatient | no | 29.6% | 12.4% | 17.7% | never |
| impatient | yes | 92.8% | 35.6% | 100% | 64 s |
| default, 5× | no | 44.0% | 3.8% | 76.3% | 112 s |
| default, 5× | yes | 50.9% | 6.5% | 100% | 98 s |

The model predicts that stopping wasted work all but removes the collapse with
impatient students.

### P7. Mirrors waste more because each keeps 256 workers on half the CPU

Settings: two mirrors with 0.5 CPU each, and students who never refresh (as
`paper-core` M).

| Load | Workers per mirror | Served | Within 5 s | Useful |
|---|---|---|---|---|
| 5× | 256 | 28.1% | 5.3% | 64.7% |
| 5× | 128 | 35.2% | 6.0% | 82.5% |
| 10× | 256 | 12.5% | 1.5% | 53.7% |
| 10× | 128 | 17.9% | 1.5% | 78.1% |

Halving the workers per mirror should recover most of the waste.

## 4. Built before the cluster runs (12 November)

1. **Newest-first queue:** `QUEUE_ORDER=lifo`. The worker pool is now an
   explicit queue (`internal/portal/pool.go`) for both orders.
2. **Page building that stops when the student leaves:**
   `CANCEL_ON_DISCONNECT=true` now stops the query and the page building.
3. **Server-side measurements:**
   - per-request traces for every n-th request with `TRACE_EVERY=n`, saved to
     `stats/portal-trace.csv`;
   - a new counter, `answers_after_client_left`;
   - new histograms: `queue_wait` and `service`.
4. **The waiting room in the model,** and the request-by-request simulator
   (`model/des.py`).

Still to do:
- **Rebuild the image.** Docker is not running; the image also still lacks the
  generator fix of 11 November.
- **One regression run** to show that the new oldest-first pool reproduces the
  old results.
- **A per-admission request cap** in `rb waitingroom`, only if P5b is run.

The race detector needs gcc, which this WSL install lacks, so it should run
inside the Docker build or on the cluster.

## 5. Procedure on the cluster

1. Build the image and run the unit tests.
2. Calibrate design A, then rerun the `paper-core` and `paper-refresh` runs of
   design A (21 runs) with `TRACE_EVERY=10`. This is P1 on the new hardware,
   and the traces locate the known failure.
3. Run `make_predictions.py --runs <cluster runs>` to refit the CPU costs on
   that machine. Keep a dated copy of the regenerated predictions before
   running any P2–P7 grid.
4. Run the P2–P7 grids: about 120 runs, or 8–10 hours on one node. Then compare
   them with the predictions under the rules in section 3.

## 6. Changes from the idea note of 12 November

- **Section 2 numbers:** all checked against the data. The 74.5% and 3.21
  requests per student come from the longer 330-second waiting-room runs.
- **Section 5 mechanism corrected.** Waiting requests are dropped when their
  student leaves (`portal.go`). The waste comes from requests that start just
  before their student gives up, and that the server then finishes.
- **The server's rate** is about 200 answers per second, not 223.
- **P4:** the sharp gain comes from serving newest first, or from a queue as
  short as the worker pool, not from 1,100.
- **P5:** the idea note expected a per-student request cap to be the fix. The
  model points to the admission rate instead, and to the room's own CPU.
- **New predictions:** P6 (stopping work) and P7 (mirrors).
- **Prior work** (`related-work.md`): the wasted-work mechanism and LIFO under
  overload are known (Dalal and Jordan 2001; Singhmar et al. 2004; Mathur and
  Apte 2007). This paper's contribution is the announced surge, the waiting
  room and the validation.
