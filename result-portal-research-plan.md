# Surviving Result Day
### Measuring, Modelling and Fixing Result Portals Under Scheduled Surges

**Thesis research plan, version 2 (rebuilt from the gap analysis)**
Author: Sankalp Pathak, M.Tech (Computer Science), AKTU Lucknow
Status: Draft v2, 27 Oct 2026. Replaces v1 (`result-portal-thesis-plan.md`, now removed).
Built on: [`reports/Result portal gap analysis check.md`](reports/Result%20portal%20gap%20analysis%20check.md) and the notes in `research_notes/Result portal gap analysis check/`.

---

## 0. What changed from v1, and why

The v1 plan claimed that nobody had compared result-portal architectures. The gap analysis showed that claim is too broad to defend:

- Two 2026 Indonesian papers already compare a plain database design with Redis cache-aside on university portals (Putranto & Pinandito 2026; Tofan et al. 2026).
- Comparisons of per-request, cached and pre-generated pages go back to 2000 (Labrinidis & Roussopoulos, SIGMOD 2000), and front-proxy admission control was studied in 2004 (Elnikety et al., WWW 2004).
- Retry-driven collapse is an active research topic (Bronson et al. HotOS 2021; Huang et al. OSDI 2022).
- Open-loop load testing is standard method (Schroeder et al. NSDI 2006), not a contribution.
- Several v1 sources could not be verified: the NIC Odisha figures, the Baroro paper, and the LinkedIn post.

So v2 does not claim "first comparison of architectures". It moves the thesis to where the real gaps are:

1. **There is no public data on what result day actually looks like.** No board, NIC or NTA has published request rates. Every lab study, including v1, has had to invent the surge. v2 adds a field measurement study during the 2027 result season, plus RTI requests, to produce the first public characterisation.
2. **Virtual waiting rooms have never been evaluated in peer-reviewed work.** Only vendor material exists. v2 makes the waiting room the centre of the lab study, including fairness when users refresh.
3. **Correctness under load has never been measured for result portals,** and it matters: WAEC (Nigeria) withdrew its 2025 result checker over wrong results. v2 adds a correctness oracle and correction-propagation tests.
4. **Cold-cache behaviour for result lookups has been mis-framed as a stampede problem.** With each student looking up their own roll number, most cold misses are on distinct keys. v2 separates miss-ratio effects from true stampedes.
5. **Nobody turns this into capacity guidance a board can use.** v2 adds a simple, validated planning model and an open reference deployment.

---

## 1. One-paragraph summary

Every year, Indian boards and universities publish results to lakhs of students at a pre-announced minute, and portals slow down or fail. Even though the workload is about as simple as web traffic gets (read-only, keyed by roll number, data fixed in advance), there is no public measurement of these surges, no evaluation of the waiting rooms now sold to fix them, and no check that portals return the right result under load. This thesis does three things. First, it measures real result days in the 2027 season from the outside, and requests official traffic figures under the RTI Act, to produce the first public characterisation of result-day load and failure. Second, it builds **ResultBench**, an open, reproducible test harness, and uses it to compare a database-backed portal, cache-aside variants, pre-computed key-value and static designs, the multi-mirror setup boards use today, and virtual waiting rooms. Every response is checked against ground truth, and resource cost is measured. Third, it fits a simple capacity-planning model to these results and releases a reference deployment a board's IT cell can adopt. The software (portal variants, harness, monitor, reference deployment) meets the "build software" requirement. The research contribution is the field data, the waiting-room and correctness results, and the validated planning model.

---

## 2. The problem

### 2.1 What result day looks like

- The release time is announced in advance, so demand piles up before it and spikes at it.
- Almost every request is "show me the result for roll number X". The data does not change during the surge, except for occasional corrections.
- Students who see an error or a slow page refresh, often many times. This can multiply load at the worst moment.
- Boards already spread load by hand: several official URLs, DigiLocker, UMANG, SMS and IVRS. Kerala SSLC, for example, publishes on at least five portals plus apps.

### 2.2 Evidence that the problem is real and recurring

These are press reports and official statements. They are motivation, not proof. Each row must be re-opened and archived before it goes in the thesis (see Section 13).

