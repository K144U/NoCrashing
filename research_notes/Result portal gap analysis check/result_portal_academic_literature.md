# Academic literature on performance, scalability and load testing of result, admission/enrollment and e-governance portals (novelty check for the AKTU M.Tech result-portal thesis)

> **Access caveat (read first).** In this session, WebFetch and direct HTTP could not reach academia.edu, researchgate.net, ijsr.net, arxiv.org, dl.acm.org, api.semanticscholar.org, api.openalex.org, j-ptiik.ub.ac.id or jurnal.polinema.ac.id. They failed DNS resolution or returned a proxy 403. **No full text was read for any paper below.** Every paper-level claim comes from search-engine snippets and abstract or metadata excerpts. This is marked as "abstract/snippet only" in the table. To confirm the details that matter most for the gap claim (correctness checks, cost, workload shape), the full PDFs of the two Indonesian Redis papers need to be opened. Search used many query variants (about 30 searches). The coverage of Google Scholar, IEEE Xplore, Shodhganga and ProQuest is therefore indirect, through a general web search engine.

## Q1. Are there papers on exam/board/university result-website scalability, crashes or load testing (India, Nigeria, Bangladesh, Pakistan, Philippines, Kenya, etc.)?

### Takeaway
No peer-reviewed paper was found that load-tests, or compares architectures for, a national or board **result-publication** portal (CBSE, state boards, AKTU, Anna University, VTU, NIC results, JAMB, WAEC, KNEC, Bangladesh or Pakistan boards). The academic material that exists has three forms: (a) single-system JMeter load tests of college, admission or academic websites, mostly in Indonesian or low-tier Indian journals; (b) user surveys that report congestion when results come out (Malawi); (c) SMS result-checking designs. Result-day crashes are documented almost only in news, vendor blogs and student project write-ups.

