# Surviving Result Day
### A Comparative Study of Architectures for High-Surge Examination Result Portals

**Thesis plan and research problem statement**
Author: Sankalp Pathak, M.Tech (Computer Science), AKTU Lucknow
Status: Draft v1, written 28 Oct 2026
Purpose: one document that holds the problem, the evidence, the plan and the open decisions, so we can hand it to the mentor and build from it.

---

## 1. One-paragraph summary

Every year, when a board or university declares results, lakhs of students open the result website in the same few minutes. The site slows down or crashes, and students are told to try SMS or DigiLocker. This is a well-known, repeated, public failure. We will build a result portal in four different architectures (a plain database-backed site, a cached site, a pre-computed site, and a pre-computed site with a waiting room), then replay a realistic result-day traffic spike against each one under the same hardware limits. We will measure who survives, how fast they answer, and what each design costs. The software we build (the portal variants plus a reproducible test harness) satisfies the "build software" requirement. The research contribution is a controlled comparison that, as far as we found, does not exist in the literature for result portals.

---

## 2. The problem

### 2.1 What happens on result day

- Result declaration is a scheduled event. Everyone knows the exact time.
- Demand is concentrated into minutes, and it is read-heavy: almost every request is "show me the result for roll number X".
- The data is immutable once published. A result does not change while students are checking it.
- Despite this, portals crash.

### 2.2 Evidence that this is a real, repeated problem

These are news and press reports (not academic sources). They show the problem recurs across boards and years.

| Event | What was reported |
|---|---|
| CBSE Class 12, 2017 | Official site crashed seconds after declaration |
| JEE Advanced, 2016 | Portal could not bear the traffic; extra links were created but did not help |
| Anna University, 2021 | Servers crashed after results were declared |
| Bihar Board Class 12, 2026 | Sites reported crashing; SMS and DigiLocker suggested as alternatives |
| KCET, 2026 | Website crashed after result and topper list release (6 June) |
| Uttarakhand Board, 2026 | Official portals slowed or crashed |

A positive example also exists: NIC Odisha reports that the CHSE Odisha 2026 portal coped with the load. It describes a dedicated session-storage VM, two Memcache VMs, and PostgreSQL as the backend. It reports 1,846,050 hits on 20 May and 319,387 active users in the last 30 minutes of the peak. This is a press release, not a controlled study, so it tells us what one team did, not what works best.

### 2.3 The research gap

- General flash-crowd research exists (adaptive CDNs, web-server hot-spot techniques, CoralCDN measurements), but it is mostly old and not specific to result portals.
- Generic load-testing papers on college websites exist, but they test a single design and do not compare architectures.
- The closest recent work I found studies university enrollment portals in the Philippines. Enrollment is transactional (writes and conflicts), while results are immutable and read-heavy, so the engineering answer is different.
- Practitioner posts already describe the likely best design: compute everything before release, store results by roll number in a key-value store, and add a waiting room. But advice in a blog post is not a measured comparison.

**The gap:** no controlled, reproducible comparison of result-portal architectures under a replayed result-day surge, with correctness checked and cost measured.

> Evidence status: this gap was found through web searches only. A proper literature check (IEEE Xplore, ACM DL, Springer, Google Scholar, plus Indian journals) must be done before we claim novelty in writing. See Section 12.

---

## 3. Research questions and hypotheses

**RQ1. Architecture comparison.**
How do four result-portal architectures compare under the same surge, on the same hardware budget?
- H1: The plain database-backed design (A) fails first. Caching (B) delays failure. Pre-computed designs (C, D) sustain the highest load.

**RQ2. Pre-computing vs caching.**
Does pre-computing every result before release beat caching on demand, especially at the first seconds after release when caches are cold?
- H2: Cache-based designs show a latency and error spike at the first seconds (cold cache, many simultaneous misses on the same keys, or "cache stampede"). Pre-computed designs do not.

**RQ3. Admission control.**
Does adding a waiting room (admission control) improve user outcomes more than simply handling more load?
- H3: Under overload beyond capacity, a waiting room converts errors into bounded waiting, and prevents retry storms from multiplying the load.