| Event | What was reported | Source strength |
|---|---|---|
| Maharashtra SSC, 16 Jul 2021 | About 16.58 lakh students affected; schools said at least 50% could not get results until evening; the Education Minister apologised and ordered an inquiry | Strongest Indian case (Hindustan Times) |
| JEE Advanced, 12 Jun 2016 | Results went live around 9:50 am; three extra links on IIT Delhi's server did not work. The chairman said the site "did not crash" but faced about 10,000 requests/s against a server that could handle 2,000 | Single outlet, but contains the only official Indian load-to-capacity figure (about 5x) |
| CBSE Class 12, 28 May 2017 | Official site reported down seconds after declaration; 10,98,891 candidates | Two education-news sources |
| MP Board, Apr 2026 | Websites reported down; more than 16 lakh students waiting | Free Press Journal |
| Bihar Board Class 12, 23 Mar 2026 | Sites reported crashing; SMS and DigiLocker suggested. Similar reports in 2019 and 2025 | Single source per year |
| KNEC Kenya (KCSE), Jan 2025 and Jan 2026 | KNEC itself stated "up to 300,000 hits per second"; portal crashed again the next year | Official claim, unaudited |
| UCAS (UK), 2011 | Track service taken offline at about 4x the previous year's peak | Channel 4 News |
| WAEC Nigeria, 2025 | Result checker withdrawn over **wrong results**, not load | ICIR. Motivates the correctness oracle |
| Quebec, Jul 2026 | Results outage caused by the government login service, not the results store | CBC, CTV. Motivates the authentication threat to validity |

Removed from v1 until verified: the NIC Odisha CHSE 2026 figures (no figure could be found anywhere), the LinkedIn practitioner post (the URL is a profile), and the Baroro enrollment-portal paper (not found).

### 2.3 Why this matters

- **Scale:** single boards publish to 10–25 lakh students at once. Failures cause real distress on a high-stakes day and push students to unofficial sites.
- **Recurrence:** the same boards fail in different years, which suggests the fix is not widely known or not easy to adopt.
- **Transferability:** the same shape (scheduled, read-heavy, keyed lookup) applies to admit cards, counselling allotment lists, recruitment results and scholarship lists.

---

## 3. Prior work and where this thesis sits

| Area | Closest work | What it did | What it did not do |
|---|---|---|---|
| Academic-portal load tests | Putranto & Pinandito, J-PTIIK 10(2), 2026; Tofan, Parlika & Krispriyanto, JIP 12(3), 2026 | Database vs Redis cache-aside on a university portal, at fixed concurrency (JMeter, Locust) | No pre-computed or static design, no waiting room, no surge shape, no correctness check or cost seen (abstracts only, to be confirmed). Mutable schedule and registration data, not results |
| Single-design load tests | Putri et al., IEEE SIET 2017; Dave & Bhanushali, IJSR 2024; Alnuhait et al., IJAAS 2024 | One site tested with JMeter | No comparison |
| Materialised web pages | Labrinidis & Roussopoulos, SIGMOD 2000; Challenger et al., INFOCOM 1999 (IBM Olympics site) | Compared serving pages on demand, from a cache and pre-generated | Pre-dates key-value stores, open-loop load and waiting rooms |
| Cache stampede and warm-up | Vattani et al., PVLDB 2015 (XFetch); Nishtala et al., NSDI 2013 (memcache leases, cold-cluster warm-up); Bonfire, FAST 2013 | Mechanisms to prevent stampedes and warm caches | Not measured under a scheduled surge of distinct keys |
| Admission control | SEDA, SOSP 2001; Elnikety et al., WWW 2004; Chen & Heidemann (flash-crowd admission control); DAGOR, SoCC 2018; Breakwater, OSDI 2020; Rajomon, NSDI 2025 | Shedding or queuing load inside or in front of servers | **No peer-reviewed evaluation of user-facing virtual waiting rooms**, or of their fairness |
| Retries and collapse | Bronson et al., HotOS 2021; Huang et al., OSDI 2022; Isaacs et al., HotOS 2025; Google SRE book | Retries as the most common force keeping failures going | No measured amplification under a human refresh model |
| Flash-crowd measurement | Jung et al., WWW 2002; Wendell & Freedman, IMC 2011; Arlitt & Jin, World Cup '98 trace | Characterised real flash crowds | **No result-day characterisation exists** |
| Practice | Cloudflare Waiting Room, AWS Virtual Waiting Room, Queue-it; Hotstar pre-warming; China 12306 query clusters | All designs are deployed somewhere | No published measured comparison; vendor numbers only |

