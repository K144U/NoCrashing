#!/usr/bin/env bash
# Runs everything the paper needs, in priority order. Resumable.
set -u
cd "$(dirname "$0")/.."
S=bench/scenarios/paper.yaml
[ -f runs/calibration/a/capacity.json ] && grep -q '"n": 200000' runs/calibration/a/scenario.yaml 2>/dev/null || \
  python3 bench/rb.py calibrate --design a --scenario $S --start 50 --step 50 --growth 1.5 --step-s 10
[ -f runs/calibration/c1/capacity.json ] && grep -q '"n": 200000' runs/calibration/c1/scenario.yaml 2>/dev/null || \
  python3 bench/rb.py calibrate --design c1 --scenario $S --start 500 --step 500 --growth 2 --step-s 8 --refine 2
for g in paper-core paper-wr paper-correct paper-cache paper-refresh; do
  python3 bench/rb.py grid bench/experiments/paper/$g.yaml
done
echo PAPER-RUN-DONE