**RQ4. Retry behaviour.**
How much do user retries (refresh, resubmit) amplify the load once the site slows down?
- H4: Failures cause retries, retries add load, and load causes more failures. A practitioner post claims retries can multiply requests substantially; we will measure it rather than assume it.

---

## 4. System designs under test

All four use the same synthetic dataset, the same API (`GET /result?roll=<number>`), the same container CPU and memory limits, and the same application language.

| ID | Name | Read path | What it represents |
|---|---|---|---|
| A | Baseline | App server queries PostgreSQL for every request | How a typical simple portal is built |
| B | Cache-aside | App checks Redis first; on miss, queries PostgreSQL and fills the cache. Variants: with and without request coalescing, with and without TTL jitter | The common "add a cache" fix |
| C | Pre-computed | All results are materialized before release into a key-value store or static files keyed by roll number. Read path = one key lookup, no database | The "do the work before 5 PM" approach |
| D | Pre-computed + waiting room | C plus an admission layer that lets a safe number of requests through and holds the rest briefly with a "your result is loading" page | Handling overload gracefully |

Design notes:
- For C, test two storage forms: (C1) key-value store and (C2) static JSON files served directly by Nginx, which acts like a CDN origin.
- For D, the waiting room can start simple (token bucket plus a queue) and become a signed-token queue if time allows. Measure the wait-time distribution to check fairness.
- Keep "operational complexity" as a qualitative column in the results: number of moving parts, what must be done before release, what can go wrong.

---

## 5. Workload model (how we create result day)

### 5.1 Why not just "N users for 5 minutes"