### 3.1 The gap (wording for the thesis)

> Result publication is a scheduled, read-only, key-addressed surge on data fixed in advance, and its failures are documented only in press reports. No public measurement of result-day traffic exists. Prior academic-portal studies compare at most a database-backed and a cache-aside design, under fixed concurrency and for mutable data (Putranto & Pinandito 2026; Tofan et al. 2026). Classic work on materialised web views and admission control (Labrinidis & Roussopoulos 2000; Elnikety et al. 2004) pre-dates modern key-value stores and user-facing waiting rooms, and no peer-reviewed study evaluates such waiting rooms at all. We found no study that (a) measures real result-day load and failure, (b) evaluates pre-computed serving and virtual waiting rooms alongside the designs boards actually use, in one reproducible harness under an open-loop surge model with user refresh, and (c) checks every response for correctness and measures resource cost. This thesis does all three for the result-lookup workload. It does not claim that caching, pre-computation or admission control help in general; that is known.

This wording must be re-checked against the full texts of the two Indonesian papers before submission (Section 13).

---

## 4. Contributions

| ID | Contribution | Why it is new | Type |
|---|---|---|---|
| C1 | **First public characterisation of result-day load and failure** in India: external availability and latency measurements of real portals across the 2027 season, plus any official figures obtained under RTI | No board, NIC or NTA traffic data is public; all prior lab work invents the surge | Measurement, data release |
| C2 | **First controlled evaluation of virtual waiting rooms** for a scheduled surge: whether they add value in front of a cheap read path, at what cost, and how fair they are when users refresh | Only vendor material exists | Experiment |
| C3 | **Correctness under load** for result portals: soft failures (HTTP 200 with no result), missing results during partial publication, and stale results after corrections, per design | No load study of these portals checks correctness; WAEC 2025 shows the risk is real | Experiment, oracle |
| C4 | **Separating miss-ratio effects from stampede effects** in cache-aside designs for per-user keys, and measuring how much coalescing, TTL jitter and XFetch actually help | Prior framing treats cold start as a stampede, which is wrong for uniform per-student keys | Experiment, analysis |
| C5 | **Measured refresh amplification and hysteresis** per design under a parameterised human refresh model | Retry collapse is known; its size under human refresh on result day is not | Experiment, model |
| C6 | **ResultBench and a validated capacity-planning model**, plus a reference deployment ("result-in-a-box") a board IT cell can run | No public benchmark or planning guide exists (a GitHub search for result-portal load tests returned nothing) | Software, guidance |

C1, C2 and C3 carry the thesis. C4 and C5 are strong supporting results. C6 is the impact route.

---

## 5. Research questions and hypotheses

**RQ1. What does result day look like? (C1)**
What arrival shape, peak-to-baseline ratio, failure onset time and recovery time do real Indian result portals show, and how do they differ by board size and hosting?
- H1a: Availability problems begin within the first few minutes after release and are worst for the largest boards.
- H1b: Portals that spread load across several origins (mirrors, DigiLocker, UMANG) show a shorter outage on the main portal than single-origin portals.
- Note: this is descriptive; the hypotheses are expectations to check, not the main finding.

**RQ2. Do designs fail where expected, and by how much? (C6, foundation)**
At each load multiple, where does each design's success rate fall below the 2 s, 5 s and 10 s deadlines, and what does it cost in CPU, memory and connections?
- H2: Pre-computed designs keep at least 99% success within 5 s at 10x the baseline capacity of the database design, on the same resources. The finding is the margin and the crossover points, not the ordering, which is expected by design.

**RQ3. Does a waiting room help, and is it fair? (C2)**
(a) In front of the database design, does a waiting room turn errors into bounded waiting and stop refresh storms? (b) In front of an already-cheap pre-computed design, does it add anything beyond what pre-computation already gives? (c) How does queue policy (first-come-first-served vs randomised at release time) affect wait-time spread and fairness when some users refresh?
- H3a: A waiting room in front of the database design gives better user outcomes at overload than doubling the database design's resources.
- H3b: In front of the pre-computed design, a waiting room only helps beyond about 10x baseline load, and only if it is itself cheaper per request than the read path.
- H3c: A naive waiting room (position lost on refresh) penalises refreshing users, which a signed-token design avoids.

