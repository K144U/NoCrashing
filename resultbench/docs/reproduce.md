# Reproducing the results

## One command

```bash
make reproduce
```

This builds the image, loads the dataset, calibrates the backends, runs every
grid in [`bench/experiments`](../bench/experiments) and writes the reports. It
takes several days of machine time; it is resumable, so interrupt and rerun
it freely.

The steps it runs, one by one:

```bash
make build
```

```bash
make calibrate
```

```bash
make grids
```

```bash
make reports
```

## What to record with published results

- The git commit (stored in every run's `meta.json`; a `-dirty` suffix means
  uncommitted changes).
- Machine: CPU model, cores, memory, OS and Docker version.
- Image digests: `docker image inspect --format '{{.RepoDigests}}' postgres:16-alpine redis:7.4-alpine nginx:1.27-alpine`.
- `runs/calibration/*/capacity.json`.

## Determinism

Data, roll-number order, and each simulated student's decisions are seeded
(`dataset.seed`, `generator.seed`; grids use seed `1000 × rep + 7`), so the
offered load is the same across designs for a given repetition. Timing on a
real machine is not deterministic; that is what the repetitions and bootstrap
intervals are for.

## Larger machines

On more than 4 cores, give the load generator more of them so it does not
saturate at high multiples:

```bash
RB_SUT_CPUSET=0,1 RB_LOADGEN_CPUSET=2-7 python bench/rb.py grid bench/experiments/core.yaml
```

Keep `RB_SUT_CPUSET` the same for every run that will be compared.