A fixed number of virtual users that wait for each reply (a closed workload) slows itself down when the server slows down. Real people do not. They keep arriving. So we use an **open-loop, arrival-rate workload** (k6's constant and ramping arrival-rate executors), and we model retries explicitly on top.

### 5.2 Shape of the traffic

1. **Pre-release ramp.** Traffic rises as students wait and refresh before the announced time.
2. **Burst at t0.** A sharp jump the moment results are declared.
3. **Decay.** Traffic falls over 30–60 minutes.
4. **Retry behaviour.** Requests that fail or time out are retried by a fraction of users, after a short random delay.

### 5.3 Making a laptop test meaningful (scale-free load)

One machine cannot generate national-scale traffic. So we do not claim absolute numbers. Instead:
- First, find the **saturation point of design A** on our hardware (the request rate where it starts failing).
- Then express all load as **multiples of that capacity**: 0.5x, 1x, 2x, 5x, 10x.
- Compare how each design behaves at each multiple.

This lets us compare designs fairly and report relative gains. We then use published figures (for example NIC Odisha's peak numbers) only as a sanity check for the shape and scale of real events, not as targets we must reach.

### 5.4 Key access pattern

- Baseline: roll numbers drawn uniformly from the dataset.
- Variant: a skewed pattern where a small set of keys (toppers, popular schools, re-check requests) are requested much more often, to test hot keys.

### 5.5 Data

- Fully synthetic: 1 million students (optionally 5 million) with roll number, name, subject marks, total, division and rank.
- No real student data is used anywhere in this study.

---

## 6. Experimental design

### 6.1 Factors

| Factor | Levels |
|---|---|
| Architecture | A, B (variants), C1, C2, D |
| Load level | 0.5x, 1x, 2x, 5x, 10x of A's capacity |
| Cache state at t0 | Cold, warm |
| Key distribution | Uniform, skewed |
| Retry behaviour | Off, on |
| Fault injection | None; kill cache node; slow database |

Not every combination is needed. Start with a core grid and add factors only where results are interesting.

### 6.2 Controls

- Same Docker CPU and memory limits for every design.
- Same application framework and language across designs.
- Load generator on separate cores; its own CPU use is monitored so it is not the bottleneck.
- At least 5 repetitions per configuration; report median and bootstrap confidence intervals.
- Fixed random seeds for data and traffic so every run can be repeated.

### 6.3 Metrics

**Performance**
- Success rate within 2 s, 5 s and 10 s deadlines
- Latency p50, p95, p99
- Error rate (5xx and timeouts)
- Throughput achieved
- Time to recover after the peak

**Correctness**
- Wrong-result rate (each response checked against ground truth; must be zero)
- Missing-result rate
- Stale-result rate

**Cost and effort**
- CPU-seconds and peak memory
- Database connections and queries per second at peak
- Preparation time before release (for C and D, how long materialization takes)

**User experience (for D)**
- Waiting-time distribution
- Fairness: whether wait time depends on arrival order

---

## 7. Tools and stack (all runnable at home)

| Purpose | Choice (can change) |
|---|---|
| Containers | Docker Compose |
| App server | One language across all designs (for example Python FastAPI or Node.js) |
| Database | PostgreSQL |
| Cache / key-value store | Redis |
| Reverse proxy / static serving | Nginx |
| Load generation | k6 (arrival-rate executors) |
| Monitoring | Prometheus and Grafana |
| Analysis | Python (pandas, matplotlib) |
| Repo and reproducibility | GitHub repo with seed script, compose files and run scripts |

---

## 8. Threats to validity (state these openly in the thesis)

1. **Single-machine testing.** We cannot reproduce national load. Mitigation: scale-free multiples of baseline capacity and relative comparisons only.
2. **Synthetic traffic.** Real behaviour may differ. Mitigation: base the shape on published reports, vary parameters, and test several shapes.
3. **No real WAN or CDN.** Mitigation: emulate edge caching with Nginx; do not claim CDN results.
4. **Load generator limits.** One generator tops out at a modest request rate. Mitigation: monitor generator CPU; discard runs where it saturates; use multiple generator processes if needed.
5. **Container limits are not production hardware.** Mitigation: report results as relative.
6. **Implementation quality bias.** One design may be tuned harder than another. Mitigation: set a fixed tuning budget per design and document every setting.
7. **Press-report evidence.** The crash reports and the NIC Odisha figures are not peer-reviewed. Mitigation: use them for motivation only, not as proof.

---

## 9. Scope

**In scope**
- Read-heavy result lookup by roll number
- The four architectures above
- Replayed surge, retries, cold and warm caches, simple fault injection

**Out of scope (can be future work)**
- Real student data, authentication with date of birth or captcha
- Multi-region deployment and real CDN testing
- Result computation and moderation pipeline
- Security attacks such as roll-number enumeration (worth a short discussion section)

**Possible extensions if time allows**
- A counselling seat-allotment module that consumes results (deadline surge plus allotment correctness)
- A mini-Tatkal booking study (write surge on scarce inventory)
- An accessibility pass on the portal pages

---

## 10. Timeline (Nov 2026 – Jun 2027)

| When | Work | Output |
|---|---|---|
| Nov 2026, weeks 1–2 | Mentor review of this plan; formal literature search; fix scope | Approved proposal |
| Nov 2026, weeks 3–4 | Synthetic data generator; design A built; baseline capacity found | Repo skeleton, first benchmark |
| Dec 2026 | Designs B and C built; load generator scripts; monitoring | Working A, B, C |
| Jan 2027 | Design D (waiting room); correctness checker; pilot experiments | Pilot results, fix the harness |
| Feb 2027 | Full experiment grid, repetitions | Raw results |
| Mar 2027 | Fault injection, retry modelling, hot-key variants | Extended results |
| Apr 2027 | Analysis, charts, interpretation; optional extension module | Draft results chapter |
| May 2027 | Thesis writing | Full draft |
| Jun 2027 | Revisions, mentor feedback, submission prep | Final thesis |

Buffer: treat Feb–Mar as the flexible months. If the grid is too large, shrink factors before cutting designs.

---

## 11. Deliverables

1. Open-source repo containing: portal variants A–D, synthetic data generator, load scripts, monitoring configs, analysis notebooks.
2. A one-command reproduction guide so a reader can rerun every experiment.
3. M.Tech thesis document.
4. Optional: a short paper (empirical software engineering or systems venue) if results are strong.

---

## 12. Open decisions and next steps

**Decisions needed**
- Application language and framework (pick one and keep it fixed).
- Dataset size (1 million vs 5 million).
- Whether to use cloud credits for one validation run on stronger hardware.
- Whether the thesis stays a single-problem study or includes the counselling module.
- Mentor's expectation on the amount of "built software" vs "evaluation".

**Immediate next steps**
1. Share this file with the mentor and collect feedback on scope.
2. Run a formal literature search and record every relevant paper in a table (title, venue, what they tested, what they did not).
3. Build design A and find its saturation point; that number anchors every later experiment.
4. Write the correctness checker early, so every later design is validated from day one.

---

## 13. Search log for the literature check (to do)

Suggested queries for Scopus, IEEE Xplore, ACM DL, Springer and Google Scholar:
- "flash crowd" AND "web application" AND (cache OR "static" OR "pre-rendering")
- "examination results" OR "result portal" AND "scalability" OR "load"
- "admission control" OR "virtual waiting room" AND "web"
- "cache stampede" OR "thundering herd" AND evaluation
- "open-loop" AND "load testing" AND "arrival rate"
- Indian e-governance portal performance (NIC, NICSI, state boards)

Record for each hit: year, venue, system studied, workload type, whether architectures were compared, whether correctness and cost were measured.

---

## 14. References and sources used so far

Press, institutional and practitioner sources (motivation only):
- NIC Odisha, "Successful Publication of CHSE Odisha Annual Higher Secondary Examination Results 2026": https://informatics.nic.in/news/1643
- Bihar Board Class 12 Result 2026 website crashing (Physics Wallah): https://www.pw.live/bseb/exams/bihar-board-result-2026-class-12-website-crashing
- KCET 2026 result website crash (Careers360): https://engineering.careers360.com/articles/kcet-2026-result-website-crashed
- Anna University results 2021, servers crash (AglaSem): https://news.aglasem.com/anna-university-results-2021-declared-at-student-login-annaunivedu-servers-crash
- CBSE Class 12, 2017 site crash (Amar Ujala): https://results.amarujala.com/results-alert/cbse-class-12th-board-results-2017-declared-official-website-cbse-nic-in-crashed-know-how-to-check-scores-on-other-websites
- JEE Advanced 2016 results, extra links in vain (PaGaLGuY): https://www.pagalguy.com/articles/jee-advanced-2016-results-three-links-created-to-ease-traffic-of-portal-but-in-vain-2678?amp=1
- Practitioner post on result-day design (precompute, key-value store, admission control): https://in.linkedin.com/in/eshaansh

Technical and research sources:
- Flash crowd techniques for web servers (EURECOM): https://www.eurecom.fr/publication/1489/download/ce-felbpa-041018.pdf
- Wendell and Freedman, "Going Viral: Flash Crowds in an Open CDN", IMC 2011 (slides): https://sns.cs.princeton.edu/assets/slides/2011-imc-wendell.pdf
- Adaptive CDN for flash crowds (FCAN): https://eceasst.org/index.php/eceasst/article/download/2398/2570/2581
- Mini-flash crowds for finding server bottlenecks (Ramamurthy et al.): https://pages.cs.wisc.edu/~pratap/papers/pratap_ramamurthy_mfc.pdf
- University enrollment portal performance under peak load (Baroro): https://independent.academia.edu/JasonSBaroro
- Load testing arrival-rate executors, k6 vs Locust: https://mojoauth.com/blog/load-testing-auth-flows-10k-requests-per-sec
- Cache stampede mitigation (coalescing, jitter, stale-while-revalidate): https://stackharbor.com/en/knowledge-base/cache-stampede-mitigation/
- Cache stampede prevention, XFetch (Vattani et al. cited here): https://oneuptime.com/blog/post/2026-01-30-cache-stampede-prevention/markdown

**Reference check note:** several entries above are news pages, blogs or slides found through web search. Before any of them goes into the thesis bibliography, open each one, confirm the details, and replace blog-level sources with peer-reviewed ones wherever possible.