**RQ4. Is the result correct under load? (C3)**
How often does each design return a soft failure, a missing result or a stale result, (a) under overload, (b) when release happens before pre-computation finishes, and (c) when a batch of corrections is published after release?
- H4: Cache-based and static designs serve stale results after a correction for up to their cache lifetime, and only explicit invalidation bounds this. Database-backed designs return the most soft failures under overload.

**RQ5. Miss ratio or stampede? (C4)**
For cache-aside at release time, what share of database load comes from distinct-key cold misses vs duplicate concurrent misses on the same key, under uniform and skewed key patterns?
- H5: Under uniform keys, distinct-key misses dominate, so coalescing and XFetch barely help and only pre-warming or pre-computation removes the cold-start penalty. Under skewed keys, duplicate misses become significant and coalescing helps.

**RQ6. How much do refreshes amplify load, and does the system recover? (C5)**
What is the ratio of requests to unique users under a parameterised refresh model, per design, and once arrivals fall back below capacity, does the system recover or stay overloaded?
- H6: The database and cache-aside designs show amplification above 2x and stay overloaded after the spike ends (a metastable state) when refresh probability is high. Pre-computed designs and waiting rooms do not.

---

## 6. Study 1: Field measurement of the 2027 result season (RQ1)

### 6.1 External monitor

A small, polite availability monitor (part of the delivered software):

- **Targets:** official result portals for a set of 8–12 releases between Feb and Jun 2027, for example JEE Main, CBSE Class 10 and 12, UP Board, Bihar Board, Maharashtra HSC/SSC, MP Board, Karnataka, NEET, and AKTU semester results, plus DigiLocker and UMANG result pages. Exact dates are announced by each body a few days ahead; the monitor must be ready by early Feb 2027.
- **What it fetches:** the public landing page and the result form page only. It **does not submit roll numbers** and does not try to load-test anything.
- **Rate:** one request every 15–30 s per target per vantage point, from about 60 minutes before release to 3 hours after. This is far below a single student's refresh rate and adds no meaningful load.
- **Vantage points:** at least two (home broadband in Lucknow, one cloud VM in an Indian region), to separate portal failure from local network problems.
- **Recorded:** DNS result, connect time, time to first byte, total time, HTTP status, page size, a content fingerprint (to catch "200 OK" error pages), and hosting and CDN hints from DNS and response headers.
- **Context:** release time, candidate count and official alternative channels for each event, taken from the board's notice and archived.

### 6.2 Official data under RTI

File Right to Information requests (RTI Act 2005) with NIC, CBSE, NTA, AKTU and two or three state boards. Ask for: peak requests per second or per minute on result day, concurrent users, number of servers or VMs, CDN use, and any post-incident report. Replies are due within 30 days; file in Nov 2026 so answers arrive before the lab grid is fixed.

### 6.3 AKTU partnership (stretch, high value)

Ask the university's IT cell, through the mentor, for anonymised access-log aggregates (per-second request counts, status codes, no roll numbers or IPs) from a past and an upcoming AKTU semester result release. If granted, this gives the first real result-day arrival curve, and lets the monitor be checked against server-side truth.

### 6.4 Output

- A public, anonymised dataset of monitor readings per event.
- Per-event curves: availability, time to first byte, onset of failure, duration, recovery.
- A surge model fitted from the data (pre-release ramp, burst, decay) used to drive Study 2. If field data is thin, fall back to the published anchors: the World Cup '98 trace (5–10x ramp before scheduled events), JEE Advanced 2016 (about 5x offered load over capacity) and UCAS 2011 (about 4x previous peak).

---

## 7. Study 2: Controlled comparison with ResultBench (RQ2–RQ6)

### 7.1 Designs under test

All designs share the same synthetic dataset, the same API (`GET /result?roll=<number>`), the same language and framework, and the same container CPU and memory limits.

