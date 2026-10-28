# Study 1: field measurement of the 2027 result season

Protocol for plan section 6. The aim is the first public description of what
result day looks like from outside: when real portals start failing, for how
long, and how that differs by board and hosting.

## Before the season (Dec 2026 – Jan 2027)

1. **Ethics sign-off.** Show this page and [`monitor/monitor.py`](../monitor/monitor.py)
   to the mentor (and the department ethics committee if required). The
   monitor only fetches public landing pages with GET, never submits roll
   numbers, identifies itself in the User-Agent, respects robots.txt, and
   sends at most one request per 15 s per target per vantage point (enforced
   in code).
2. **Vantage points.** At least two: home broadband (Lucknow) and one cloud VM
   in an Indian region. Keep their clocks synchronised (NTP).
3. **Targets.** Edit [`monitor/targets.yaml`](../monitor/targets.yaml): set
   `contact`, check every URL, add mirror links as boards announce them.
4. **Dry run** on a smaller release (a university or semester result):

   ```bash
   python -m monitor.monitor run --config monitor/targets.yaml --event example-2027 --vantage home-lucknow --dry-run
   ```

5. **RTI requests.** File the [RTI template](rti-template.md) with NIC, CBSE,
   NTA, AKTU and two or three state boards in November 2026; replies are due
   within 30 days.

## During the season (Feb – Jun 2027)

For each release:

1. Add the event to `targets.yaml` when the board announces the time
   (with timezone, e.g. `2027-05-13T13:00:00+05:30`).
2. Start the monitor on every vantage point at least an hour before release:

   ```bash
   python -m monitor.monitor run --config monitor/targets.yaml --event cbse-12-2027 --vantage home-lucknow
   ```

3. Archive the board's notice and any press reports about the day (PDF or
   Wayback Machine snapshot) in `field/<event>/sources/`.
4. Afterwards, summarise:

   ```bash
   python -m monitor.monitor summarize field/cbse-12-2027
   ```

## What is recorded

Per probe (`field/<event>/<vantage>.jsonl`): time relative to release, HTTP
status, DNS / connect / TLS / first-byte / total time, bytes, remote IP,
redirects, page title, content fingerprint, error-page text found in a 200
response ("soft failure"), and hosting/CDN headers (`server`, `via`,
`cf-cache-status`, `x-cache`, …).

Per event (`field/<event>/report/`): availability and median time to first
byte per minute, failure onset, minutes degraded, recovery minute, hosting
hints, and one chart per target.

## From field data to the lab

The arrival curve itself cannot be seen from outside. Use, in order of
preference:

1. Server-side aggregate counts from AKTU (plan 6.3) or RTI replies, to fit
   the surge shape directly.
2. Failure onset and duration from the monitor, to check that the lab's
   surge shape produces failures on a similar time scale.
3. The published anchors (JEE Advanced 2016 about 5× overload, World Cup '98
   5–10× pre-event ramp, UCAS 2011 about 4× previous peak).

Record which source each fitted parameter came from.

## Data release

Publish the per-probe readings and summaries (no personal data is collected),
together with the target list and the exact code version.
