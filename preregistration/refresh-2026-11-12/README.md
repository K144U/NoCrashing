# Pre-registration: predictions before the experiments (12 November 2026)

This folder records predictions made with the ResultBench capacity model
**before** any of the experiments that test them were run. Its purpose is to
let anyone check, later, that the predictions were not adjusted to fit the
results.

| File | What it is |
|---|---|
| `predictions.md` | The predictions P1–P7, their tolerances and the rules for judging them |
| `predictions-tables.md`, `predictions.csv` | Every predicted number |
| `make_predictions.py` | The script that produced them |
| `model/capacity.py`, `model/des.py` | The fluid model and the request-by-request simulator, as they were when the predictions were made |
| `FROZEN.txt` | SHA-256 fingerprints taken at freezing time (04:27 UTC) |

## Checking the files

```bash
sha256sum predictions.md predictions.csv predictions-tables.md model/capacity.py model/des.py
```

The output must match `FROZEN.txt`. There, the two model files are listed
under their paths in the repository (`../resultbench/model/...`).
`make_predictions.py` was changed after freezing only to also write a LaTeX
numbers file, as the note in `FROZEN.txt` says. Its predictions are
unchanged.

The model and its inputs are described in `predictions.md`. The experiments
will be run on the same machine as the ResultBench runs the CPU costs were
measured on. The results, including every prediction that fails, will be
reported against these files.

## Second round (frozen 11:12 UTC, 12 November 2026)

`round2/` holds predictions made after the first round's results were known
(166 of 176 numbers held) and before any of the runs that test them:

| File | What it is |
|---|---|
| `round2/predictions2.md` | P8 (is the collapse metastable?) and P5c (the waiting room's own capacity), with the rules for judging them |
| `round2/predictions2-tables.md`, `round2/predictions2.csv` | Every predicted number |
| `round2/make_predictions2.py` | The script that produced them (it imports `make_predictions.py` above) |
| `round2/grids/` | The experiment grids, as run |
| `round2/FROZEN2.txt` | SHA-256 fingerprints taken at freezing time |

The model code is unchanged: `model/capacity.py` has the same fingerprint in
`FROZEN.txt` and `round2/FROZEN2.txt`. `round2/grids/x1-cancel-trace.yaml`
is an exploratory measurement with no prediction.