| ID | Design | Read path | Why it is included |
|---|---|---|---|
| A | Database-backed | App queries PostgreSQL every request | Typical simple portal; baseline capacity anchor |
| M | Multi-mirror | Two or three copies of A behind DNS or link splitting, as boards do today | **The real status quo**, missing from v1 |
| B0 | Cache-aside | Redis first; on miss, PostgreSQL then fill | The common "add a cache" fix |
| B1 | Cache-aside + coalescing | B0, with one database query per key in flight | Stampede mitigation |
| B2 | Cache-aside + XFetch | B0, with probabilistic early refresh and TTL jitter | Published stampede mitigation |
| B3 | Cache-aside + pre-warm | B0, with the cache filled before release | Separates "cold" from "cache-aside" |
| C1 | Pre-computed, key-value | All results written to Redis before release; no database on read path | Pre-computation |
| C2 | Pre-computed, static | One JSON file per roll number served by Nginx | Edge/CDN-origin style |
| D-A | Waiting room + A | Admission layer in front of A | Can a waiting room replace pre-computation? |
| D-C | Waiting room + C1 or C2 | Admission layer in front of C | Does a waiting room add anything to a cheap read path? |

Waiting-room variants, kept small:
- **Policy:** first-come-first-served vs randomised order for everyone who arrived before release (Cloudflare offers both; no study compares them).
- **Implementation:** naive (position held in server memory, lost on refresh) vs signed token (position carried in a signed cookie, kept on refresh).

### 7.2 Workload

- **Open-loop arrivals** (k6 arrival-rate executors), following Schroeder et al. Report k6 dropped iterations so the generator never hides overload.
- **Surge shape** fitted from Study 1, or from the anchors in 6.4 if field data is thin: pre-release ramp, burst at release, decay over 30–60 minutes.
- **Load levels** as multiples of design A's measured saturation point: 0.5x, 1x, 2x, 5x, 10x, 20x. The 5x level is anchored by JEE Advanced 2016.
- **Human refresh model** on top of arrivals, with parameters stated as assumptions and varied:
  - refresh after an error with probability p (0, 0.5, 0.9), after a random delay;
  - impatience refresh when no response within T seconds (5, 10, 20), even without an error;
  - give up after k attempts.
- **Keys:** uniform (each student looks up their own roll number, with occasional repeats) and skewed (Zipf, for toppers, popular schools and family members re-checking).
- **Data:** synthetic, 1 million students (optionally 5 million); roll number, name, marks, total, division and rank. No real student data anywhere.

### 7.3 Correctness scenarios (RQ4)

The oracle compares every response with ground truth and classifies it as correct, wrong, missing, stale, soft failure (HTTP 200 without a result) or hard failure.

1. **Overload:** correctness at every load level.
2. **Early release:** release time arrives while pre-computation is 50%, 90% or 99% done.
3. **Correction batch:** 1% of results are revised at release + 30 min (as after re-totalling). Measure how long each design keeps serving the old value, with and without explicit invalidation.

### 7.4 Fault injection (kept small)

Kill the cache node at peak; slow the database by 10x for 60 s. Measure recovery time and whether the system returns to normal once the fault clears (hysteresis).

### 7.5 Experimental design

Run a core grid first, then add factors only where results are interesting.

| Block | Designs | Factors varied | Answers |
|---|---|---|---|
| Core | A, M, B0, C1, C2 | Load level; uniform keys; refresh off | RQ2 |
| Cache | B0–B3 | Load level; uniform vs skewed; cold vs warm | RQ5 |
| Waiting room | A, D-A, C1, D-C | Load level above capacity; policy; implementation; refresh on | RQ3 |
| Refresh | A, B0, C1, D-A | Refresh parameters; spike then drop | RQ6 |
| Correctness | All | Overload; early release; correction batch | RQ4 |
| Faults | B0, C1, D-C | Cache kill; slow database | Robustness |

Controls:
- Same CPU and memory limits for every design; load generator pinned to separate cores, and runs discarded if it saturates.
- A fixed tuning budget per design (for example, two days), with every setting documented, to avoid tuning one design harder than another.
- At least 5 repetitions per configuration; report medians with bootstrap confidence intervals; fixed random seeds for data and traffic.
- Follow the reproducibility principles of Papadopoulos et al. (IEEE TSE 2019) and Uta et al. (NSDI 2020).

### 7.6 Metrics

