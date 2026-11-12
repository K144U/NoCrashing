# Predictions (generated)

Model code: `resultbench/model/capacity.py` at commit `c7c9a7b-dirty`; time step 0.1 s.

## P1: existing runs of design A (leave one run out)

| experiment | label | x | page | mirrors | n | served_ok obs / pred | success_5s obs / pred | amplification obs / pred | useful_share obs / pred | recovery_s obs / pred |
|---|---|---|---|---|---|---|---|---|---|---|
| paper-core |  | 1 | 5ms | 1 | 3 | 1.000 / 1.000 | 1.000 / 1.000 | 1.093 / 1.088 | 1.000 / 1.000 | 3.000 / 3.000 |
| paper-core |  | 10 | 5ms | 1 | 3 | 0.208 / 0.212 | 0.014 / 0.015 | 1.089 / 1.088 | 0.834 / 0.843 | nan / nan |
| paper-core |  | 2 | 5ms | 1 | 3 | 0.782 / 0.805 | 0.313 / 0.334 | 1.090 / 1.088 | 0.925 / 0.939 | 45.000 / 42.000 |
| paper-core |  | 5 | 5ms | 1 | 3 | 0.399 / 0.406 | 0.076 / 0.079 | 1.088 / 1.088 | 0.867 / 0.883 | 74.667 / 73.000 |
| paper-refresh | default | 2 | 5ms | 1 | 3 | 0.890 / 0.906 | 0.132 / 0.141 | 2.155 / 2.029 | 0.755 / 0.784 | 89.333 / 84.333 |
| paper-refresh | impatient | 2 | 5ms | 1 | 3 | 0.220 / 0.296 | 0.117 / 0.124 | 8.626 / 8.152 | 0.133 / 0.177 | nan / nan |
| paper-refresh | no-refresh | 2 | 5ms | 1 | 3 | 0.774 / 0.791 | 0.295 / 0.305 | 1.165 / 1.167 | 0.925 / 0.943 | 48.000 / 46.000 |
| paper-sens | page-0ms | 2 | 0 | 1 | 3 | 1.000 / 1.000 | 1.000 / 1.000 | 1.090 / 1.088 | 1.000 / 1.000 | 3.000 / 3.000 |
| paper-sens | page-2ms | 2 | 2ms | 1 | 3 | 1.000 / 1.000 | 1.000 / 1.000 | 1.090 / 1.088 | 1.000 / 1.000 | 3.000 / 3.000 |
| paper-wr |  | 5 | 5ms | 1 | 3 | 0.433 / 0.439 | 0.035 / 0.038 | 3.800 / 3.746 | 0.719 / 0.763 | 118.667 / 112.000 |

served_ok: mean absolute error 0.016, largest 0.089 (30 runs)
success_2s: mean absolute error 0.005, largest 0.022 (30 runs)
success_5s: mean absolute error 0.007, largest 0.029 (30 runs)
success_10s: mean absolute error 0.024, largest 0.099 (30 runs)
amplification: mean absolute error 0.074, largest 0.524 (30 runs)
backend_amplification: mean absolute error 0.121, largest 0.434 (30 runs)
useful_share: mean absolute error 0.018, largest 0.051 (30 runs)
dropped_per_user: mean absolute error 0.033, largest 0.225 (30 runs)
rejected_per_user: mean absolute error 0.057, largest 0.636 (30 runs)
recovery_s: mean absolute error 2.625, largest 10.000 (24 runs)
recovered within the run or not: model agrees in 30 of 30 runs

## P1: existing runs of design M (leave one run out)

| experiment | label | x | page | mirrors | n | served_ok obs / pred | success_5s obs / pred | amplification obs / pred | useful_share obs / pred | recovery_s obs / pred |
|---|---|---|---|---|---|---|---|---|---|---|
| paper-core |  | 1 | 5ms | 2 | 3 | 1.000 / 1.000 | 1.000 / 1.000 | 1.093 / 1.088 | 1.000 / 1.000 | 3.000 / 3.000 |
| paper-core |  | 10 | 5ms | 2 | 3 | 0.132 / 0.134 | 0.014 / 0.016 | 1.089 / 1.088 | 0.521 / 0.532 | nan / nan |
| paper-core |  | 2 | 5ms | 2 | 3 | 0.757 / 0.752 | 0.304 / 0.305 | 1.090 / 1.088 | 0.867 / 0.867 | 47.667 / 46.000 |
| paper-core |  | 5 | 5ms | 2 | 3 | 0.294 / 0.313 | 0.064 / 0.069 | 1.088 / 1.088 | 0.641 / 0.672 | nan / 76.667 |

