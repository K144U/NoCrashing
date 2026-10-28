# Systems/networking literature overlapping the result-portal flash-crowd thesis (RQ1–RQ4)

Verification legend used throughout:
- **[V]** = title/authors/venue/year confirmed by a web search or fetch in this session (Oct 2026).
- **[K]** = well-known citation from prior knowledge, NOT re-checked online this session. Check it before it goes into a bibliography.
- **[U]** = found only via a secondary source or a blocked page (arXiv could not be fetched from this session). Treat as unverified.

Note: the thesis plan (`/home/user/NoCrashing/result-portal-thesis-plan.md`, section 14) currently cites only EURECOM flash-crowd techniques, Wendell & Freedman IMC 2011 (slides, not the paper), FCAN, Ramamurthy et al., and XFetch *through a 2026 blog post*. None of the papers on overload control, metastability, open-vs-closed load, or cache stampedes are cited in their primary form.

## Q1. Flash crowds: classic and newer work. Is "mostly old and not specific to result portals" accurate?

### Takeaway
The claim is half right. Measurement studies of web flash crowds really are mostly from 1999 to 2011, and none covers exam-result portals. But the *mechanisms* the thesis tests (overload control, retry-driven metastable failure, cache stampede) have active, recent literature (2018–2025) at top venues (OSDI, NSDI, SoCC, HotOS), and the plan does not cite it. An examiner would likely say the plan undersells recent related work.