| Group | Metrics |
|---|---|
| User outcome | Success within 2 s, 5 s and 10 s; latency p50, p95, p99; time to first correct result per user; share of users who give up |
| System | Throughput; error rate (5xx, timeouts); database queries/s and connections at peak; cache hit ratio; distinct-key vs duplicate-key misses (RQ5) |
| Amplification | Requests per unique user; time to recover after the spike or fault; whether load stays high after arrivals drop |
| Correctness | Wrong, missing, stale and soft-failure rates; staleness window after corrections |
| Cost | CPU-seconds and peak memory per 1 lakh users served; preparation time before release; estimated cloud cost from one validation run on standard instances |
| Waiting room | Wait-time distribution; fairness as the rank correlation between arrival order and service order; penalty to refreshing users |
| Operations (qualitative) | Number of moving parts; what must be done before release; failure modes |

---

## 8. Study 3: Capacity-planning model and reference deployment (C6)

### 8.1 Model

A simple model that a board IT cell can use: given candidate count, expected arrival shape, refresh behaviour and design, estimate the capacity needed to meet a target (for example, 99% of users get a correct result within 5 s).

- Start from a queueing approximation (arrival curve vs per-design service capacity), with refresh as a feedback term on arrivals.
- Fit per-design service capacity from Study 2.
- **Validate** by predicting held-out Study 2 runs, and where possible the Study 1 events or AKTU data. Report prediction error openly.
- Output: a one-page planning table (rows: board size from 1 lakh to 30 lakh students; columns: design; cells: cores and memory needed, and expected success rate).

### 8.2 Reference deployment ("result-in-a-box")

An open-source, documented setup that runs the best-performing design from Study 2 (likely pre-computed static files plus an optional waiting room) with:
- a pre-release materialisation script with a completeness check;
- a correction-publishing script with invalidation;
- a release-day checklist;
- a dry-run load test using ResultBench.

Stretch goal: offer it to AKTU's IT cell for a dry run, or a real semester result release, with their approval.

---

## 9. Threats to validity

1. **Single-machine lab.** National load cannot be reproduced. Mitigation: load as multiples of baseline capacity, relative comparisons, and one validation run on cloud hardware.
2. **Synthetic surge and refresh parameters.** No human refresh data exists. Mitigation: calibrate from Study 1, vary parameters, report sensitivity.
3. **External monitoring is not server-side truth.** The monitor sees availability, not request rates. Mitigation: two vantage points; compare with RTI or AKTU data where available; state limits.
4. **No real CDN or WAN.** Mitigation: Nginx static serving as a stand-in; no CDN claims.
5. **Implementation bias.** Mitigation: fixed tuning budget, one language, all settings published.
6. **Out-of-scope failure sources.** Login and captcha services (Quebec 2026), bots and DDoS (Australian eCensus 2016), and DNS failures can break real portals regardless of design. Mitigation: state openly; the field study records which failures happened.
7. **Press evidence.** Motivation only; every item archived and checked (Section 13).
8. **Load generator limits.** Mitigation: monitor generator CPU, discard saturated runs, use several generator processes.

---

## 10. Ethics and data

- **No load testing of real portals.** The monitor makes one light request per 15–30 s per target, fetches only public pages and never submits roll numbers.
- **No real student data** in the lab. AKTU data, if obtained, is aggregate counts only, with written approval from the university.
- RTI replies are public records and will be cited as such.
- Get the mentor's sign-off, and the department ethics committee's if required, before the monitor runs.

---

## 11. Scope

**In scope:** result lookup by roll number; the designs in 7.1; the 2027 field season; correctness, cost and waiting-room fairness; a planning model and reference deployment.

**Out of scope (future work):** login, date of birth and captcha; multi-region and real CDN testing; result computation and moderation; write-heavy surges (counselling seat allotment, Tatkal-style booking); roll-number enumeration attacks (short discussion only).

---

## 12. Timeline (Nov 2026 – Jun 2027)

The 2027 result season fixes the schedule: the monitor must be running by early February.