served_ok: mean absolute error 0.009, largest 0.047 (12 runs)
success_2s: mean absolute error 0.011, largest 0.092 (12 runs)
success_5s: mean absolute error 0.003, largest 0.017 (12 runs)
success_10s: mean absolute error 0.008, largest 0.038 (12 runs)
amplification: mean absolute error 0.002, largest 0.009 (12 runs)
backend_amplification: mean absolute error 0.088, largest 0.088 (12 runs)
useful_share: mean absolute error 0.011, largest 0.065 (12 runs)
dropped_per_user: mean absolute error 0.005, largest 0.021 (12 runs)
rejected_per_user: mean absolute error 0.001, largest 0.007 (12 runs)
recovery_s: mean absolute error 0.875, largest 2.000 (8 runs)
recovered within the run or not: model agrees in 11 of 12 runs

## P1: existing runs of design D-A (leave one run out)

| experiment | label | x | page | mirrors | n | served_ok obs / pred | success_10s obs / pred | backend_amplification obs / pred | useful_share obs / pred | wait_p50_s obs / pred | recovery_s obs / pred |
|---|---|---|---|---|---|---|---|---|---|---|---|
| paper-refresh | default | 2 | 5ms | 1 | 3 | 0.975 / 1.000 | 0.114 / 0.156 | 1.315 / 1.100 | 0.907 / 1.000 | 26.306 / 18.000 | 3.000 / 3.000 |
| paper-refresh | impatient | 2 | 5ms | 1 | 3 | 0.445 / 0.912 | 0.101 / 0.139 | 5.461 / 2.115 | 0.331 / 0.627 | 18.010 / 18.000 | 3.000 / 3.000 |
| paper-refresh | no-refresh | 2 | 5ms | 1 | 3 | 0.913 / 1.000 | 0.114 / 0.155 | 1.090 / 1.100 | 0.947 / 1.000 | 25.455 / 18.000 | 3.000 / 3.000 |
| paper-wr | fifo-naive | 5 | 5ms | 1 | 3 | 0.417 / 0.404 | 0.037 / 0.040 | 0.461 / 0.440 | 0.999 / 1.000 | 59.521 / 55.000 | 3.000 / 3.000 |
| paper-wr | fifo-token | 5 | 5ms | 1 | 3 | 0.357 / 0.562 | 0.042 / 0.049 | 1.618 / 0.736 | 0.632 / 0.954 | 40.111 / 57.000 | 3.000 / 3.000 |
| paper-wr | random-naive | 5 | 5ms | 1 | 3 | 0.420 / 0.404 | 0.038 / 0.040 | 0.462 / 0.440 | 0.999 / 1.000 | 59.790 / 55.000 | 3.000 / 3.000 |
| paper-wr | random-token | 5 | 5ms | 1 | 3 | 0.344 / 0.562 | 0.043 / 0.049 | 1.711 / 0.738 | 0.610 / 0.954 | 38.750 / 57.000 | 3.000 / 3.000 |
| paper-wr-long | fifo-naive | 5 | 5ms | 1 | 3 | 0.985 / 0.967 | 0.037 / 0.040 | 1.078 / 1.060 | 1.000 / 1.000 | 121.021 / 130.000 | 3.000 / 3.000 |
| paper-wr-long | fifo-token | 5 | 5ms | 1 | 3 | 0.712 / 0.932 | 0.044 / 0.049 | 3.454 / 1.706 | 0.561 / 0.833 | 107.361 / 85.000 | 3.000 / 3.000 |

served_ok: mean absolute error 0.141, largest 0.502 (27 runs)
success_2s: mean absolute error 0.002, largest 0.003 (27 runs)
success_5s: mean absolute error 0.007, largest 0.023 (27 runs)
success_10s: mean absolute error 0.016, largest 0.047 (27 runs)
amplification: mean absolute error 1.727, largest 3.615 (27 runs)
backend_amplification: mean absolute error 0.804, largest 3.722 (27 runs)
useful_share: mean absolute error 0.153, largest 0.376 (27 runs)
dropped_per_user: mean absolute error 0.529, largest 3.084 (27 runs)
rejected_per_user: mean absolute error 0.028, largest 0.245 (27 runs)
recovery_s: mean absolute error 0.000, largest 0.000 (27 runs)
wait_p50_s: mean absolute error 10.330, largest 37.394 (27 runs)
recovered within the run or not: model agrees in 27 of 27 runs

## CPU costs used for the predictions

- CPU per answer (PAGE_COST 5 ms): 4.761 ms
- CPU per other request: 0.0693 ms (0.0146 answers)
- constant use per portal: 0.045 CPU
- so design A (1 CPU) finishes mu = 200.6 answers/s; 1x = 223.4375 students/s (mu / 1x = 0.898)