### Cited Findings
**Single-system load tests of university, admission or academic websites (one design each, no architecture comparison):**
- Putri, M. A., Hadi, H. N., Ramdani, F. (Universitas Brawijaya). "Performance testing analysis on web application: Study case student admission web system." 2017 Int. Conf. on Sustainable Information Engineering and Technology (SIET), IEEE. It uses Apache JMeter to measure response time, throughput, capacity and scalability of the student-admission websites of Universitas Brawijaya and Politeknik Negeri Malang. Its introduction cites an earlier JMeter study of a "Pre Examination Process Automation System" (PEPAS, a Java system). *Abstract/metadata only. No numeric results seen.* — [IEEE Xplore 8304099](https://ieeexplore.ieee.org/document/8304099/); [Semantic Scholar](https://www.semanticscholar.org/paper/Performance-testing-analysis-on-web-application:-Putri-Hadi/3e2fe26d6c9653cef90931f3117911f7bdcaeb8c)
- Dave, D. M., Bhanushali, A. "Performance Testing: Methodology for Determining Scalability of Web Systems." IJSR 13(1), Jan 2024, pp. 1254–1261. It uses https://mu.ac.in/ (University of Mumbai) as the example system and reports how response time and scalability change as user load rises. It tests one design only. *Abstract only. Full text (ijsr.net) blocked.* This is very likely the "generic load-testing paper on college websites" that the thesis plan refers to. — [IJSR abstract](https://www.ijsr.net/getabstract.php?paperid=SR24121010827); [ResearchGate](https://www.researchgate.net/publication/377656524_Performance_Testing_Methodology_for_Determining_Scalability_of_Web_Systems)
- Raweyai & Widiasari. "Performance testing of academic website using load testing method supported by Apache JMeter at XYZ University." JUTIF (Jurnal Teknik Informatika, Unsoed), May 2024. Average GET response was about 0.855 s in the basic scenario and about 2.564 s under stress. In the "peak" scenario, GET and POST stayed under 3 s. Single system. *Snippet only.* — [JUTIF](https://jutif.if.unsoed.ac.id/index.php/jurnal/article/view/1796)
- "Performance Evaluation of Web Applications Using JMeter Load Testing for Server Capacity and Response Efficiency," JAIC (Politeknik Negeri Batam). The site was stable up to 200 concurrent users. Above 300 users, response times exceeded 60 s and errors appeared. The snippet does not say whether a university portal was tested. *Snippet only.* — [JAIC](https://jurnal.polibatam.ac.id/index.php/JAIC/article/view/11840)
- Shrestha, Koirala et al. "Load Capacity Testing of Moodle Server: Experimenting Quiz Application" (Univ. of North Dakota student work). A JMeter test of response time, throughput, CPU and RAM on an LMS, not a result portal. *Title/snippet only.* — [UND Scholarly Commons](https://commons.und.edu/ehb-stu/21/)

**Survey evidence of result-day congestion (no load testing):**
- Lubanga, S. "Web based student information management system in universities: experiences from Mzuzu University" (SCECSAL 2018) and the related SSRN report. Students named server load from concurrent use as a major problem, "especially during the time of online registration and accessing examination results." A secondary summary gives 83.7% reporting peak-time congestion, but this figure was **not verified** against the paper. — [SCECSAL PDF](https://www.scecsal.org/publications/papers2018/040_lubanga_2018.pdf); [SSRN](https://papers.ssrn.com/sol3/papers.cfm?abstract_id=3131810)
- A Nueva Ecija University of Science and Technology (Philippines) assessment of its online enrollment system, with 1,078 students, notes that "simultaneous system access by many users results in system slowdown." This is a survey (ISO-25010-style quality attributes), not a load test. *Title/snippet only.* — [ResearchGate 349670477](https://www.researchgate.net/publication/349670477_Students'_Assessment_of_the_Online_Enrollment_System_of_Nueva_Ecija_University_of_Science_and_Technology_An_Experienced_Based)

**SMS result-checking designs:**
- "An Improved SMS User Interface Result Checking System" (ResearchGate 238685874). The search summary links it to Orissa, India. *Title only. Author, year and venue not verified.* — [ResearchGate](https://www.researchgate.net/publication/238685874_An_Improved_SMS_User_Interface_Result_Checking_System)
- "Design and Implementation of a Secure and Scalable SMS-Based Academic Results Notification System" (ResearchGate 399358693, recent). It frames SMS as a way around web-portal congestion. No load figures appeared in the excerpt. *Title/snippet only.* — [ResearchGate](https://www.researchgate.net/publication/399358693_Design_and_Implementation_of_a_Secure_and_Scalable_SMS-Based_Academic_Results_Notification_System)

**Non-academic evidence only (news, blogs, projects). Useful for motivation, but these do not count as prior academic work:**
- CBSE: in 2020 "the CBSE website went down" after the Class XII results; NIC cited a technical issue, and results were also pushed through DigiLocker. — [Tribune India](https://www.tribuneindia.com/news/schools/cbse-website-crashes-after-declaration-of-results-112398)
- Board result days are described as among India's largest recurring online traffic events. — [BW Education](https://www.bweducation.com/article/board-results-season-triggers-india-s-biggest-traffic-surge-603894)
- WAEC withdrew its 2025 result checker over a correctness fault (a "paper serialization" security feature produced wrong results), not over load. This is a **real-world correctness failure** that supports the thesis's correctness-checking angle. — [ICIR Nigeria](https://www.icirnigeria.org/waec-shuts-down-results-portal-reviews-2025-wassce-results/); commentary on JAMB server overloads — [Guardian Nigeria](https://guardian.ng/features/education/jamb-waec-glitch-a-wake-up-call-for-exam-bodies-to-strengthen-digital-systems-afolabi/)
- QuickPU (Punjab University, Pakistan): a self-published developer write-up. FastAPI + MongoDB on EC2, about 850 concurrent users and 4,100+ API hits on result day, with parsed results cached in the DB. — [malahim.dev](https://www.malahim.dev/blogs/quickpu-punjab-university-result-portal)
- A GitHub DevOps project, "school-portal-reliability," simulates a university results portal. Its load testing is listed as not yet done. — [GitHub](https://github.com/BalogunFareed/school-portal-reliability)
- A vendor blog describes a university portal that collapsed at about 12,000 simultaneous logins after being tested at only 300, and recommends staggered release waves. — [examonline.in](https://examonline.in/exam-result-processing/)
- Bangladesh and Pakistan: only result-checker guide sites mention slowdowns and SMS-gateway congestion in the first hour. No research found. — [webresult.bd](https://webresult.bd/ssc-result-2026/)

### Inferences
- The result-publication workload has these properties: read-only, fixed key space (roll numbers), data immutable after publication, a scheduled spike at a known instant, and correctness-critical. It appears **unstudied as a controlled experimental object** in the peer-reviewed literature found. The nearest academic analogues are course-registration (KRS) and admission workloads in Indonesia.
- The thesis's statement that "generic load-testing papers on college websites test only a single design" holds for every Indian, Philippine, Jordanian and Indonesian JMeter paper found, **except** the two Indonesian Redis papers in Q2.

### Gaps
- No paper found for Kenya KCSE/KNEC, Bangladesh boards, Pakistan boards, CBSE/NIC, AKTU, Anna University or VTU result portals specifically. Searching IEEE Xplore, Scopus and Google Scholar directly with full-text access might surface low-visibility conference papers that a web search engine does not index.
- Numeric results of Putri et al. (2017) and Dave and Bhanushali (2024) could not be read (paywall or blocked host).

## Q2. Are there papers comparing architectures (caching, static generation, CDN, autoscaling, queueing/waiting room) for government, e-governance or education portals under peak load?

### Takeaway
Yes, partly, and these are the closest prior work found. **Two 2026 Indonesian papers compare a plain DB-backed design against Redis cache-aside for an academic information system (SIAKAD) under high concurrent load.** That is arms 1 and 2 of the thesis's four. Neither, as far as the abstracts show, tests pre-computed static or key-value serving, or a waiting room. Neither replays a real surge trace, checks the correctness of returned results, or measures cost. No peer-reviewed paper was found that compares any of these architectures for an Indian e-governance portal. No independent academic evaluation of virtual waiting rooms for public-sector sites was found; only vendor material.

### Cited Findings
**Closest work 1:** Putranto, M. A. S., Pinandito, A. (Universitas Brawijaya). "Analisis Kinerja Cache Redis pada RESTful API Berbasis Express.js." *Jurnal Pengembangan Teknologi Informasi dan Ilmu Komputer (J-PTIIK)* Vol 10 No 2 (Feb 2026); also listed in the Brawijaya repository.
- System: the SIAKAD class-schedule (jadwal kuliah) feature. Express.js with PostgreSQL (Supabase). The SQL arm runs a three-table JOIN (krs, jadwal_kuliah, mata_kuliah). The Redis arm uses **cache-aside**.
- Workload: Apache JMeter at 1,000, 5,000 and 10,000 concurrent users. This is synthetic concurrency, not a replayed trace.
- Results at 10,000 users: SQL averaged about 27.59 s with a 39.41% error rate. Redis averaged about 95.77 ms with 0.00% errors. A Mann-Whitney U test gave p < 0.05.
- Correctness of returned data and cost: **not mentioned in any snippet seen**. Error rate here means HTTP or request failures.
- *Abstract/snippet only (host blocked).* — [J-PTIIK article page](https://j-ptiik.ub.ac.id/index.php/j-ptiik/article/view/15978); [Brawijaya repository](https://repository.ub.ac.id/id/eprint/254925/)

**Closest work 2:** Tofan, Parlika, Krispriyanto. "Perancangan Arsitektur Cache-Aside Menggunakan Redis pada Sistem Informasi Akademik: Studi Prototipe dan Simulasi Beban." *Jurnal Informatika Polinema (JIP)* 12(3), 2026, pp. 493–502, DOI 10.33795/jip.v12i3.9675.
- System: the KRS (course-registration) module, motivated by "extreme traffic spikes at the start of semester."
- Design: a Flask prototype with Redis cache-aside. **DB latency (500 ms) and cache latency (5 ms) were simulated** using values from the literature; real MySQL and Redis were not used.
- Workload: Locust, 1,000 users, spawn rate 100 users/s.
- Results: average 507.52 ms without cache vs 9.12 ms with cache. p95 520 ms vs 13 ms. Throughput 385.71 vs 483.03 req/s. 0 failures in both.
- The authors state that validation on real infrastructure is still needed. No correctness or cost measurement was seen.
- *Abstract/snippet only (host blocked).* — [JIP article page](https://jurnal.polinema.ac.id/index.php/jip/article/view/9675)

**Other relevant work:**
- An arXiv paper, "Experimental Analysis of Server-Side Caching for Web Performance" (arXiv 2602.06074, 2026), from an Indian university department. It reports large response-time reductions from in-memory server-side caching on small-scale apps. Not a result portal. *Snippet only. Authors not verified (arxiv blocked).* — [arXiv 2602.06074](https://arxiv.org/pdf/2602.06074)
- Alnuhait, H., Alzyadat, W., Althunibat, A., Kahtan, H., Zaqaibeh, B., Al-Khawaja, H. A. "Web application performance assessment: A study of responsiveness, throughput, and scalability." *Int. J. of Advanced and Applied Sciences* 11(9), Sep 2024, pp. 214–226, DOI 10.21833/ijaas.2024.09.023.
  - Uses JMeter on an RSMD website and a (Jordanian) E-Government website. Both degraded over time. A 10 s ramp with 5 loops showed significant degradation.
  - Load test of e-government sites, but a single design each, with no architecture comparison.
  - *Abstract only.*
  - — [Science-Gate](https://www.science-gate.com/IJAAS/2024/V11I9/1021833ijaas202409023.html); [Cardiff Met record](https://pure.cardiffmet.ac.uk/en/publications/web-application-performance-assessment-a-study-of-responsiveness-/)
- Indian e-government website performance studies use passive tools (Pingdom, Websitepulse) to measure page size and download time across about 10 government sites. They do not do load testing. — [ResearchGate 274070835, "Analysis on Design Issues of E-Government Websites of India"](https://www.researchgate.net/publication/274070835_Analysis_on_Design_Issues_of_E-Government_Websites_of_India)
- A 2022 *Information Polity* survey of 631 users of Indian e-government portals includes "system stability" as an adoption factor. It is perception-based, not a measurement. — [SAGE, Singh et al. 2022](https://journals.sagepub.com/doi/10.3233/IP-220001)
- An arXiv study of 212 Bangladeshi websites found that government sites "often suffered from slow performance." It is an accessibility and usability audit, not a load test. — [arXiv 2601.00592](https://arxiv.org/pdf/2601.00592)

**Generic flash-crowd literature (architecture mitigation for scheduled or unscheduled surges, not education- or government-specific):**
- "Flash Crowds and Denial of Service Attacks: Characterization and Implications for CDNs and Web Sites." Usually attributed to Jung, Krishnamurthy and Rabinovich, WWW 2002; the attribution comes from background knowledge, and the PDF is hosted at MIT. It notes that both predictable and unpredictable flash events threaten sites. — [MIT PDF](http://nms.lcs.mit.edu/papers/flash-crowds02.pdf)
- Ari, Hong, Miller et al. "Managing Flash Crowds on the Internet," MASCOTS 2003. It shows that caching gives "orders of magnitude savings" in client response time and server load during flash crowds. — [UCSC PDF](https://users.soe.ucsc.edu/~elm/Papers/mascots03flash.pdf)
- Chen and Heidemann. "Experimental Evaluation of an Adaptive Flash Crowd Protection System" (NEWS, ISI). Admission control detected a flash crowd within about 20 s and cut response packet drops from 25% to 2% by discarding about 32% of requests. This is the academic analogue of a waiting room. — [ISI PDF](https://ant.isi.edu/~johnh/PAPERS/Chen03b.pdf)
- Chandra and Shenoy. "Effectiveness of Dynamic Resource Allocation for Handling Internet Flash Crowds" (autoscaling analogue). — [UMN PDF](https://www-users.cse.umn.edu/~chandra/papers/flash-crowds/paper.pdf)
- Wendell and Freedman. "Going Viral: Flash Crowds in an Open CDN," IMC 2011. — [Princeton PDF](https://www.cs.princeton.edu/~mfreed/docs/flash-imc11.pdf)

**Waiting rooms:**
- Only vendor or government-procurement pages were found: Queue-it, Queue-Fair, and RoomQ on the Hong Kong Smart Government Innovation Lab. Their claims (e.g., "tripling traffic capacity for HMPO", "queued 450,000 people in an afternoon") are unverified vendor statements. No peer-reviewed evaluation was found. — [Carahsoft/Queue-it](https://www.carahsoft.com/tech-spotlight-series/queue-it-managing-traffic-surges-for-gov-websites-tech-spotlight-2024); [Queue-Fair](https://queue-fair.com/public-sector); [HK Smart Lab RoomQ](https://www.smartlab.gov.hk/en/it-solutions/s-0279)

### Inferences
- The thesis's gap statement, "no controlled, reproducible comparison of [the four architectures] … under a replayed result-day surge, with correctness checked and cost measured," **survives as a conjunction**.
- Its weaker components are **already partly covered**:
  - "DB-backed vs cache-aside Redis for an academic portal under high concurrent load" has been done twice in 2026, in Indonesian venues, for schedule and KRS workloads.
  - The thesis must cite both and must not imply that no academic-portal architecture comparison exists.
- The parts that appear novel:
  - (i) pre-computed key-value or static-file serving as an arm;
  - (ii) a waiting room as an arm;
  - (iii) a **replayed** result-day surge shape, instead of fixed-concurrency JMeter or Locust runs;
  - (iv) **end-to-end correctness checking** (right result for the right roll number, no stale or mixed data). The WAEC 2025 incident shows correctness failures happen in practice;
  - (v) **cost measurement**;
  - (vi) the **result-publication** workload itself: read-only, immutable, scheduled spike.
- Tofan et al. simulated their DB and cache latencies. A thesis using real infrastructure with reproducible scripts would be methodologically stronger, and this is a legitimate contrast to draw.

### Gaps
- The full texts of the two Indonesian papers were not readable. It is not confirmed whether they report cost, check payload correctness, or include any additional arm such as static files. They need to be opened before the gap statement is finalised.
- No search was possible inside IEEE Xplore, ACM DL or Scopus full-text indexes. Studies of e-governance portals comparing CDN, autoscaling and caching that appear only there (e.g., ICEGOV proceedings) may have been missed. No ICEGOV paper on portal load or architecture surfaced in web search.

## Q3. What exactly does the Baroro enrollment-portal work do?

### Takeaway
**Not found.** Many queries combined the name (Jason S. Baroro, J. S. Baroro) with enrollment, portal, load testing, scalability and Philippines, and returned no paper by this author. The academia.edu profile the thesis cites could not be fetched because the host was blocked in this session. Its title, venue, year and methods could not be verified.

### Cited Findings
- Name searches returned only unrelated Facebook profiles (e.g., a "Josh Baroro" listing Our Lady of Fatima University). There was no scholarly record. — [search result: Facebook](https://www.facebook.com/josh.baroro.7/)
- Candidate (unverified) Philippine enrollment-system paper: "Evaluation and Improvement of the Higher Education Institution's Enrollment Information System," ACM, DOI 10.1145/3698062.3698084 (ICIET-type proceedings, c. 2024). The search snippet says it "proposes an enrollment portal for a Philippine higher education institution." Its authors could not be seen, and it **cannot be confirmed as Baroro's**. — [ACM DL](https://dl.acm.org/doi/fullHtml/10.1145/3698062.3698084)
- The other Philippine enrollment-system papers found are usability or ISO-25010 acceptance surveys, not load or architecture experiments:
  - Rafael L. Lazatin Memorial SHS online enrollment, ISO 25010, 222 respondents. — [cca.edu.ph](https://cca.edu.ph/assets/images/2-online-enrollment.pdf)
  - Central Philippines State University paperless enrollment, IJCSMC July 2022. — [IJCSMC](https://ijcsmc.com/docs/papers/July2022/V11I7202212.pdf)
  - DepEd "Web-based enrollment system: an evaluation." — [e-saliksik](https://e-saliksik.deped.gov.ph/web-based-enrollment-system-an-evaluation/?download=6295)
  - CSUQ usability study of a university portal. — [Philippine EJournals](https://ejournals.ph/article.php?id=21652)
- An anecdotal student blog says the University of Southeastern Philippines' Online Enrollment System "was overwhelmed" at rollout. — [Medium](https://medium.com/@pelhempeso01344/oes-so-convenient-85f5b767938c)

### Inferences
- If Baroro's work resembles the rest of the Philippine enrollment-portal literature found, it is likely a survey, usability or performance study of existing portals rather than a controlled multi-architecture experiment. **This is a guess and must not be cited as fact.**
- The thesis plan's description of it as "the closest recent work" should be re-checked once the paper is retrieved. The Indonesian Redis papers (Q2) are demonstrably closer in method (architecture comparison under load).

### Gaps
- The actual Baroro paper (title, venue, year, methods) is unknown. **Action:** open https://independent.academia.edu/JasonSBaroro in a normal browser and record the exact paper. Also check whether it is the ACM paper above.

## Q4. Are there M.Tech/PhD theses (Shodhganga, ProQuest, university repositories) on result-portal performance?

### Takeaway
None found. Searches for Shodhganga theses on examination-result portal performance or scalability returned only material about Shodhganga itself. No ProQuest or university-repository thesis on result-portal load was surfaced. The nearest thesis-type items are an Indonesian undergraduate thesis behind the J-PTIIK Redis paper and a Swedish master's thesis on Kubernetes autoscaling (not education-specific).

### Cited Findings
- The Shodhganga searches surfaced no relevant thesis. Shodhganga runs on DSpace and holds about 680–692k theses (2026). — [CASRAI guide](https://casrai.org/guides/shodhganga-inflibnet-india-thesis-repository)
- The Brawijaya repository lists the Putranto Redis vs SQL SIAKAD work as an institutional thesis or eprint. — [repository.ub.ac.id](https://repository.ub.ac.id/id/eprint/254925/)
- A KTH/DiVA master's thesis compares horizontal, vertical and hybrid pod autoscaling on GKE (p99 latency, resource use). It is generic, not about a portal. — [DiVA](https://www.diva-portal.org/smash/get/diva2:1783247/FULLTEXT01.pdf)

### Inferences
- Shodhganga's own search is weak and full-text indexing by web engines is limited. "Not found" here is weaker evidence than a direct Shodhganga or ProQuest keyword search would give.

### Gaps
- Direct searches of the Shodhganga UI and ProQuest Dissertations could not be run (no access). The thesis author should run "result portal", "examination result" + "load", "web server performance" + "university" there.

## Q5. Are there papers on DigiLocker, NIC results infrastructure, or national-scale result dissemination (SMS/IVRS/web) in India?

### Takeaway
No peer-reviewed paper on the **performance or architecture of NIC's results.nic.in hosting** or on result-day load in DigiLocker was found. DigiLocker is covered by policy and case-study write-ups and by blockchain re-design papers, not by load or performance evaluations. SMS result dissemination in India has only informal coverage (a 2004 Slashdot thread) plus a couple of SMS system-design papers.

### Cited Findings
- UCL Bartlett, "The DigiLocker Story" (2025) is a policy case study describing DigiLocker's evolution under NeGD into a "data-sharing infrastructure" with an API gateway. It is not a load study. — [UCL PDF](https://www.ucl.ac.uk/bartlett/sites/bartlett/files/2025-10/The%20DigiLocker%20Story.pdf)
- A 2016 trade article says NeGD scaled DigiLocker in phases with user and file targets, using open-source technology. — [Open Source For You](https://www.opensourceforu.com/2016/10/government-leverages-open-source-build-digilocker-indian-citizens/)
- Two papers re-design DigiLocker on blockchain; neither is a load evaluation:
  - "The Design and Development of Decentralized Digilocker using Blockchain" (ResearchGate 334077011). — [ResearchGate](https://www.researchgate.net/publication/334077011_The_Design_and_Developement_of_Decentralized_Digilocker_using_Blockchain)
  - A 2025 *Scientific Reports* paper notes that DigiLocker is scalable but has single points of failure. — [Nature Sci Rep](https://www.nature.com/articles/s41598-025-26326-0)
- A 2026 vendor blog says DigiLocker integrates CBSE, NTA, 30+ state boards and universities, with marksheets available "within hours" of declaration. This is not peer-reviewed. — [MAPLES OSM blog](https://maplesosm.com/blog/digilocker-examination-infrastructure-india-2026/)
- NIC's results gateway describes itself as a "single window" for board results. No published capacity or architecture details were found. — [results.nic.in](https://results.nic.in/); [NIC examination result services](https://examinationservices.nic.in/resultservices/)
- 2004 India SMS-flood discussion: BSNL handled about 100,000 SMS/hour, and commenters located the bottleneck in database lookups. This is informal. — [Slashdot](https://news.slashdot.org/story/04/05/24/0325233/secondary-exam-results-in-india-mean-an-sms-flood)

### Inferences
- National result dissemination in India (NIC + DigiLocker + SMS + mirrors) is an operationally important but academically undocumented system. That supports the thesis's motivation section. The thesis can cite news crash reports plus the absence of NIC or NeGD technical publications.

### Gaps
- No NIC or MeitY technical report on results hosting (CDN use, static pre-generation, mirroring) was found. These may exist only as internal documents or in NIC's "Informatics" magazine, which was not searched directly.

## Q6. Overall: master list of relevant papers and how close the closest work is

### Takeaway
**Closest work:** Putranto and Pinandito (J-PTIIK, 2026) and Tofan, Parlika and Krispriyanto (JIP, 2026). Both compare a plain DB design against Redis cache-aside for an Indonesian academic portal under synthetic high-concurrency load. That covers about 2 of the thesis's 4 arms. It does not cover pre-computed static/KV, a waiting room, a replayed surge, correctness checking or cost, as far as the abstracts show. **The novelty claim is confirmed only in narrowed form.** Rewrite it as an extension of these comparisons (four arms + trace replay + correctness oracle + cost), not as a claim that no architecture comparison of academic portals exists. The Baroro work could not be located or verified.

### Cited Findings (master table; "Access" = what was actually seen)

| # | Title (short) | Authors | Year | Venue | System studied | Workload | Multiple architectures compared? | Correctness measured? | Cost measured? | Access |
|---|---|---|---|---|---|---|---|---|---|---|
| 1 | Analisis Kinerja Cache Redis pada RESTful API Berbasis Express.js — [link](https://j-ptiik.ub.ac.id/index.php/j-ptiik/article/view/15978) | M. A. S. Putranto, A. Pinandito | 2026 | J-PTIIK 10(2) (Indonesia) | SIAKAD class-schedule API (Express + PostgreSQL) | JMeter, fixed concurrency 1k/5k/10k | **Yes: SQL vs Redis cache-aside (2 arms)** | Not mentioned (HTTP error rate only) | Not mentioned | Abstract/snippet only |
| 2 | Perancangan Arsitektur Cache-Aside Menggunakan Redis pada SIAKAD — [link](https://jurnal.polinema.ac.id/index.php/jip/article/view/9675) | Tofan, Parlika, Krispriyanto | 2026 | JIP 12(3):493–502 | KRS registration module prototype (Flask) | Locust 1k users, 100/s spawn; **simulated** DB/cache latency | **Yes: no-cache vs cache-aside (2 arms)** | Not mentioned | Not mentioned | Abstract/snippet only |
| 3 | Performance testing analysis on web application: student admission web system — [link](https://ieeexplore.ieee.org/document/8304099/) | M. A. Putri, H. N. Hadi, F. Ramdani | 2017 | IEEE SIET 2017 | Admission websites (Univ. Brawijaya, Polinema) | JMeter load | No | No (per abstract) | No | Abstract only |
| 4 | Performance Testing: Methodology for Determining Scalability of Web Systems — [link](https://www.ijsr.net/getabstract.php?paperid=SR24121010827) | D. M. Dave, A. Bhanushali | 2024 | IJSR 13(1):1254–61 | University of Mumbai website (mu.ac.in) | Increasing user load | No | No (per abstract) | No | Abstract only |
| 5 | Performance testing of academic website … JMeter at XYZ University — [link](https://jutif.if.unsoed.ac.id/index.php/jurnal/article/view/1796) | Raweyai, Widiasari | 2024 | JUTIF | University academic website | JMeter basic/stress/peak | No | No | No | Snippet only |
| 6 | Web application performance assessment: responsiveness, throughput, scalability — [link](https://www.science-gate.com/IJAAS/2024/V11I9/1021833ijaas202409023.html) | Alnuhait, Alzyadat, Althunibat, Kahtan, Zaqaibeh, Al-Khawaja | 2024 | IJAAS 11(9):214–226 | RSMD site + Jordanian e-government site | JMeter ramp/loops | No (two sites, not two designs) | No | No | Abstract only |
| 7 | Performance Evaluation of Web Applications Using JMeter … — [link](https://jurnal.polibatam.ac.id/index.php/JAIC/article/view/11840) | (not seen) | c. 2025 | JAIC (Polibatam) | A web application (unclear if university) | JMeter up to 300+ users | No | No | No | Snippet only |
| 8 | Experimental Analysis of Server-Side Caching for Web Performance — [link](https://arxiv.org/pdf/2602.06074) | (not verified; Indian univ. dept.) | 2026 | arXiv preprint | Small web apps | Cached vs uncached requests | Yes (cache vs no cache) | Not seen | Not seen | Snippet only |
| 9 | Web based SIMS in universities: Mzuzu University — [link](https://www.scecsal.org/publications/papers2018/040_lubanga_2018.pdf) | S. Lubanga | 2018 | SCECSAL | Mzuzu Univ. student portal (registration + results) | User survey (congestion at results time) | No | No | No | Snippet only |
| 10 | Students' Assessment of the Online Enrollment System of NEUST — [link](https://www.researchgate.net/publication/349670477_Students'_Assessment_of_the_Online_Enrollment_System_of_Nueva_Ecija_University_of_Science_and_Technology_An_Experienced_Based) | (not seen) | c. 2021 | (not seen) | Philippine univ. enrollment system | Survey, n=1,078 | No | No | No | Title/snippet only |
| 11 | Evaluation and Improvement of the HEI's Enrollment Information System — [link](https://dl.acm.org/doi/fullHtml/10.1145/3698062.3698084) | (not seen; possibly Baroro? unverified) | c. 2024 | ACM proceedings | Philippine HEI enrollment portal | Evaluation (method unknown) | Unknown | Unknown | Unknown | Title/snippet only |
| 12 | Baroro enrollment-portal study (cited by thesis plan) — [profile](https://independent.academia.edu/JasonSBaroro) | J. S. Baroro | ? | ? | Philippine university enrollment portals | ? | ? | ? | ? | **Not found / not accessible** |
| 13 | Analysis on Design Issues of E-Government Websites of India — [link](https://www.researchgate.net/publication/274070835_Analysis_on_Design_Issues_of_E-Government_Websites_of_India) | (not seen) | c. 2015 | (not seen) | ~10 Indian govt sites | Passive tools (Pingdom), page size/download time | No | No | No | Snippet only |
| 14 | An Improved SMS User Interface Result Checking System — [link](https://www.researchgate.net/publication/238685874_An_Improved_SMS_User_Interface_Result_Checking_System) | (not seen) | (not seen) | (not seen) | SMS result checking (India/Orissa per summary) | Design paper | No | No | No | Title only |
| 15 | Secure and Scalable SMS-Based Academic Results Notification System — [link](https://www.researchgate.net/publication/399358693_Design_and_Implementation_of_a_Secure_and_Scalable_SMS-Based_Academic_Results_Notification_System) | (not seen) | c. 2025–26 | (not seen) | SMS results notification | Design paper | No | No | No | Title/snippet only |
| 16 | Flash Crowds and DoS Attacks: Characterization and Implications — [link](http://nms.lcs.mit.edu/papers/flash-crowds02.pdf) | Jung, Krishnamurthy, Rabinovich (attribution from background knowledge) | 2002 | WWW 2002 | Real flash-crowd traces; CDN implications | Trace analysis | Partly (CDN implications) | No | No | Snippet only |
| 17 | Managing Flash Crowds on the Internet — [link](https://users.soe.ucsc.edu/~elm/Papers/mascots03flash.pdf) | Ari, Hong, Miller et al. | 2003 | MASCOTS | Generic web | Simulated flash crowds | Yes (caching schemes) | No | No | Snippet only |
| 18 | Experimental Evaluation of an Adaptive Flash Crowd Protection System — [link](https://ant.isi.edu/~johnh/PAPERS/Chen03b.pdf) | Chen, Heidemann | c. 2003–05 | ISI tech report / ToN | Generic web (admission control) | Testbed flash crowds | Admission control vs none | No | No | Snippet only |
| 19 | Effectiveness of Dynamic Resource Allocation for Handling Internet Flash Crowds — [link](https://www-users.cse.umn.edu/~chandra/papers/flash-crowds/paper.pdf) | Chandra, Shenoy | c. 2003 | (UMass/UMN tech report) | Generic hosting | Flash crowds | Yes (allocation policies) | No | No | Title only |
| 20 | Going Viral: Flash Crowds in an Open CDN — [link](https://www.cs.princeton.edu/~mfreed/docs/flash-imc11.pdf) | Wendell, Freedman | 2011 | IMC | CoralCDN | Real traces | CDN behaviour | No | No | Title only |

### Inferences
- **How close is the closest work?** Moderately close on method, far on scope.
  - Rows 1–2 share the core experimental idea: same portal logic, DB-only vs cache-aside, measured under high concurrency with an open-source load generator. They share the domain (university academic portals in a developing-country context).
  - They differ on:
    - workload type: course schedule or registration (read-mostly but mutable) vs immutable result lookup;
    - arm count: 2 vs 4, with no static/KV pre-compute and no waiting room;
    - load model: fixed concurrency vs replayed surge;
    - correctness: none vs an oracle check;
    - cost: none vs measured;
    - realism: row 2 simulates latencies.
  - On a 0–10 overlap scale with the proposed study, rows 1–2 are about **3–4/10**. Every other paper found is about **1/10** (single-design load tests or surveys).
- **Recommended rewording of the gap:** "Prior academic-portal studies compare at most a DB-backed and a cache-aside design under fixed synthetic concurrency (e.g., Putranto & Pinandito 2026; Tofan et al. 2026) and do not evaluate pre-computed static or key-value serving or admission control (waiting rooms). They do not replay a result-day surge, verify correctness of returned results, or measure cost."
- The thesis's description of "generic load-testing papers on college websites" testing only a single design is accurate for rows 3–7.

### Gaps
- Full-text verification of rows 1–2 (the decisive papers) and identification of the Baroro paper (row 12) remain open. Both need hosts that were blocked here: academia.edu, j-ptiik.ub.ac.id and jurnal.polinema.ac.id.
- Authors, venues and years marked "(not seen)" could not be confirmed and should not be cited without checking.
- Low-visibility Indian conference papers (IEEE India-section conferences, IJCA, IRJET) on specific result portals may exist without being indexed. Direct Google Scholar queries such as `"result portal" load` and `"examination result" website "JMeter"` are recommended as a final check.