| When | Work | Output |
|---|---|---|
| Nov 2026, weeks 1–2 | Mentor review; evidence repair (Section 13); file RTI requests; request AKTU log access | Approved plan; RTIs filed |
| Nov 2026, weeks 3–4 | Synthetic data generator; correctness oracle; design A; find A's saturation point | Repo skeleton; baseline number |
| Dec 2026 | External monitor built and tested on smaller releases (university and semester results); designs M, B0–B3, C1, C2 | Monitor v1; working core designs |
| Jan 2027 | Waiting room (both policies, both implementations); refresh model in k6; pilot core grid | Pilot results; harness fixed |
| Feb–May 2027 | **Field season:** monitor every target release. In parallel: core, cache, waiting-room and correctness blocks | Field dataset; main lab results |
| Mar–Apr 2027 | Refresh and fault blocks; fit surge model from field data and re-run key configurations with it | Calibrated results |
| Apr 2027 | Capacity model fit and validation; reference deployment; cloud validation run | Planning table; result-in-a-box |
| May 2027 | Thesis writing; paper draft | Full draft |
| Jun 2027 | Revisions; artifact packaging; submission | Final thesis; public repo and dataset |

Buffer: the lab blocks are ordered by importance (core, waiting room, correctness, cache, refresh, faults). If time runs short, cut faults first, then shrink the refresh block. Never cut the field season; it cannot be re-run until 2028.

---

## 13. Evidence repair before the mentor meeting

These items from the gap analysis must be done in the first two weeks. Many could not be opened from the research session's network, so they need a normal browser.

1. **Indonesian papers (decides the gap wording):** read the full texts of Putranto & Pinandito (J-PTIIK 10(2), 2026) and Tofan et al. (JIP 12(3):493–502, 2026). Confirm whether either checks correctness, measures cost, or tests a pre-computed design.
2. **Venue searches:** search IEEE Xplore, ACM DL, Scopus, Google Scholar, Shodhganga and ProQuest with the queries in Section 15. Above all, search for peer-reviewed evaluations of virtual waiting rooms, since C2 depends on there being none.
3. **Press sources:** open, archive (PDF or Wayback) and quote exactly every row in Section 2.2. Look for coverage in TOI, The Hindu, Indian Express, HT, NDTV or India Today.
4. **NIC Odisha (informatics.nic.in/news/1643):** if the page exists and the figures check out, add it back as the "portal that coped" example, with exact units.
5. **Huang et al. OSDI 2022:** check the ">50% retries" and "35% load-spike triggers" figures against the paper, not the slides.
6. **References marked [K] in Section 16:** check title, venue, year and pages before they go in the bibliography.

---

## 14. Deliverables and impact

Implementation status: the software for all three studies is in [`resultbench/`](resultbench/README.md) (designs, generator, oracle, runner, experiment grids, analysis, capacity model, field monitor, result-in-a-box). Design decisions and assumptions are documented in [`resultbench/docs/methodology.md`](resultbench/docs/methodology.md).

1. **ResultBench:** open-source harness with all portal designs, the data generator, k6 scenarios with the refresh model, the correctness oracle, monitoring configs and analysis notebooks, with a one-command reproduction guide.
2. **Result-day field dataset:** anonymised monitor readings for the 2027 season, plus RTI replies.
3. **Capacity-planning table and result-in-a-box** reference deployment, written for a board's IT cell.
4. **M.Tech thesis.**
5. **Paper:** one conference paper with an artifact submission. Candidate venues (check scope and deadlines): ACM/SPEC ICPE (performance engineering, has an artifact track), COMSNETS (India), ACM ICEGOV (e-governance, for the field study and planning guide). A short practitioner summary for NIC and state board IT cells.

---

## 15. Literature search log (to do)

Run on Scopus, IEEE Xplore, ACM DL, Springer, Google Scholar, Shodhganga and ProQuest. Record for each hit: year, venue, system, workload, designs compared, correctness checked, cost measured.

- "virtual waiting room" OR "online queue" AND (evaluation OR fairness)
- "flash crowd" AND "web application" AND (cache OR static OR "pre-rendering")
- "examination result" OR "result portal" AND (scalability OR load)
- "result website" AND JMeter
- "SIAKAD" AND (Redis OR "cache-aside")
- "WebView materialization"; "dynamic content caching" AND Olympics
- "cache stampede" OR "thundering herd" AND evaluation
- "metastable failure"; "retry amplification"
- "admission control" AND "web" AND overload
- Indian e-governance portal performance (NIC, NICSI, state boards)

---

## 16. References

[V] = title, venue and year confirmed online during the gap analysis. [K] = from background knowledge or secondary summaries; check before use. [A] = abstract or snippet only; read the full text.