## P2: tipping point (default refreshing: 0.8 after an error, 0.9 after a time-out, pause 1-5 s; runs end 240 s after arrivals stop)

| patience_s | load | served | within 5 s | useful work | requests/student | recovery (s) | overload outlasts arrivals (90 s) |
|---|---|---|---|---|---|---|---|
| 3-8 | 1x | 100.0% | 100.0% | 100.0% | 1.19 | 3.00 | no |
| 3-8 | 1.25x | 89.5% | 79.4% | 53.1% | 2.12 | 79.00 | no |
| 3-8 | 1.5x | 72.5% | 21.0% | 38.7% | 3.63 | 109.00 | yes |
| 3-8 | 2x | 49.3% | 12.4% | 27.4% | 5.61 | 143.00 | yes |
| 3-8 | 2.5x | 34.8% | 8.9% | 23.2% | 6.00 | 150.00 | yes |
| 3-8 | 3x | 24.1% | 6.9% | 19.5% | 6.04 | 149.00 | yes |
| 3-8 | 4x | 16.3% | 4.7% | 17.6% | 5.90 | 152.00 | yes |
| 3-8 | 5x | 12.5% | 3.5% | 17.0% | 5.76 | 154.00 | yes |
| 5-20 | 1x | 100.0% | 100.0% | 100.0% | 1.19 | 3.00 | no |
| 5-20 | 1.25x | 100.0% | 95.1% | 100.0% | 1.19 | 3.00 | no |
| 5-20 | 1.5x | 97.9% | 38.0% | 89.1% | 1.38 | 48.00 | no |
| 5-20 | 2x | 90.7% | 14.3% | 78.8% | 2.01 | 83.00 | no |
| 5-20 | 2.5x | 79.8% | 9.4% | 75.9% | 2.58 | 97.00 | yes |
| 5-20 | 3x | 69.4% | 7.4% | 76.2% | 2.93 | 102.00 | yes |
| 5-20 | 4x | 54.1% | 5.0% | 76.0% | 3.43 | 109.00 | yes |
| 5-20 | 5x | 44.0% | 3.8% | 76.4% | 3.74 | 112.00 | yes |
| 10-30 | 1x | 100.0% | 100.0% | 100.0% | 1.19 | 3.00 | no |
| 10-30 | 1.25x | 100.0% | 95.1% | 100.0% | 1.19 | 3.00 | no |
| 10-30 | 1.5x | 100.0% | 44.5% | 100.0% | 1.19 | 3.00 | no |
| 10-30 | 2x | 96.9% | 15.6% | 89.6% | 1.46 | 66.00 | no |
| 10-30 | 2.5x | 85.7% | 9.4% | 85.2% | 1.98 | 84.00 | no |
| 10-30 | 3x | 75.1% | 7.4% | 85.0% | 2.38 | 91.00 | yes |
| 10-30 | 4x | 58.9% | 5.0% | 85.9% | 2.98 | 94.00 | yes |
| 10-30 | 5x | 47.9% | 3.8% | 85.7% | 3.38 | 98.00 | yes |

## P3: recovery against refresh probability (2x, patience 5-20 s, same probability after errors and time-outs; runs end 240 s after arrivals stop)

| refresh_prob | load | served | useful work | requests/student | recovery (s) |
|---|---|---|---|---|---|
| 0.0 | 2x | 79.1% | 94.3% | 1.17 | 46.00 |
| 0.5 | 2x | 81.4% | 90.4% | 1.36 | 55.00 |
| 0.7 | 2x | 84.0% | 86.6% | 1.55 | 64.00 |
| 0.8 | 2x | 86.4% | 83.5% | 1.72 | 72.00 |
| 0.9 | 2x | 90.7% | 78.8% | 2.01 | 83.00 |
| 0.95 | 2x | 94.5% | 77.4% | 2.23 | 89.00 |

## P4: queue length and order (paper scenario, runs end 45 s after arrivals stop)

