# Result-in-a-box

A reference deployment for a board's or university's IT cell (plan section
8.2). It publishes results as pre-computed static files behind Nginx, so
nothing on the read path can run out of database connections, with a
release-time gate, a per-IP rate limit, a student page that backs off instead
of hammering the server, and an optional waiting room.

Which design to pick, and how much hardware it needs, comes from the
ResultBench experiments and the capacity model; this folder is how to run it.

## 1. Prepare the results file

Export the results as CSV with this header (subjects are `CODE:Name`):

```
roll,name,father_name,school_code,school_name,district,HIN:Hindi,ENG:English,MAT:Mathematics,...
```

See [`sample/results.csv`](sample/results.csv). Totals, percentage, result and
division are computed from the marks with the rules in
[`internal/dataset`](../../internal/dataset/dataset.go) (pass mark 33 per
subject; first ≥ 60%, second ≥ 45%). Adjust `Finalize` there if your board's
rules differ.

## 2. Configure

```bash
cp .env.example .env
```

Set `RELEASE_AT_MS` (release time in Unix milliseconds) and
`RESULTS_CSV_DIR`. For the waiting room, also set `QUEUE_SECRET` to a long
random string.

## 3. Build the image and publish

From the `resultbench` folder:

```bash
docker build -t resultbench:local .
```

Then here:

```bash
docker compose --profile tools run --rm publish
```

The publish step writes one file per student and reads every file back to
check it. It refuses duplicate roll numbers and invalid marks.

## 4. Start

```bash
docker compose up -d
```

Until `RELEASE_AT_MS` every lookup answers `425 not released` without
touching the result files. With the waiting room in front (students use port
`QUEUE_PORT`):

```bash
docker compose --profile queue up -d
```

## 5. Dry run before release day

Run a ResultBench surge against the deployment from another machine, at the
load you expect, with a test release time:

```bash
docker run --rm --network host resultbench:local surge -targets http://<server>:8080 -peak 2000 -release-at <ms> -n <students> -roll-base <first roll> -oracle roll_only
```

`-oracle roll_only` checks that every answer belongs to the requested roll
number (the synthetic ground truth does not apply to real data). Roll numbers
are drawn from `roll-base` to `roll-base + n`; any gaps in your numbering show
up as 404s, which this mode accepts.

## 6. Corrections after release

Re-export the CSV with the revised rows and run step 3 again. Each file is
replaced atomically. Nginx may keep serving the old file for up to
`OFC_VALID`, and browsers or a CDN for up to `RESULT_MAX_AGE`; keep both short
when corrections are expected.

## Sizing

Run the planning model with your numbers:

```bash
python -m model.capacity plan --sizes 1600000 --share-first-hour 0.6 --tau-min 15
```

See also the [release-day checklist](CHECKLIST.md).
