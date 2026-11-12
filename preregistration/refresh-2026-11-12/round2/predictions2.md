# Pre-registered predictions, second round (12 November 2026)

Written and frozen before any of the runs below. The model code, CPU costs
and time step are those of the first round (`predictions.md`, frozen at
04:27:06Z the same day); nothing is fitted to an outcome. The numbers come
from `make_predictions2.py` (`predictions2-tables.md`, `predictions2.csv`).

The first round's results are known at the time of writing (166 of 176
numbers held; the failures lie in fast, repeated refreshing near collapse).
This round tests the explanation the derivation gives for that regime.

## P8. The collapse is metastable when students refresh persistently

**Claim** (derivation, condition (8)). With an oldest-first queue, a collapse
sustains itself when (1 − p)(b − a) < S: refreshing students alone keep the
queue so long that no answer arrives in time, even after the fresh load has
fallen below what the server can carry. With patience 3–8 s (b − a = 5 s) and
S ≈ 1.28 s, this holds for p = 0.95 but not for p = 0.5. Allowing for the
limit of 20 attempts, the collapse persists while first requests stay above
about 61 per s (0.27×) for p = 0.95, and above 393 per s (1.76×) for p = 0.5.

**Design** (`resultbench/bench/experiments/refresh/p8-metastable.yaml`,
3 runs each). Design A; impatient students (patience 3–8 s, pause 0.5–2 s);
one refresh probability p after errors and time-outs. Students arrive for
300 s after release; runs end 45 s later.
- **surge 2× to 0.5×:** the usual surge to 2×, decaying (τ = 30 s) to a
  steady 0.5× (112 students per s).
- **steady 0.5×:** 0.5× from release.

The load from 150 to 300 s after release is the same in both (the surge's
excess is 0.011× at 150 s and falls from there). "Answered in hold" is the share of the
requests sent in that window that got an answer in time.

**Predictions:**

| p | Arrivals | Served | Useful work | Requests per student | Answered in hold | Recovery | Recovers while students arrive |
|---|---|---|---|---|---|---|---|
| 0.5 | surge 2× to 0.5× | 73.0% | 79.0% | 1.37 | 100.0% | 97 s | yes |
| 0.5 | steady 0.5× | 100.0% | 100.0% | 1.11 | 100.0% | 3 s | yes |
| 0.95 | surge 2× to 0.5× | 8.9% | 6.5% | 11.57 | 0.0% | never | no |
| 0.95 | steady 0.5× | 100.0% | 100.0% | 1.11 | 100.0% | 3 s | yes |

**Direction predictions** (the test of the claim):
- **D1 (hysteresis).** At p = 0.95, the same 0.5× load is answered in the hold
  window after the surge (below 20% of requests) but not from a fresh start
  (at least 95%).
- **D2.** At p = 0.95, the run after the surge does not recover while
  students are still arriving (no recovery before 300 s).
- **D3 (control).** At p = 0.5, the run after the surge recovers while
  students are still arriving, and at least 95% of the requests in the hold
  window are answered.

**Numbers** are judged by the first round's rules (`predictions.md`
section 3): median of 3 runs; served ±5 points, useful work ±7 points,
requests per student ±10%, recovery ±10 s (and "never" must match), answered
in hold ±5 points. The runs after a surge are in the known-failure regime
(oldest first, queue 4,096, patience 3–8 s), so there "served" may be
over-predicted by up to 10 points.

**What would refute the claim:** D1 or D2 failing, that is, the p = 0.95 run
recovering at 0.5× while students still arrive.

## P5c. The waiting room's own capacity

Pre-registered in the first round as a measurement; its number is frozen here.

**Design** (`p5c-room-capacity.yaml`, 3 runs). Design D-A at 5×, token
tickets, admitting 1 student per second, so the room (0.25 CPU) answers
almost only the polls of queued students.

**Prediction.** From the room's CPU costs fitted to the saturated seconds of
the earlier D-A runs (48.7 µs per queued answer, 303 µs per passed-through
request), the room saturates in every run and then gives **5,130 queued
answers per second** (measured by `model.capacity._room_busy`). It holds if
the median of the 3 runs is within ±15%.

## Not pre-registered (exploratory)

`x1-cancel-trace.yaml` (3 runs, started before this freeze) repeats P6's
impatient work-stopping configuration with every 10th request traced, to
measure how long the server takes to notice that a student has left. It
makes no prediction.

## Files frozen with this document

`FROZEN2.txt` lists the SHA-256 of this file, `predictions2-tables.md`,
`predictions2.csv`, `make_predictions2.py`, the model code and both grid
files.