**Closest work and load tests**
- M. A. S. Putranto, A. Pinandito. "Analisis Kinerja Cache Redis pada RESTful API Berbasis Express.js." J-PTIIK 10(2), 2026. https://j-ptiik.ub.ac.id/index.php/j-ptiik/article/view/15978 [A]
- Tofan, Parlika, Krispriyanto. "Perancangan Arsitektur Cache-Aside Menggunakan Redis pada Sistem Informasi Akademik." JIP 12(3):493–502, 2026. DOI 10.33795/jip.v12i3.9675 [A]
- Putri, Hadi, Ramdani. IEEE SIET 2017. https://ieeexplore.ieee.org/document/8304099/ [A]
- Dave, Bhanushali. IJSR 13(1), 2024. https://www.ijsr.net/getabstract.php?paperid=SR24121010827 [A]

**Materialisation and caching**
- A. Labrinidis, N. Roussopoulos. "WebView Materialization." SIGMOD 2000, pp. 367–378. [V]
- J. Challenger, A. Iyengar, P. Dantzig. "A Scalable System for Consistently Caching Dynamic Web Data." INFOCOM 1999, pp. 294–303. [V]
- A. Vattani, F. Chierichetti, K. Lowenstein. "Optimal Probabilistic Cache Stampede Prevention." PVLDB 8(8):886–897, 2015. DOI 10.14778/2757807.2757813 [V]
- R. Nishtala et al. "Scaling Memcache at Facebook." NSDI 2013, pp. 385–398. [V]
- Y. Zhang et al. "Warming Up Storage-Level Caches with Bonfire." FAST 2013. [V]

**Admission control and overload**
- M. Welsh, D. Culler, E. Brewer. "SEDA: An Architecture for Well-Conditioned, Scalable Internet Services." SOSP 2001. [K]
- S. Elnikety, E. Nahum, J. Tracey, W. Zwaenepoel. "A Method for Transparent Admission Control and Request Scheduling in E-Commerce Web Sites." WWW 2004. [V]
- X. Chen, J. Heidemann. Flash-crowd mitigation via adaptive admission control. ACM TOIT. https://ant.isi.edu/~johnh/PAPERS/Chen03b.pdf [V, details to check]
- H. Zhou et al. "Overload Control for Scaling WeChat Microservices" (DAGOR). SoCC 2018. [K]
- I. Cho et al. "Overload Control for µs-scale RPCs with Breakwater." OSDI 2020. [K]
- Rajomon. NSDI 2025. https://www.usenix.org/conference/nsdi25/presentation/xing [V]
- Google SRE book, chapters "Handling Overload" and "Addressing Cascading Failures." [K]

**Retries and metastable failures**
- N. Bronson, A. Aghayev, A. Charapko, T. Zhu. "Metastable Failures in Distributed Systems." HotOS 2021. [K]
- L. Huang et al. "Metastable Failures in the Wild." OSDI 2022. [V]
- R. Isaacs et al. HotOS 2025. DOI 10.1145/3713082.3730380 [V]
- M. Brooker. "Timeouts, Retries, and Backoff with Jitter." Amazon Builders' Library. [K]

**Flash crowds and workload method**
- J. Jung, B. Krishnamurthy, M. Rabinovich. "Flash Crowds and Denial of Service Attacks." WWW 2002. [K]
- P. Wendell, M. J. Freedman. "Going Viral: Flash Crowds in an Open CDN." IMC 2011, pp. 549–558. DOI 10.1145/2068816.2068867 [V]
- M. Arlitt, T. Jin. World Cup '98 workload characterisation. [K]
- B. Schroeder, A. Wierman, M. Harchol-Balter. "Open Versus Closed: A Cautionary Tale." NSDI 2006. [V]
- P. Ramamurthy et al. "Remote Profiling of Resource Constraints of Web Servers Using Mini-Flash Crowds." USENIX ATC 2008. [V] (a probing method; relevant to Study 1's ethics)

**Benchmarking method**
- A. V. Papadopoulos et al. "Methodological Principles for Reproducible Performance Evaluation in Cloud Computing." IEEE TSE, 2019. DOI 10.1109/TSE.2019.2927908 [V]
- A. Uta et al. "Is Big Data Performance Reproducible in Modern Cloud Networks?" NSDI 2020. [V]

**Press and official sources (motivation only)**
Full URLs and verification status are in `reports/Result portal gap analysis check.md`, Section "Section 2.2 evidence".