### Cited Findings
- Jung, Krishnamurthy & Rabinovich, "Flash Crowds and Denial of Service Attacks: Characterization and Implications for CDNs and Web Sites," WWW 2002 [K]. It is the standard reference for telling flash crowds from DoS (flash crowds come from many existing client clusters, and per-client request rates stay normal). It also proposes adaptive CDN changes. — [ACM DL](https://dl.acm.org/doi/10.1145/511446.511485)
- Wendell & Freedman, "Going Viral: Flash Crowds in an Open CDN," IMC 2011 [V]. It analyses over four years of CoralCDN traffic (more than 33 billion HTTP requests) and evaluates elastic redirection and resource provisioning during flash crowds. The plan cites the *slides*. The paper PDF should be cited instead. — [Paper PDF](https://www.cs.princeton.edu/~mfreed/docs/flash-imc11.pdf); [IMC copy](https://conferences.sigcomm.org/imc/2011/docs/p549.pdf)
- Ramamurthy, Sekar, Akella, Krishnamurthy & Shaikh, "Remote Profiling of Resource Constraints of Web Servers Using Mini-Flash Crowds," USENIX ATC 2008 [V]. This is a *probing tool*: synchronized requests from distributed clients locate server bottlenecks. It is not a study of flash-crowd behaviour or of mitigation architectures, so the plan should not present it as flash-crowd mitigation work. It notes that most servers rely on over-provisioning, admission control or CDNs to survive flash crowds. — [USENIX](https://usenix.org/conference/2008-usenix-annual-technical-conference/remote-profiling-resource-constraints-web-servers); [PDF](https://pages.cs.wisc.edu/~pratap/papers/pratap_ramamurthy_mfc.pdf)
- Flash crowds in cloud settings (2015): "Handling flash-crowd events to improve the performance of web applications," ACM SAC 2015 [V for ACM DOI], and "Detecting and Handling Flash-Crowd Events on Cloud Environments" (arXiv 1510.03913) [U]. Both propose detecting a flash crowd and sizing cloud instances, compared against Amazon Auto Scaling, using synthetic and real traces. — [ACM DL](https://dl.acm.org/doi/10.1145/2695664.2695839); [arXiv 1410.2834](https://arxiv.org/pdf/1410.2834); [arXiv 1510.03913](https://arxiv.org/abs/1510.03913)
- An auto-scaling survey (c. 2019) states that flash crowds remain a challenge for reactive auto-scaling and cites VM start-up times of about 350–400 s. This supports the plan's premise that scaling after the surge starts is too slow for a result declaration at a known time. — [ResearchGate](https://www.researchgate.net/publication/332828653_Research_on_Auto-Scaling_of_Web_Applications_in_Cloud_Survey_Trends_and_Future_Directions)
- Slashdot effect: the only source found is the Wikipedia overview, and no peer-reviewed Slashdot measurement paper was located in this session. — [Wikipedia](https://en.wikipedia.org/wiki/Slashdot_effect)

### Inferences
- The plan's novelty case should rest on the domain (scheduled, read-only, key-addressed, nationally synchronized surge at a known instant, India-specific) and on running the mechanisms *in combination*. It should not rest on "the literature is old", because the overload and metastability literature is not old.
- A result declaration is a *scheduled* flash crowd, so it is closer to a ticket on-sale or a Singles' Day sale than to the unpredictable Slashdot or viral event that Jung et al. and Wendell & Freedman study. That framing difference is itself a defensible contribution.

### Gaps
- No peer-reviewed measurement study (2015–2026) of web flash crowds at IMC, SIGMETRICS or NSDI was found in this session's searches. Absence is not proof; a Scholar search on "flash crowd" with a 2015 or later filter is still needed.
- The EURECOM and FCAN items cited in the plan were not re-verified here. Another researcher's scope may cover them.
- Arlitt & Jin's 1998 World Cup workload characterization (IEEE Network, 2000) is a classic surge-workload trace [K]. It was not verified this session.

## Q2. Open vs closed workloads, coordinated omission. Is the open-loop method already established?

### Takeaway
Yes. Open-loop load generation is established methodology, not a contribution. Schroeder et al. (NSDI 2006) is mandatory to cite. Adding user retries makes the thesis workload a *partly-open* model, a term that paper itself introduced.

### Cited Findings
- Schroeder, Wierman & Harchol-Balter, "Open Versus Closed: A Cautionary Tale," NSDI 2006, pp. 239–252 [V]. Implementation and simulation experiments show a vast difference in behaviour between open and closed models. The authors distil eight guiding principles and propose a *partly open* model whose behaviour lies between the two. — [USENIX](https://www.usenix.org/conference/nsdi-06/open-versus-closed-cautionary-tale); [PDF](https://www.cs.utoronto.ca/~bianca/papers/nsdi_camera.pdf)
- Coordinated omission (Gil Tene): the canonical citable artefact is the wrk2 README, which explains how closed-loop generators under-report latency when the server stalls and how a constant-throughput generator corrects for it [K]. This is a practitioner source with no peer-reviewed paper. — [wrk2 on GitHub](https://github.com/giltene/wrk2)
- k6 documents open (arrival-rate executors) versus closed (VU-based) models explicitly [K]. — [Grafana k6 docs](https://grafana.com/docs/k6/latest/using-k6/scenarios/concepts/open-vs-closed/)

### Inferences
- The thesis should describe its workload as "open arrivals plus a retry feedback loop = partly-open" and cite Schroeder et al. This also places RQ4 (retry amplification) correctly: it is the closed-loop component layered on an open process.
- k6 arrival-rate executors drop iterations when VUs run out, so the plan should check for and report dropped iterations. Otherwise coordinated omission re-enters through the back door. This is an inference from how the tool works, not a sourced finding.

### Gaps
- No peer-reviewed paper on coordinated omission was found. Cite Tene's materials as grey literature.

## Q3. Retry storms and metastable failures (RQ4)

### Takeaway
RQ4 is **partly answered**. It is well established qualitatively that retries amplify load and can sustain metastable failures. Retries are the most common sustaining effect in the OSDI 2022 incident study. Quantitative modelling is now active (HotOS 2025; a 2025 formal-analysis preprint). What seems missing is measurement of *human* refresh-and-retry behaviour against a read-only portal, comparing architectures A–D. That narrower question is the defensible novelty.

### Cited Findings
- Bronson, Aghayev, Charapko & Zhu, "Metastable Failures in Distributed Systems," HotOS 2021 [K]. Defines metastable failure: a trigger pushes the system into a bad state that a *sustaining effect* (often retries) keeps going after the trigger is removed. — [HotOS 2021 PDF](https://sigops.org/s/conferences/hotos/2021/papers/hotos21-s11-bronson.pdf)
- Huang et al., "Metastable Failures in the Wild," OSDI 2022 [V]:
  - Analysed 22 metastable failures across 11 organizations.
  - At least 4 of 15 major AWS outages in the prior decade were metastable failures.
  - The talk slides report that retry-driven load increase is the most common sustaining effect (more than 50% of cases).
  - About 35% of triggers were load spikes.
  - The authors reproduced metastable failures in controlled example applications.
  - The slide-level percentages should be checked against the paper text before citing.
  - [USENIX](https://www.usenix.org/conference/osdi22/presentation/huang-lexiang); [PDF](https://www.usenix.net/system/files/osdi22-huang-lexiang.pdf)
- Isaacs, Alvaro et al., "Analyzing Metastable Failures," HotOS 2025, pp. 172–178, DOI 10.1145/3713082.3730380 [V]. Combines queueing models, discrete-event simulation and service emulation to predict vulnerability to metastability. The running example is a retry storm. — [ACM DL](https://dl.acm.org/doi/10.1145/3713082.3730380); [PDF](https://sigops.org/s/conferences/hotos/2025/papers/hotos25-106.pdf)
- "Formal Analysis of Metastable Failures in Software Systems," arXiv 2510.03551 (Oct 2025) [U]. Formal model plus tool support; reports that recovery times grow sharply as parameters approach metastable regimes. — [arXiv](https://arxiv.org/abs/2510.03551)
- Stoica et al., "If At First You Don't Succeed, Try, Try, Again…? Insights and LLM-informed Tooling for Detecting Retry Bugs in Software Systems," SOSP 2024 [V via secondary pages]. An empirical study of retry bugs plus detection tooling. It covers retry *implementation* bugs and does not quantify load amplification. — [Chameleon blog summary](https://blog.chameleoncloud.org/posts/if-at-first-you-dont-succeed-try-try-again-insights-and-llm-informed-tooling-for-detecting-retry-bugs-in-software-systems/); [MSR podcast](https://microsoft.com/en-us/research/podcast/abstracts-november-4-2024)
- "Retry Amplification in Distributed Systems: A Systematic Analysis of Retry Policies and Their Role in Cascading Failures," arXiv 2608.25403 [U]. Search snippets say it defines a retry amplification factor metric. In its simulations, naive retries cut success rate from 55.4% to 41.5% compared with no retries under correlated failures. arXiv could not be fetched from this session, so authors, date and claims are unverified. — [arXiv PDF](https://arxiv.org/pdf/2608.25403)
- Practitioner sources [K]: they define retry budgets, capped exponential backoff and jitter, which are the standard mitigations the thesis should model.
  - Google SRE Book, "Addressing Cascading Failures": retry budgets per request and per client.
  - AWS Builders' Library, "Timeouts, retries, and backoff with jitter" (Marc Brooker).
  - AWS Architecture Blog, "Exponential Backoff and Jitter" (2015).
  - [SRE book](https://sre.google/sre-book/addressing-cascading-failures/); [AWS Builders' Library](https://aws.amazon.com/builders-library/timeouts-retries-and-backoff-with-jitter/); [AWS blog](https://aws.amazon.com/blogs/architecture/exponential-backoff-and-jitter/)
- Dean & Barroso, "The Tail at Scale," CACM 2013 [K]. The standard reference for hedged and tied requests, which are a deliberate form of request duplication that adds load. — [CACM](https://cacm.acm.org/research/the-tail-at-scale/)

### Inferences
- The thesis cannot claim to discover that retries amplify load. It can claim to (a) quantify the amplification factor for a *human* retry model (refresh after X seconds, abandonment probability) on a read-only lookup, and (b) show which architecture enters or escapes a metastable state. Point (b) fits Huang et al.'s "trigger + sustaining effect" framing exactly and should be stated that way.
- Testing whether load stays high *after* the arrival spike ends (the hysteresis test) is the experiment that would most clearly link RQ4 to the metastability literature.

### Gaps
- No study was found that measures real human retry and refresh behaviour during result or ticket surges. The thesis's retry parameters will need justification from logs (for example, from NIC) or must be stated as assumptions.

## Q4. Cache stampede, thundering herd, cold cache (RQ2)

### Takeaway
RQ2 is **partly answered**. The mechanisms are well studied:
- probabilistic early expiration (XFetch, VLDB 2015);
- leases and request coalescing (Facebook memcache, NSDI 2013);
- cold-cluster warmup (the same paper);
- cache-warmup measurement (FAST 2013, HotCloud 2020).

No paper was found that measures *pre-computed static results vs a cache-aside cache on cold start under a flash crowd*. The closest prior work is from 1998–2000: IBM's Olympics systems and WebView materialization. The plan should cite it, and it makes the precompute-vs-cache idea look older than the plan implies.

### Cited Findings
- Vattani, Chierichetti & Lowenstein, "Optimal Probabilistic Cache Stampede Prevention," PVLDB 8(8):886–897, 2015, DOI 10.14778/2757807.2757813 [V]. Proposes probabilistic early recomputation (XFetch) that is theoretically optimal and performs better than other real-world solutions. The plan currently cites it through a 2026 blog post, which should be replaced with the PVLDB citation. — [PVLDB listing](https://mail.vldb.org/pvldb/volumes/8/paper/Optimal%20Probabilistic%20Cache%20Stampede%20Prevention); [Sapienza repository](https://iris.uniroma1.it/handle/11573/877847)
- Nishtala et al., "Scaling Memcache at Facebook," NSDI 2013 [K]. Introduces *leases*, which stop the thundering herd by giving one client the right to refill a missed key while others wait or get stale data. It also describes "Cold Cluster Warmup", where a new cluster fills from a warm one. Both are direct prior art for design B "with request coalescing" and for the cold-cache condition. — [USENIX](https://www.usenix.org/conference/nsdi13/technical-sessions/presentation/nishtala)
- Zhang et al., "Warming up Storage-Level Caches with Bonfire," FAST 2013 [V]. A cold cache that fills on demand reached an 84% read hit rate by the end of the trace, against 96% for an always-warm cache. — [PDF](https://www.usenix.org/system/files/conference/fast13/fast13-final118_0.pdf)
- Zhang, Yang et al., "When is the Cache Warm? Manufacturing a Rule of Thumb," HotCloud 2020 [V]. Argues that "time to a fixed hit-rate threshold" is an inadequate definition of warmup and proposes a warmup-time model. This is useful for defining "warm" rigorously in the thesis. — [PDF](https://www.usenix.org/system/files/hotcloud20_paper_zhang-lei.pdf)
- Hot keys [K, all unverified this session]: for skewed and hot-key load balancing with a small front-end cache, the following are relevant.
  - Fan, Lim, Andersen & Kaminsky, "Small Cache, Big Effect," SoCC 2011.
  - NetCache, SOSP 2017.
  - SwitchKV, NSDI 2016.
  - The result portal's hot keys (topper lists, the result landing page) are a weaker form of the same problem, since roll-number lookups are mostly uniform.
- Precomputation and dynamic-content caching [K, all unverified this session; check before citing]:
  - Challenger, Iyengar & Dantzig, "A Scalable System for Consistently Caching Dynamic Web Data," IEEE INFOCOM 1999: the 1998 Nagano Olympics site.
  - Challenger et al., "A Publishing System for Efficiently Creating Dynamic Web Content," INFOCOM 2000.
  - Labrinidis & Roussopoulos, "WebView Materialization," SIGMOD 2000. It compares virtual views, views materialized in the DB, and views materialized at the web server (pre-generated pages) under load.
  - This is almost exactly the A vs B vs C comparison.

### Inferences
- An examiner familiar with databases would expect WebView materialization (Labrinidis & Roussopoulos) and the IBM Olympics papers. Their absence would weaken the claim that comparing precompute and cache is new. The novelty lies in modern tooling, cold start under an open-loop surge, and combination with retries and a waiting room. The core comparison is not new.
- Design C's advantage on cold start is close to true by construction (no miss path). The thesis should frame RQ2 as quantifying the *size* of the cold-start gap and how far coalescing, jitter or XFetch close it, not as asking whether a gap exists.

### Gaps
- No modern (2015–2026) peer-reviewed measured comparison of static or precomputed serving against cache-aside under a surge was found.
- The 1999–2000 IBM and WebView citations were not verified online this session.

## Q5. Admission control and waiting rooms (RQ3)

### Takeaway
RQ3 is **well answered for admission control in general**: admission control and load shedding preserve goodput under overload (SEDA 2001, Gatekeeper 2004, DAGOR 2018, Breakwater 2020, Rajomon 2025). It is **essentially unstudied for virtual waiting rooms specifically**. No peer-reviewed evaluation of Queue-it or Cloudflare-style waiting rooms, or of their fairness, was found; every search hit was vendor material. That makes design D's waiting-room evaluation the most defensible novel piece. The "beats raw capacity" framing should be made into a cost-for-same-SLO comparison.

### Cited Findings
- Welsh, Culler & Brewer, "SEDA: An Architecture for Well-Conditioned, Scalable Internet Services," SOSP 2001 [K]. Staged event-driven design with per-stage admission control for well-conditioned behaviour under overload. — [ACM DL](https://dl.acm.org/doi/10.1145/502034.502057)
- Elnikety, Nahum, Tracey & Zwaenepoel, "A Method for Transparent Admission Control and Request Scheduling in E-Commerce Web Sites," WWW 2004, pp. 276–286, DOI 10.1145/988672.988710 [V]. Gatekeeper is a proxy that needs no changes to the OS, web server, app server or DB. Tested on TPC-W in a three-tier setup, it gave stable performance under overload, up to about 10% more throughput and up to 14x better response time, with a 15% penalty for large jobs. It is the closest academic analogue of design D, a front proxy gating requests. — [WWW 2004 PDF](https://archives.iw3c2.org/www2004/proceedings/docs/1p276.pdf); [ACL/webis anthology](https://ir.webis.de/anthology/2004.wwwconf_conference-2004.28/)
- Zhou et al., "Overload Control for Scaling WeChat Microservices" (DAGOR), ACM SoCC 2018 [K]. Priority- and business-aware load shedding in WeChat's microservices, including behaviour during surges. — [ACM DL](https://dl.acm.org/doi/10.1145/3267809.3267823)
- Cho et al., "Breakwater: Overload Control for μs-scale RPCs," OSDI 2020 [K]. Server-driven, credit-based admission control. — [USENIX](https://www.usenix.org/conference/osdi20/presentation/cho)
- Xing et al., "Rajomon: Decentralized and Coordinated Overload Control for Latency-Sensitive Microservices," NSDI 2025 [V]. Market-based, token-priced load shedding. Reports 78% lower tail latency and 45% more goodput under high load than state-of-the-art microservice overload control. — [USENIX](https://www.usenix.org/conference/nsdi25/presentation/xing); [PDF](https://www.seas.upenn.edu/~leebcc/documents/xing25-nsdi.pdf)
- Google SRE Book, "Handling Overload" [K]. Client-side adaptive throttling and criticality-based shedding. — [SRE book](https://sre.google/sre-book/handling-overload/)
- Netflix, "Keeping Netflix Reliable Using Prioritized Load Shedding" (tech blog, 2020) [K]. — [Netflix TechBlog](https://netflixtechblog.com/keeping-netflix-reliable-using-prioritized-load-shedding-6cc827b02f94)
- Virtual waiting rooms: searches returned only vendor material.
  - Queue-Fair describes randomizing queue positions for users who arrive before the sale opens, which is a fairness mechanism.
  - Queue-it warns that FIFO queues can be gamed by fast bots.
  - A load-testing vendor reports that the release cadence slips under sustained pressure, producing uneven waves.
  - None is independent evidence.
  - Sources: [Queue-Fair](https://queue-fair.com/virtual-waiting-room); [Queue-it buyer's guide](https://queue-it.com/blog/how-to-choose-virtual-waiting-room/); [LoadView](https://www.loadview-testing.com/blog/virtual-waiting-room-load-testing/)
  - Cloudflare's 2021 Waiting Room launch blog describes the design (cookie-based, configurable admission rate) [K]. — [Cloudflare blog](https://blog.cloudflare.com/cloudflare-waiting-room/)

### Inferences
- Because admission control's goodput benefit is established, RQ3 phrased as "does admission control help?" is answered. A defensible RQ3 would instead ask, for a *read-only, cheap-per-request* workload (design C), whether a waiting room adds value beyond what plain static serving already gives, and at what cost in user-perceived wait and fairness. When per-request cost is close to zero, a waiting room may add latency without improving goodput. Only an experiment can say.
- Fairness of the waiting room (FIFO vs randomized position, and the effect of retries and refresh on queue position) is a measurable gap with almost no academic coverage.

### Gaps
- Using the plain web search tool, I could not confirm whether any IEEE or ACM paper evaluates commercial virtual waiting rooms. A direct search of IEEE Xplore and the ACM DL ("virtual waiting room", "online queue" + ticketing) is still needed before claiming novelty.

## Q6. Static site generation and precomputation vs dynamic serving under load

### Takeaway
No peer-reviewed, controlled load-test comparison of SSG/JAMstack against dynamic rendering was found. The material available is blog-level. The academic precursors are the 1999–2000 dynamic-content caching and materialization papers listed in Q4.

### Cited Findings
- Searches for SSG vs SSR load-test studies returned only blogs and vendor posts. One describes a WordPress vs Jamstack comparison by TTFB and stress test, but it is not a formal study. — [CSS-Tricks](https://css-tricks.com/static-vs-dynamic-vs-jamstack-wheres-the-line/); [Naturaily blog](https://naturaily.com/blog/static-vs-dynamic-website)

### Inferences
- Design C vs A/B is a legitimate empirical gap at the "modern measured comparison" level. It should still cite Labrinidis & Roussopoulos (2000) and Challenger et al. (1999/2000) as conceptual precedent (both [K]).

### Gaps
- No ACM/IEEE search on "static site generation benchmark" or "incremental static regeneration" was run directly.

## Q7. Benchmarking methodology and reproducibility

### Takeaway
Examiners will expect the thesis to follow established cloud-benchmarking principles. Papadopoulos et al. (TSE 2019) and Uta et al. (NSDI 2020) are both real and directly applicable (repetitions, reporting variability, cloud network noise). DeathStarBench and TPC-W/RUBiS are the standard multi-tier benchmarks. The thesis uses a custom app, so it should justify not using them.

### Cited Findings
- Papadopoulos, Versluis, Bauer, Herbst, von Kistowski, Ali-Eldin, Abad, Amaral, Tůma & Iosup, "Methodological Principles for Reproducible Performance Evaluation in Cloud Computing," IEEE TSE 2019, DOI 10.1109/TSE.2019.2927908 [V]. Eight methodological principles. A review of 2012–2017 publications found that few studies follow them. Originated in the SPEC RG Cloud group. — [VU research portal](https://research.vu.nl/en/publications/methodological-principles-for-reproducible-performance-evaluation/); [SPEC RG tech report](https://research.spec.org/fileadmin/user_upload/documents/rg_cloud/endorsed_publications/SPEC_RG_2019_Methodological_Principles_for_Reproducible_Performance_Evaluation_in_Cloud_Computing.pdf)
- Uta, Custura, Duplyakin, Jimenez, Rellermeyer, Maltzahn, Ricci & Iosup, "Is Big Data Performance Reproducible in Modern Cloud Networks?," NSDI 2020 [V]:
  - Finds that the systems community regularly ignores cloud variability.
  - Collected millions of datapoints from more than 9 PB of transfers.
  - Variability persists and is even worsened by providers' QoS mechanisms.
  - Gives guidelines for repeatable experiments.
  - [USENIX](https://www.usenix.org/conference/nsdi20/presentation/uta)
- Gan et al., "An Open-Source Benchmark Suite for Microservices and Their Hardware-Software Implications for Cloud & Edge Systems" (DeathStarBench), ASPLOS 2019 [K]. — [ACM DL](https://dl.acm.org/doi/10.1145/3297858.3304013)
- TPC-W, the e-commerce benchmark used by Gatekeeper (WWW 2004, above) [V via the Elnikety abstract]. RUBiS (Amza et al., 2002) [K, unverified].

### Inferences
- Because the thesis compares architectures by small differences in tail latency, it should adopt the Papadopoulos principles explicitly and report run-to-run variance (Uta et al.). Running on a shared college or cloud VM makes this essential.

### Gaps
- No paper was found that compares caching tiers (DB vs cache-aside vs precomputed) on TPC-W or RUBiS under *open-loop flash-crowd* load specifically.

## Q8. Ticketing and flash-sale systems (IRCTC Tatkal, Ticketmaster Eras, Singles' Day, 12306)

### Takeaway
There is no academic study comparing architectures for scheduled surges. What exists:
- a 2023 journal paper describing 12306's production architecture;
- a 2025 arXiv preprint on a microservice ticketing framework with no flash-sale benchmarks seen;
- grey literature from Ticketmaster and Alibaba.

No IRCTC Tatkal academic study was found. This supports the plan's domain-gap claim, as long as it is narrowed to "architecture comparison for scheduled surges".

### Cited Findings
- "Application and realization of key technologies in China railway e-ticketing system," *Railway Sciences* (Emerald), 2023, DOI 10.1108/RS-01-2023-0005 [V]. Tens of millions of daily passengers produce query demand beyond what ordinary relational databases support. The fixes are dedicated service clusters plus a data-synchronization mechanism that cuts direct queries to the backend host, which is conceptually design C (read replicas and precomputed query data). — [Emerald](https://www.emerald.com/insight/content/doi/10.1108/rs-01-2023-0005/full/html)
- A Science China Information Sciences (2019) stream-processing paper uses 12306 as a test case, citing 1.7 million page views per second [V for the existence of the paper only]. — [PDF](http://scis.scichina.com/en/2019/082101.pdf)
- "Securing High-Concurrency Ticket Sales: A Framework Based on Microservice," arXiv 2512.24941 [U]. Argues monoliths freeze and oversell under ticket-grabbing peaks, and proposes splitting ticket, payment and order services. No flash-sale benchmark results were seen. — [arXiv](https://arxiv.org/abs/2512.24941)
- Ticketmaster's Nov 2022 statement on the Taylor Swift Eras Tour on-sale (about 3.5 billion system requests, said to be 4x the previous peak) [K, figures unverified this session]. — [Ticketmaster Business](https://business.ticketmaster.com/press-release/taylor-swift-the-eras-tour-onsale-explained/)
- Alibaba Singles' Day: X-Engine (Huang et al., SIGMOD 2019) describes the transaction spike at midnight on Singles' Day as motivation [K, figures unverified]. — [ACM DL](https://dl.acm.org/doi/10.1145/3299869.3314041)

### Inferences
- Ticketing and flash sales are *write-heavy with contention* (inventory). Result lookup is *read-only*. So ticketing architectures (inventory locking, queue-then-purchase) only partly transfer, and the read-only nature is a real distinguishing feature. It also explains why design C (fully precomputed) is viable for results but not for ticketing.

### Gaps
- No academic paper on IRCTC Tatkal, CBSE/NIC result portals, or Indian government portal surges was found.
- Ticketmaster and Alibaba figures were not re-verified this session.

---

## Summary verdict per RQ (for the report writer)

| RQ | Verdict | Most important prior work | Defensible novelty |
|---|---|---|---|
| RQ1: architecture comparison | **Partly answered** in general (dynamic vs cached vs materialized, c. 1999–2004); not answered for modern stacks or result portals | Labrinidis & Roussopoulos SIGMOD 2000 [K]; Challenger/Iyengar INFOCOM 1999/2000 [K]; Elnikety WWW 2004 [V]; Nishtala NSDI 2013 [K] | Same-harness, open-loop, retry-aware comparison of A–D for a scheduled read-only surge |
| RQ2: precompute vs cache on cold start | **Partly answered**: mechanisms well studied, but no modern measured head-to-head comparison found | Vattani PVLDB 2015 [V]; Nishtala NSDI 2013 (leases, cold cluster warmup) [K]; Bonfire FAST 2013 [V]; HotCloud 2020 warmup [V] | Size of the cold-start gap under a surge, and how far coalescing, jitter or XFetch close it |
| RQ3: admission control / waiting room vs capacity | **Well answered** for admission control in general; **largely unstudied** for virtual waiting rooms (no peer-reviewed evaluation found) | SEDA SOSP 2001 [K]; Gatekeeper WWW 2004 [V]; DAGOR SoCC 2018 [K]; Breakwater OSDI 2020 [K]; Rajomon NSDI 2025 [V] | Waiting room on a near-zero-cost read path: cost for the same SLO, user wait, fairness under retries |
| RQ4: retry amplification | **Partly answered**: qualitatively established, quantitative models emerging | Bronson HotOS 2021 [K]; Huang OSDI 2022 [V]; Isaacs HotOS 2025 [V]; SRE book and AWS Builders' Library [K] | Measured amplification under a *human* retry model, per architecture, with a hysteresis (metastability) test |
| Method: open-loop load | **Established**, not a contribution | Schroeder NSDI 2006 [V]; Tene / wrk2 [K] | None; cite and follow it |

Missing literature an examiner would most likely flag:
1. Schroeder et al. NSDI 2006
2. Huang et al. OSDI 2022 and Bronson et al. HotOS 2021
3. Nishtala et al. NSDI 2013
4. Vattani et al. PVLDB 2015 (primary citation instead of the blog)
5. Elnikety et al. WWW 2004 and Welsh et al. SOSP 2001
6. Jung et al. WWW 2002
7. Papadopoulos et al. TSE 2019 and Uta et al. NSDI 2020
8. Labrinidis & Roussopoulos SIGMOD 2000
9. Google SRE book chapters on overload and cascading failures
10. Recent overload control: DAGOR SoCC 2018, Breakwater OSDI 2020, Rajomon NSDI 2025
