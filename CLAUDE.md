# CLAUDE.md

Thesis project "Surviving Result Day" (Sankalp Pathak, M.Tech CSE, AKTU).
Current goal: finish a lab-only paper as fast as possible. **Read
`HANDOVER.md` first**: it has the state, history, decisions and next steps.

## Layout

- `result-portal-research-plan.md`: thesis plan v2.
- `reports/`, `research_notes/`: gap analysis.
- `resultbench/`: all software (Go binary `rb`, Docker Compose designs, Python runner and analysis).
- `paper/`: LaTeX paper (IEEEtran). Figures and tables come from `paper/make_figures.py`.

## Commands (from `resultbench/`)

- Tests: `go test ./...` and `python -m pytest -q tests`.
- Build image: `python bench/rb.py build` (rebuild after any Go change).
- Paper experiments: `bench/paper-run.sh` (resumable, about 6.5 h on 4 cores).
- Figures and tables: `python ../paper/make_figures.py`; then in `paper/`: `latexmk -pdf main.tex`.

## Rules

- Every number in the paper comes from `paper/generated/*.csv` or tables generated from real runs. Never estimate, round up or invent results; if data is missing, say so.
- A run with `wrong_requests > 0`, unexpected `missing_requests`, or `generator.saturated: true` needs investigation before its numbers are used.
- Do not change design settings (`bench/designs.yaml`, `deploy/`), scenarios or budgets while a grid is running. If they must change, delete and rerun the affected grid.
- After changing Go code: `gofmt`, `go vet ./...`, `go test ./...`, then rebuild the image before running experiments.
- `resultbench/runs/` and `resultbench/vendor/` are gitignored; do not commit them.
- Methodology and assumptions are documented in `resultbench/docs/methodology.md`. Keep it in sync with any change.
- Work on branch `claude/awesome-fermi-7ckuzk`.
