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