| students | load | queue | order | served | within 5 s | useful work | requests/student | recovery (s) |
|---|---|---|---|---|---|---|---|---|
| default | 2x | 4096 | fifo | 90.7% | 14.3% | 78.8% | 2.01 | 83.00 |
| default | 2x | 4096 | lifo | 93.5% | 57.0% | 99.7% | 1.77 | 57.00 |
| default | 2x | 1100 | fifo | 80.5% | 24.4% | 87.3% | 2.01 | 55.00 |
| default | 2x | 1100 | lifo | 84.6% | 59.1% | 99.7% | 1.91 | 45.00 |
| default | 2x | 256 | fifo | 79.2% | 57.0% | 100.0% | 2.00 | 42.00 |
| default | 2x | 256 | lifo | 79.3% | 58.9% | 99.8% | 2.02 | 43.00 |
| impatient | 2x | 4096 | fifo | 29.6% | 12.4% | 17.7% | 8.15 | never |
| impatient | 2x | 4096 | lifo | 92.9% | 43.8% | 99.7% | 2.53 | 62.00 |
| impatient | 2x | 1100 | fifo | 55.7% | 14.8% | 42.3% | 5.37 | 102.00 |
| impatient | 2x | 1100 | lifo | 83.4% | 52.6% | 99.8% | 2.95 | 51.00 |
| impatient | 2x | 256 | fifo | 77.6% | 55.5% | 100.0% | 3.17 | 42.00 |
| impatient | 2x | 256 | lifo | 77.6% | 57.5% | 99.8% | 3.24 | 42.00 |
| default | 5x | 4096 | fifo | 44.0% | 3.8% | 76.3% | 3.74 | 112.00 |
| default | 5x | 4096 | lifo | 50.9% | 17.6% | 99.6% | 3.47 | 92.00 |
| default | 5x | 1100 | fifo | 39.2% | 3.4% | 84.4% | 3.60 | 89.00 |
| default | 5x | 1100 | lifo | 43.4% | 20.0% | 99.7% | 3.49 | 78.00 |
| default | 5x | 256 | fifo | 41.0% | 18.7% | 100.0% | 3.49 | 76.00 |
| default | 5x | 256 | lifo | 41.0% | 20.6% | 99.9% | 3.51 | 75.00 |

## CPU costs for the waiting-room predictions

- design A behind the room (0.875 CPU): mu = 180.8 answers/s
- room (0.25 CPU): 48.7 us per queued answer, 302.8 us per passed-through request
- ResultBench admitted 178.8 students/s (80% of A's 223.4 at 1 CPU) = 99% of mu

## P5: waiting room with token tickets (runs end 45 s after arrivals stop). The model over-predicts 'served' for token rooms (see P1, design D-A).

| students | load | room | admit_per_s | served | within 10 s | useful work | server requests/student | median wait (s) |
|---|---|---|---|---|---|---|---|---|
| default | 5x | as run (ResultBench) | 178.8 | 56.0% | 4.9% | 95.2% | 0.74 | 57.00 |
| default | 5x | admit 80% of mu | 144.6 | 51.1% | 4.0% | 100.0% | 0.56 | 59.00 |
| default | 5x | cap 2 server requests | 178.8 | 56.1% | 4.9% | 95.3% | 0.71 | 57.00 |
| default | 5x | 80% of mu and cap 2 | 144.6 | 51.1% | 4.0% | 100.0% | 0.56 | 59.00 |
| impatient | 2x | as run (ResultBench) | 178.8 | 90.4% | 13.9% | 62.2% | 2.12 | 18.00 |
| impatient | 2x | admit 80% of mu | 144.6 | 100.0% | 9.2% | 100.0% | 1.10 | 29.00 |
| impatient | 2x | cap 2 server requests | 178.8 | 89.4% | 13.4% | 61.4% | 2.05 | 18.00 |
| impatient | 2x | 80% of mu and cap 2 | 144.6 | 100.0% | 9.2% | 100.0% | 1.10 | 29.00 |

## P6: stop the work when the student leaves

| students | load | cancel_on_disconnect | served | within 5 s | useful work | recovery (s) |
|---|---|---|---|---|---|---|
| no refresh | 2x | False | 79.1% | 30.5% | 94.3% | 46.00 |
| no refresh | 2x | True | 82.0% | 37.6% | 100.0% | 42.00 |
| default | 2x | False | 90.7% | 14.3% | 78.8% | 83.00 |
| default | 2x | True | 94.6% | 27.9% | 100.0% | 60.00 |
| impatient | 2x | False | 29.6% | 12.4% | 17.7% | never |
| impatient | 2x | True | 92.8% | 35.6% | 100.0% | 64.00 |
| default | 5x | False | 44.0% | 3.8% | 76.3% | 112.00 |
| default | 5x | True | 50.9% | 6.5% | 100.0% | 98.00 |

## P7: two mirrors with 0.5 CPU each, students do not refresh (as paper-core M)

| load | workers_per_mirror | served | within 5 s | useful work |
|---|---|---|---|---|
| 5x | 256 | 28.1% | 5.3% | 64.7% |
| 5x | 128 | 35.2% | 6.0% | 82.5% |
| 10x | 256 | 12.5% | 1.5% | 53.7% |
| 10x | 128 | 17.9% | 1.5% | 78.1% |

