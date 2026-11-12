# Second-round predictions (generated)

Model code: `resultbench/model/capacity.py` at commit `c7c9a7b-dirty`; time step 0.1 s; mu = 200.6 answers/s; 1x = 223.4375 students/s.

## P8: metastability (impatient students, patience 3-8 s, pause 0.5-2 s; arrivals for 300 s after release, runs end 45 s later; 'hold' = requests sent 150-300 s after release)

| p | Arrivals | Served | Useful work | Requests/student | Answered in hold | Recovery | Recovers while students arrive |
|---|---|---|---|---|---|---|---|
| 0.5 | surge 2x to 0.5x | 73.0% | 79.0% | 1.37 | 100.0% | 97 s | yes |
| 0.5 | steady 0.5x | 100.0% | 100.0% | 1.11 | 100.0% | 3 s | yes |
| 0.95 | surge 2x to 0.5x | 8.9% | 6.5% | 11.57 | 0.0% | never | no |
| 0.95 | steady 0.5x | 100.0% | 100.0% | 1.11 | 100.0% | 3 s | yes |

Closed form (derivation (7)-(9), M = 20, b - a = 5 s, S = W/mu):

- p = 0.5: N = 2.00, S = 1.28 s, metastable by (8): no, collapse persists while first requests >= 393/s (1.76x)
- p = 0.95: N = 12.83, S = 1.28 s, metastable by (8): yes, collapse persists while first requests >= 61/s (0.27x)

## P5c: the waiting room alone

- Room CPU costs fitted to the saturated seconds of the earlier D-A runs: 48.7 us per queued answer, 303 us per passed-through request.
- Predicted capacity of the 0.25 CPU room with nobody admitted: 5,130 queued answers/s.

