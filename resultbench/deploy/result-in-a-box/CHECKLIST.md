# Release-day checklist

## One week before

- [ ] Results CSV exported from the source system; row count matches the number of candidates.
- [ ] Published to the result volume; the publish report shows `verified_ok` equal to the row count.
- [ ] Spot-check 20 roll numbers against the source system by hand.
- [ ] Dry-run surge at 2× the expected peak passed (99% correct within 5 s, zero wrong).
- [ ] Planning model run for this board size; server has at least that many cores.
- [ ] Rate limit tested from one IP; the limit does not block a college's shared NAT at normal use.
- [ ] DNS TTL lowered (e.g. 300 s) in case the server must be moved.
- [ ] Alternative channels (SMS, DigiLocker, UMANG) confirmed with their operators.

## Day before

- [ ] `RELEASE_AT_MS` set and double-checked (`date -d @$((RELEASE_AT_MS/1000))`).
- [ ] `docker compose ps`: web and releaser healthy; a lookup returns `425 not released`.
- [ ] Monitoring open: request rate, 5xx rate, CPU.
- [ ] Press note lists the official URL(s) only, and asks students not to keep refreshing.

## At release

- [ ] Lookup of a known roll number returns the correct result within a second of release.
- [ ] Watch 5xx and 429 rates. Rising 429s from a few IPs: scripted enumeration, keep the limit. Rising 5xx: check CPU and network.
- [ ] If overloaded, start the waiting room profile and point traffic at it; do not restart the web server.

## After

- [ ] Corrections, if any: re-publish; note the time; expect old files for up to `OFC_VALID`.
- [ ] Keep logs (no roll numbers are logged) for the post-incident note.
- [ ] Write a short note on peak load and any problems, and publish it: this is the data the next board needs.
