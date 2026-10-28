# One-command reproduction (docs/reproduce.md). Every target is resumable.
PY ?= python3
SCENARIO ?= bench/scenarios/core.yaml
GRIDS ?= core waiting-room correctness cache refresh faults

.PHONY: test build calibrate grids reports reproduce smoke clean-runs

test:
	go test ./...
	$(PY) -m pytest -q tests

build:
	$(PY) bench/rb.py build

calibrate: build
	$(PY) bench/rb.py calibrate --design a --scenario $(SCENARIO)
	$(PY) bench/rb.py calibrate --design c1 --scenario $(SCENARIO) --start 500 --step 500 --growth 2
	$(PY) bench/rb.py calibrate --design c2 --scenario $(SCENARIO) --start 500 --step 500 --growth 2

grids:
	for g in $(GRIDS); do $(PY) bench/rb.py grid bench/experiments/$$g.yaml || exit 1; done

reports:
	for g in $(GRIDS); do $(PY) -m analysis.report runs/$$g --recollect || exit 1; done
	$(PY) -m model.capacity fit runs/core runs/refresh --design a --out runs/model-fit-a.json
	$(PY) -m model.capacity plan --cpu-costs runs/core/report/summary.csv --out runs/planning.md

reproduce: calibrate grids reports

# About 20 minutes: every design once, on the quick scenario.
smoke: build
	$(PY) bench/rb.py calibrate --design a --scenario bench/scenarios/quick.yaml --step-s 8
	$(PY) bench/rb.py grid bench/experiments/smoke.yaml
	$(PY) -m analysis.report runs/smoke --recollect
