#!/usr/bin/env bash
# Cross-check the ResultBench generator against k6 on design A at a constant
# 150 requests/s with evenly spaced arrivals (docs/experiments.md). Two runs of
# each; results go to runs/k6check/. Uses the same CPU split as the paper runs.
set -eu
cd "$(dirname "$0")/.."
: "${RB_SUT_CPUSET:?set RB_SUT_CPUSET}" "${RB_LOADGEN_CPUSET:?set RB_LOADGEN_CPUSET}"
S=bench/scenarios/k6check.yaml
mkdir -p runs/k6check
chmod a+w runs/k6check  # the k6 image runs as its own user

for r in 1 2; do
  [ -f "runs/k6check/rb-even-r$r/load/summary.json" ] && continue
  python3 bench/rb.py run --design a --scenario "$S" --experiment k6check --name "rb-even-r$r"
done

# Bring design A up with the runner's own settings, results already released.
python3 - <<'PY'
import sys
sys.path.insert(0, "bench")
import rb
designs, defaults = rb.load_designs()
d = designs["a"]
c = rb.Compose(d["files"], rb.base_env(d, defaults))
c.down()
c.up(d["databases"])
rb.ensure_dataset(c, d, rb.load_scenario("bench/scenarios/k6check.yaml", {}))
c.up([s for s in d["services"] if s not in d["databases"]])
PY

for r in 1 2; do
  [ -f "runs/k6check/k6-r$r.json" ] && continue
  docker run --rm --network rb-net --cpuset-cpus "$RB_LOADGEN_CPUSET" \
    --sysctl "net.ipv4.ip_local_port_range=1024 65535" --sysctl net.ipv4.tcp_tw_reuse=1 \
    -v "$PWD/k6:/scripts:ro" -v "$PWD/runs/k6check:/out" grafana/k6:0.57.0 run --quiet \
    -e TARGET=http://portal:8080 -e MODE=constant -e RATE=150 -e DURATION=30s -e N=200000 \
    --summary-export "/out/k6-r$r.json" /scripts/open_loop.js
done
python3 bench/rb.py down
echo K6-CHECK-DONE
