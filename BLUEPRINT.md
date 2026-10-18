# Recontact: build blueprint

The single source of truth for building **Recontact** for **Graph Hacks: Context for AI Agents** (WeMakeDevs x FalkorDB).
Submissions close **Sunday 18 Oct 2026, 11:59 PM IST**. Implementation: Cursor. Product owner and reviewer: Claude (this spec's author) with the team. Recontact is the backup project to ModelBrain; it reuses ModelBrain's conventions, hosting decision and verified FalkorDB facts.

## 0. Read me first (document map)
| File | What it is | Authority |
|---|---|---|
| `AGENTS.md` | the rules every coding agent follows | binding |
| `BLUEPRINT.md` (this file) | product, architecture, data model, logic, plan | binding |
| `docs/GOALS.md` | 147 numbered goals with Accept and Verify: the work list Cursor executes in order | binding; the definition of done |
| `docs/FLOWS.md` | every runtime and build-time flow step by step (F0-F20), with failure handling | binding |
| `docs/API.md` | endpoint, type, error and MCP tool contract | binding |
| `docs/UI.md` | every page, state and line of copy, and the wording rules | binding |
| `docs/queries.cypher` | every Cypher query (81 blocks), each executed on FalkorDB | binding |
| `docs/REQUIREMENTS.md` | every hackathon rule (H1-H20) and judging signal (S1-S27) mapped to goals | binding |
| `docs/TASKS.md` | the hour-by-hour board (summary of GOALS by block) | guidance |
| `docs/OPEN_POINTS.md` | what was verified, what is deferred, and why | guidance |
| `docs/EXPLAINER.md` | the 2-minute talk track every team member must be able to give | guidance |
| `data/*` | genes, normalisation, releases, demo tenants, generator parameters, templates, playbooks, eval skeleton | binding |

If two files disagree, the order of precedence is: AGENTS.md, GOALS.md, API.md, FLOWS.md, BLUEPRINT.md, UI.md, queries.cypher, the rest. Record the conflict in `docs/TASKS.md` under "Questions for the owner" and continue with the next goal you can do.

Name spaces (no clashes): goals `G001`-`G147`; flows `F0`-`F20`; queries `SCHEMA_*`, `K*` (kb), `X*` (exposure), `C*` (consent), `W*` (owner), `D*` (decisions), `L*` (ledger, tasks, handoffs), `T*` (tenant views), `A*` (algorithms), `P*` (seeding); requirement rows `H1`-`H20`, `S1`-`S27`. Code must use these names verbatim.

## 0.1 FalkorDB is the heart (prime constraint)
The sponsor is FalkorDB. The FAQ and rule 2 require it to be the primary graph database supporting a central part of the product; rule 3 disqualifies a graph that is decoration. In Recontact:
- **Every answer is a FalkorDB query.** The monthly ClinVar diff is computed in FalkorDB (K5 creates `ClassChange` nodes while loading a release). Who is at risk (X2), which channel is permitted (C1), who owns the duty today (W1, W2, W3), which decisions reopen (D1), which submissions differ from an expert panel (K11) and whether a later archive closed the loop (K12) are Cypher traversals. The Python duty engine only applies a fixed decision table to rows FalkorDB returns (like ModelBrain's clause evaluator); it never walks a pedigree, a succession chain or a release history itself.
- **Every memory write is a FalkorDB write**: releases, SCV versions, class changes, runs, duties, tasks, events, notices, consents, tests, handoffs, reconsideration items, conversation turns, live-lookup records. There is no other database. Caches may hold raw HTTP responses (NCBI) only, never graph answers.
- **We use the sponsor's headline features on screen**: multi-graph tenancy (`kb` + one graph per organisation + per-visitor sandboxes via `GRAPH.COPY` on one instance), Cypher with bounded variable-length paths and list predicates, `algo.WCC` (families and multi-carrier merge), `algo.BFS` (cascade view), MCP, and FalkorDB Browser (README walkthrough).
- **Proof**: goal G054 stops FalkorDB and shows the duty-map and variant endpoints return 503 instead of an answer.

---

## 1. What we are building, in one paragraph

When a clinical lab's classification of a variant changes in ClinVar, the lab already knows which of its reports cite that variant. What nobody answers end to end is the rest: **"This classification just changed: exactly who must be told, by whom, are we allowed to tell them, and which decisions made on the old answer must reopen?"** Recontact loads the real monthly ClinVar per-submission archives into FalkorDB and diffs them in the graph, so every lab's class changes are visible release by release. For a lab tenant (a fictional lab whose classifications mirror a real public submitter) it walks from the changed variant to the reports that cite it, to the carriers, and up and down each family to untested relatives, cutting every side of the family behind a relative who tested negative. It decides, per person, whether any consented path permits contact (AND along a derivation, OR across derivations, so a consenting carrier cousin can make a relative reachable even when the proband refused), finds who holds the duty today across retirements and clinic closures (or proves nobody does), and reopens every decision that rested on the old class, including downgrades. Agents draft every notice and reopened decision; nothing leaves the system until a named genetic counsellor approves. Clinical agents call the same graph over MCP (`variant_status`, `duty_map`) before they quote a variant's class. Patients, families, consents, clinicians and organisations are synthetic and labelled fictional; the ClinVar layer is real.

### The three things a judge must see
1. **Real data opener (no synthetic people yet).** "Pick any lab": the submitter picker lists real ClinVar submitters ranked by class changes between the 2026-09 and 2026-10 archives; click one and see its submissions that changed class, with version, evaluation date and the change kind (upgrade to actionable, downgrade, VUS resolved). Verified examples from the live archives: Women's Health and Genetics/LabCorp's SCV001983711 for PCSK9 (VCV 2877) moved from Uncertain significance (v2) to Benign (v3, evaluated 2026-06-15); Blueprint Genetics' SCV000206974 for HFE (VCV 11) moved from Pathogenic (v1) to Likely benign (v2, evaluated 2024-11-26, first visible in the 2026-10 archive).
2. **The duty map with the cousin path.** Click an upgrade that the fictional Demo Diagnostics Lab (mirroring that submitter) has reported: in about a second the synthetic pedigree lights up. Ana, the proband, refused family contact, but her cousin Vera, also a carrier, consented to direct contact, so Ana's sister Mila is reachable directly (green derivation through Vera; red derivation through Ana with the failed condition). Ana's son exercised the right not to know: **BLOCKED_NO_PERMITTED_PATH** with every failed condition listed. The maternal side is greyed: "no inheritance path: Rosa (mother) tested negative 2021". Ana's oncologist retired: the succession chain resolves to Dr Lindqvist; a carrier in another family is **ORPHAN** (clinic closed 2024, no successor) and goes to the medical director with the dead ends shown. Mila's 2022 discharge from screening rested on the VUS: **reopened**. Side by side, the lab baseline (amended reports to the ordering doctors on file) sends 3 letters, all 3 to clinicians who have left, and reaches 0 relatives.
3. **Memory and the loop.** Approve Mila's notice; re-run the same change: Mila is ALREADY_NOTIFIED. Replay a downgrade: the relative who was told in 2024 now gets a CORRECTION and two decisions reopen (downgrades are about 91% of VUS reclassifications in a 1.45-million-test cohort, Mersch et al., JAMA 2018). Then the reconsideration loop: a submission that differed from the expert-panel review in the 2026-08 archive is closed automatically when the 2026-09 or 2026-10 archive shows it updated. Finally Claude Code, acting as a clinical assistant, calls `variant_status` over MCP before quoting a class and is told which submissions changed and which differ from the expert panel.

### Tracks
- **Primary: Track 1, Agents That Act on Connected Data.** The headline answer is an agent action (who gets which notice, through whom, or a proof that no permitted path exists) decided by multi-hop graph proofs: variant -> report -> carrier -> kinship path with pruning (X2), AND/OR consent over derivations (C1), time-ordered succession chains with a no-path proof (W1, W2), reopen-on-change (D1). Graph algorithms are agent tools (`algo.WCC` multi-carrier merge, `algo.BFS` cascade view). External agents choose tools over MCP. Every result is explainable down to the path and the failed condition.
- **Also native: Track 2** (one FalkorDB graph per organisation and per sandbox; agents in different tenants hand off work only through `Handoff` nodes with leases; memory across releases suppresses re-notification and honours the right not to know; consent-aware memory: derived risk crosses a tenant boundary only along a permitted path) **and Track 3** (the health-system graph answers who owns each patient's follow-up today and which decisions still rest on a superseded ClinVar release, who approved them and what they cited; every decision is traced to the ClinVar release, SCV version and source URL).
- Why Track 1 is primary: the product's output is an action per person that only exists because of graph reachability and its absence. Tracks 2 and 3 are how it runs (tenants, handoffs, memory) and what it keeps current (owners, decisions), so they come for free from the core rather than as extra features.

### What Recontact is not (positioning)
- Not a lab amended-report pipeline: labs already list the reports citing a changed variant (we show that list as the baseline panel). Our value is only what the baseline cannot do: relatives, today's owner, a permitted channel, reopened decisions, scored on a frozen held-out eval.
- Not a family-history risk calculator. A FalkorDB entry created on 17 Oct 2026 (a family health tracker that follows synthetic family trees to compute Mendelian risk with an LLM agent) overlaps only on "pedigree in a graph". Differences: our trigger is a real ClinVar submission change diffed monthly in the graph; we compute duties and permitted channels, not probabilities; consent AND/OR over derivations, owner succession, reopened decisions, cross-tenant handoffs and memory across releases have no counterpart there. Per H15/G144, the public README states this generically ("unlike family-history risk calculators ...") and never names another entry.
- Not medical advice. Decision support for genetic counsellors; a human approves every notice.

---

## 2. Non-negotiables (rules, ethics, wording)

1. **FalkorDB is load-bearing.** Every duty, owner, reopened decision and class change comes from Cypher in `docs/queries.cypher`. If FalkorDB is removed, the product must not work. Never compute kinship, succession or release diffs in Python and only store the result.
2. **The model suggests, the graph decides.** Verdicts are deterministic code over graph rows. An LLM may only rephrase a notice draft from fixed slots (quote-checked) or route an "ask the org" question to a templated query. With no LLM key, templates are used and everything works.
3. **Human approval before any outward action.** A `Notice` node exists only after L5 (approval by a named counsellor in the health-system graph). The product never sends email, letters or messages; approved notices become delivery tasks for the owning clinician. Nothing is ever sent to ClinVar or to any real lab.
4. **Append-only history.** Runs, duties, notices, events, consents, tests, decisions and SCV versions are never edited in place. A changed answer is a new run; a replaced decision SUPERSEDES the old one; reopening is an Event. (Only workflow fields on Task and Handoff, and the release window marker `SCVVersion.superseded_in`, change.)
5. **Wording about real labs.** Never call a named submitter's classification "stale", "wrong", "incorrect", "outdated", an "error" or a "mistake". Say "the submitter updated its classification in the 2026-10 archive", "this submission's classification differs from the current expert-panel review", "submitted before the most recent expert-panel review". A reconsideration item is an internal task of the fictional lab tenant; we never contact a real lab.
6. **Medical framing.** "Decision support for genetic counsellors. Not medical advice." Drafts never diagnose, never recommend treatment, never name the source relative to another relative. Pedigree pruning and automatic relative routing apply only to autosomal dominant genes without a review flag; everything else returns NEEDS_REVIEW. Jurisdiction rules are an illustrative rule set, labelled as such.
7. **Data (rule 6).** ClinVar public data only (NCBI places no restrictions on use or distribution of its molecular data; verified 18 Oct 2026). All people, families, consents, tests, clinicians, clinics, decisions and organisations are synthetic, generated or hand-written, flagged `synthetic: true`, and labelled "(fictional)" in every UI. No personal data is stored. NCBI E-utilities calls carry only Variation IDs.
8. **README must include** (rule 10): setup instructions, the graph data model, the Cypher queries and algorithms the product depends on, the demo video link, the live URL, the tracks entered, and a disclosure that AI coding assistants were used (rule 11). Everyone on the team must be able to explain the graph model and queries (rule 12, `docs/EXPLAINER.md`).

---

## 3. Architecture

```
               Vercel (Next.js web app)                     Clinical / coding agents (Claude Code, Cursor)
                        |                                              |  MCP (streamable HTTP)
                        v                                              v
        +------------------------------------------ Railway (always-on) ------------------------------------+
        |  services/api  (Python 3.12, FastAPI)                                                               |
        |   - REST API (/api/*)              - MCP server (/mcp)                                              |
        |   - Agents (in-process workers): Watcher, Tracer, Steward, Drafter, Curator                         |
        |   - APScheduler: Watcher daily 06:00 UTC, handoff sweeper every 30 s, sandbox cleanup every 15 min  |
        |   - NCBI client: httpx, E-utilities limiter (3 rps; 10 rps with NCBI_API_KEY), FTP streaming        |
        +-----------------------------------------------------------------------------------------------------+
                        |  falkordb-py (Redis protocol, private network)
                        v
        FalkorDB (Docker image falkordb/falkordb on Railway, persistent volume, requirepass)
          graph "kb"            real ClinVar: genes, variants, submitters, SCVs, SCV versions, releases, class changes
          graph "lab_demo"      Demo Diagnostics Lab (fictional): synthetic families, reports, tests, consents, runs, duties
          graph "hs_demo"       Riverside Health (fictional): clinicians, clinics, succession, patients, decisions
          graphs "sbx_<8hex>_lab" + "sbx_<8hex>_hs"   per-visitor copies of the two demo tenants (GRAPH.COPY), 2 h TTL

        Build time (laptop, once): scripts/extract_clinvar.py streams the monthly archives from
        https://ftp.ncbi.nlm.nih.gov/pub/clinvar/tab_delimited/archive/ and writes compact extracts to data/clinvar/.
```

FalkorDB cannot query across graphs, so the app joins graphs in code and agents cross tenant boundaries only through `Handoff` nodes written into the target graph (section 7).

### Hosting decision (verified 17-18 Oct 2026, same as ModelBrain)
- **Web app on Vercel** (Hobby). Vercel serves only the Next.js frontend; it calls the API over HTTPS. Vercel cannot host FalkorDB and Hobby cron runs at most daily, so no backend work there.
- **API, agents and MCP on Railway**, one always-on replica (APScheduler jobs must run once). Avoid sleeping free tiers: judges may open the link days later.
- **FalkorDB on Railway in Docker** (`falkordb/falkordb:latest`, persistent volume at `/var/lib/falkordb/data`, `REDIS_ARGS="--appendonly yes --requirepass ${FALKORDB_PASSWORD}"`, `FALKORDB_ARGS="MAX_QUEUED_QUERIES 25 TIMEOUT 5000 RESULTSET_SIZE 10000"`, private networking only, memory limit 2 GB). Do **not** use the FalkorDB Cloud free tier for the judged deployment (100 MB, no backups, stops after 1 day idle, deleted after 7 days idle; the kb alone needs about 1 GB). FalkorDB Cloud Startup is the managed fallback.
- Expected cost for the judging window: about $10 to $25 on Railway (the kb is larger than ModelBrain's hub).
- `docker compose up` must work locally too (the rules accept a full local setup).

### Tech choices
| Layer | Choice | Why |
|---|---|---|
| Graph | FalkorDB 4.x via the `falkordb` Python client | the sponsor; multi-graph tenancy; Cypher; `algo.WCC`, `algo.BFS` |
| API | FastAPI, pydantic v2, httpx, APScheduler, slowapi | typed, async HTTP to NCBI |
| MCP | official `mcp` Python SDK **pinned `mcp>=1.10,<2`** (verified 1.30.0 for ModelBrain), `FastMCP("recontact", stateless_http=True)`, mounted with `app.mount("/", mcp.streamable_http_app())` **after all FastAPI routes**, FastAPI lifespan runs `async with mcp.session_manager.run():`; endpoint `/mcp` | Claude Code and Cursor connect over HTTP. mcp 2.x renamed FastMCP to MCPServer: do not upgrade during the event |
| LLM (optional) | OpenRouter (`OPENROUTER_API_KEY`, `LLM_MODEL`) for rephrasing drafts and the "ask the org" router only | template fallback when no key |
| Web | Next.js (App Router, TypeScript), Tailwind, `react-force-graph-2d` for pedigrees and chains | pedigree with lit and greyed nodes, coloured derivation edges |
| Tests | pytest against a FalkorDB service container; Playwright smoke | golden duty maps must not regress |

### Verified FalkorDB facts (18 Oct 2026, `falkordb/falkordb:latest`, graph module version 42201)
- Every block in `docs/queries.cypher` executes; 52 behavioural checks pass on a fixture (listed in the file header): zero-length segments `*0..3`, `n IN nodes(p)`, `nodes(p)[1..-1]`, CASE without ELSE inside list comprehensions, `OPTIONAL MATCH ... WHERE`, pattern predicates `NOT (n)-[:T]->()`, time-ordered paths via `all(i IN range(...))` over `relationships(p)`, `FOREACH` with a conditional list, idempotent re-run of K5, `algo.WCC` with a config map, `algo.BFS(node, depth, 'TYPE')` (outgoing edges only), `GRAPH.COPY` (fails if the destination exists).
- Container: data at `/var/lib/falkordb/data`; Redis options in `REDIS_ARGS`; module options in `FALKORDB_ARGS`, whose image default is `MAX_QUEUED_QUERIES 25 TIMEOUT 1000 RESULTSET_SIZE 10000` (re-confirmed with `GRAPH.CONFIG GET TIMEOUT` -> 1000). Set `TIMEOUT 5000`. The image starts without a password: always set `requirepass` and keep FalkorDB on private networking.
- Available procedures (re-confirmed): `algo.AStar`, `algo.betweenness`, `algo.BFS`, `algo.HarmonicCentrality`, `algo.labelPropagation`, `algo.maxFlow`, `algo.MSF`, `algo.pageRank`, `algo.SPpaths`, `algo.SSpaths`, `algo.WCC`. We use only WCC and BFS, where they do real work; adding PageRank or betweenness would be decoration.
- Load-scale test (synthetic rows through redis-cli, 500 rows per call): 40,000 variants (K2) in 10.8 s; 100,000 SCVs (K4) in 25.2 s; 100,000 base versions (K5) in 19.9 s; a 3,000-row delta in 0.8 s; K8 19 ms, K11 39 ms, K9 7 ms server time; Redis used memory 145 MB for about 245,000 nodes. Extrapolation for the in-scope genes (about 307,000 variants and 779,000 submissions): about 6-10 minutes to load and about 1-1.5 GB of memory. Through falkordb-py with 2,000-row batches it will be faster.

---

## 4. Data sources (ClinVar, all public)

All endpoints were exercised on 18 Oct 2026 unless marked "verify".

### 4.1 Files (NCBI FTP over HTTPS)
| File | Size (verified) | Use |
|---|---|---|
| `tab_delimited/variant_summary.txt.gz` | 455,785,525 bytes, modified 2026-10-12 | not used directly (weekly; not archived) |
| `tab_delimited/submission_summary.txt.gz` | 404,186,231 bytes, modified 2026-10-11 | not used directly (weekly) |
| `tab_delimited/archive/variant_summary_2026-10.txt.gz` | 450,727,547 bytes (2026-10-01) | Variant nodes: gene, name, aggregate class |
| `tab_delimited/archive/submission_summary_2026-08.txt.gz` | 385,522,058 bytes | kb BASE release |
| `tab_delimited/archive/submission_summary_2026-09.txt.gz` | 387,212,719 bytes | kb DELTA release |
| `tab_delimited/archive/submission_summary_2026-10.txt.gz` | 394,172,714 bytes | kb DELTA release |
| `tab_delimited/archive/2024/submission_summary_2024-10.txt.gz` | 272,294,228 bytes | eval transitions only |
| `tab_delimited/gene_specific_summary.txt` | 3,498,636 bytes | sizing (per-gene allele and submission counts) |
| `tab_delimited/organization_summary.txt` | 942,263 bytes, 3,576 lines | optional: submitter organisation ids and types |

Release cadence (ClinVar FTP README, verified): monthly releases usually on the first Thursday of the month, copied to `archive/`; weekly files usually on Mondays and **not archived**. We therefore load only monthly archives (replayable, citable). Monthly archives exist for every month of 2025 and 2026 at `archive/`, and for 2024 under `archive/2024/`. The 2026-11 archive is expected around Thursday 5 Nov 2026; the Watcher ingests it live during the judging window.

**`submission_summary` columns (verified 2026-08/09/10 archives; 16 columns, tab-separated, header line starts with `#VariationID`, preceded by `##` and `#Name:` description lines):** `VariationID, ClinicalSignificance, DateLastEvaluated, Description, SubmittedPhenotypeInfo, ReportedPhenotypeInfo, ReviewStatus, CollectionMethod, OriginCounts, Submitter, SCV, SubmittedGeneSymbol, ExplanationOfInterpretation, SomaticClinicalImpact, Oncogenicity, ContributesToAggregateClassification`. The 2024-10 archive has 15 columns (no `ContributesToAggregateClassification`): **always map columns by header name**. `SCV` holds `accession.version` (e.g. `SCV000206974.2`). `DateLastEvaluated` is `Mon DD, YYYY` or `-`. Rows are sorted by VariationID but not by SCV within a variant. `ClinicalSignificance` case varies (`pathogenic`, `Likely Pathogenic` appear in the VCV XML).

**`variant_summary` columns (verified; 43 columns):** `#AlleleID, Type, Name, GeneID, GeneSymbol, HGNC_ID, ClinicalSignificance, ClinSigSimple, LastEvaluated, RS# (dbSNP), nsv/esv (dbVar), RCVaccession, PhenotypeIDS, PhenotypeList, Origin, OriginSimple, Assembly, ChromosomeAccession, Chromosome, Start, Stop, ReferenceAllele, AlternateAllele, Cytogenetic, ReviewStatus, NumberSubmitters, Guidelines, TestedInGTR, OtherIDs, SubmitterCategories, VariationID, PositionVCF, ReferenceAlleleVCF, AlternateAlleleVCF, SomaticClinicalImpact, SomaticClinicalImpactLastEvaluated, ReviewStatusClinicalImpact, Oncogenicity, OncogenicityLastEvaluated, ReviewStatusOncogenicity, SCVsForAggregateGermlineClassification, SCVsForAggregateSomaticClinicalImpact, SCVsForAggregateOncogenicityClassification`. Each variant appears twice (GRCh37 and GRCh38): **keep `Assembly == GRCh38` only**. `GeneSymbol` may hold several symbols separated by `;`: keep a variant only if exactly one symbol is in scope, and assign it that gene.

**Real class changes (tiny live check, 18 Oct 2026):** the first 20,000 rows of the 2026-09 and 2026-10 archives (VariationID up to 3,609) share 19,195 SCVs; 224 changed version, **26 changed class**, 786 SCVs are new and 181 disappeared. Examples: SCV001983711 (Women's Health and Genetics/LabCorp, PCSK9, VCV 2877) Uncertain significance v2 -> Benign v3; SCV000206974 (Blueprint Genetics, HFE, VCV 11) Pathogenic v1 -> Likely benign v2 with evaluation date 2024-11-26 (the evaluation predates its first appearance in a monthly archive by 23 months, so the **release month, not the evaluation date, is the trigger**); SCV000581937 (GeneDx, VCV 449) Uncertain significance -> Likely pathogenic. Earlier research on a larger partial diff (about 1.2 million rows per month) found at least 761 SCV-level class changes from Sep to Oct 2026 (270 LP->P, 262 VUS->LB, 92 VUS->LP/P, 32 LP->VUS), from labs such as Blueprint Genetics (477), GeneDx (164) and LabCorp (25); treat those as research numbers, re-measured by G027.

**Scope (sizing verified from `gene_specific_summary.txt` dated 11 Oct 2026):** the 84 ACMG SF v3.3 genes hold 347,667 alleles and 876,513 submissions; TTN alone 40,949 alleles and 97,618 submissions. Default `KB_SCOPE=sf` loads the 83 genes with `kb_scope: true` in `data/genes.json` (all but TTN: about 306,700 alleles and 778,900 submissions). `KB_SCOPE=core` (22 genes) is the memory fallback; `KB_SCOPE=dev` (BRCA1, BRCA2, MYBPC3, PCSK9, HFE) is for tests and CI.

### 4.2 E-utilities (live lookups for a judge's own Variation ID)
| Need | Endpoint | Verified notes |
|---|---|---|
| Summary | `GET https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esummary.fcgi?db=clinvar&id={vcv}&retmode=json&tool=recontact&email={NCBI_EMAIL}` | `result[vcv]` has `accession` (`VCV000051579`), `accession_version` (`VCV000051579.32`), `title`, `germline_classification {description, last_evaluated, review_status, trait_set}`, `genes [{symbol, geneid}]`, `supporting_submissions {scv:[...], rcv:[...]}`, `record_status`. |
| Per-submission detail | `GET .../efetch.fcgi?db=clinvar&id={vcv}&rettype=vcv&is_variationid&tool=recontact&email=...` | **`is_variationid` is required**: without it the response is an empty `<ClinVarResult-Set><set/></ClinVarResult-Set>` (110 bytes); with it VCV 51579 returns 88,994 bytes. Path: `VariationArchive` (attributes `VariationID, VariationName, Accession, Version, DateLastUpdated, NumberOfSubmissions`) / `ClassifiedRecord` / `Classifications/GermlineClassification` (`ReviewStatus`, `Description`, attribute `DateLastEvaluated`) and `ClinicalAssertionList/ClinicalAssertion` (17 for VCV 51579), each with `ClinVarAccession` (attributes `Accession, Version, SubmitterName, OrgID`) and `Classification` (attribute `DateLastEvaluated`, children `ReviewStatus`, `GermlineClassification`). |
| Rate limits | response headers | Verified `x-ratelimit-limit: 3` without a key; 10 requests/second with `NCBI_API_KEY` (NCBI documentation). Always send `tool` and `email`. |
| Terms | NCBI policies page | "NCBI places no restrictions on the use or distribution of the data contained therein" (submitters may hold rights in parts; ClinVar classifications are facts we display with attribution). |

Example verified record: VCV 51579, NM_000059.4(BRCA2):c.3G>A (p.Met1Ile), aggregate Pathogenic, reviewed by expert panel (ENIGMA SCV001161657.3), 17 submissions, DateLastUpdated 2026-07-15; Ambry Genetics SCV000213380.9 evaluated 2025-12-15; Institute of Human Genetics, University of Leipzig SCV007614884.1 evaluated 2026-04-27; Mass General Brigham LMM SCV004848523.1 "Likely Pathogenic".

### 4.3 Normalisation (`data/normalisation.json`, applied before loading)
- Class (case-insensitive): pathogenic -> `P`; likely pathogenic, pathogenic/likely pathogenic -> `LP`; uncertain significance -> `VUS`; likely benign, benign/likely benign -> `LB`; benign -> `B`; conflicting classifications/interpretations of pathogenicity -> `CONFLICTING`; everything else (low penetrance, risk alleles, risk factor, drug response, association, protective, affects, other, not provided) -> `OTHER`. Actionable = `P`, `LP`.
- Stars from review status: practice guideline 4; reviewed by expert panel 3; criteria provided, multiple submitters, no conflicts 2; criteria provided, single submitter 1; criteria provided, conflicting classifications 1; no assertion criteria provided 0. Rows with `flagged submission` or `no classification provided` are skipped.
- Dates: `Mon DD, YYYY` -> `YYYY-MM-DD`; `-` -> null. Submitter id: lowercase, runs of characters outside `[a-z0-9]` -> `-`, trimmed, max 80 characters.

### 4.4 Gene list
`data/genes.json`: ACMG SF v3.3 (Lee et al., Genet Med 2025;27(8):101454): the 81 genes of v3.2 exactly as listed on the NCBI ClinVar ACMG page (cross-checked 18 Oct 2026) plus ABCD1, CYP27A1 and PLN. Each gene has `inheritance` (AD, AR, XL), `review_always` (true for non-AD genes and for SDHD, SDHAF2 (parent-of-origin effect), HFE (p.C282Y homozygotes only) and TTN (truncating only)), `category`, `condition`, `kb_scope`, `core`. 69 genes are AD without a review flag (automatic relative routing); 15 always go to review. A human verifies every inheritance mode against the published table (G024).

---

## 5. Graph model

### 5.1 Graph `kb` (shared, real public ClinVar; written only by the loader and the Watcher)
Nodes
| Label | Key properties |
|---|---|
| `Gene` | `symbol` (unique), `inheritance`, `review_always`, `review_reason`, `category`, `condition`, `sf_version` |
| `Variant` | `vcv` (int, ClinVar VariationID), `name` (HGVS title), `gene`, `agg_cls`, `agg_cls_raw`, `agg_review`, `agg_stars`, `agg_release` |
| `Submitter` | `id` (slug), `name` (exact ClinVar Submitter string) |
| `SCV` | `acc` (e.g. `SCV000206974`), `vcv`, `submitter_id` |
| `SCVVersion` | `id` = `<acc>.<version>|<cls>`, `acc`, `version`, `cls`, `cls_raw`, `dle` (submitter's DateLastEvaluated), `review`, `stars`, `first_release` (`YYYY-MM`), `superseded_in` (`YYYY-MM` or null = current), `withdrawn_in` |
| `Release` | `id` (`YYYY-MM`), `kind` (BASE, DELTA), `file`, `file_sha256`, `rows`, `loaded_at` |
| `ClassChange` | `id` = `<acc>@<release>`, `acc`, `vcv`, `submitter_id`, `release`, `from_cls`, `to_cls`, `from_version`, `to_version`, `to_dle`, `to_stars`, `kind` (UP_TO_ACTIONABLE, DOWN_FROM_ACTIONABLE, VUS_RESOLVED_BENIGN, BENIGN_TO_VUS, WITHIN_TIER, NEEDS_REVIEW_CLASS) |
| `LiveLookup` | `vcv`, `fetched_at`, `accession`, `name`, `gene`, `agg_cls`, `agg_review`, `submissions_json`, `date_last_updated` (record of a live E-utilities lookup outside the loaded scope) |

Relationships: `(Variant)-[:IN_GENE]->(Gene)`, `(SCV)-[:ABOUT]->(Variant)`, `(SCV)-[:SUBMITTED_BY]->(Submitter)`, `(SCV)-[:HAS_VERSION]->(SCVVersion)`, `(SCVVersion)-[:NEXT {release}]->(SCVVersion)`, `(ClassChange)-[:OF]->(SCV)`, `(ClassChange)-[:FROM]->(SCVVersion)`, `(ClassChange)-[:TO]->(SCVVersion)`.

"As of release R" means the SCVVersion with `first_release <= R` and (`superseded_in` is null or `> R`). The diff is computed in FalkorDB by K5: a release's rows are compared with each SCV's current version; a new version closes the old one and, if the normalised class differs, a `ClassChange` is created. Version bumps with the same class create no ClassChange.

### 5.2 Graph `lab_<slug>` (one lab tenant; `lab_demo` and sandbox copies)
Nodes
| Label | Key properties |
|---|---|
| `Org` | `id`, `name` ("Demo Diagnostics Lab (fictional)"), `kind: lab`, `mirrors_submitter` (real ClinVar Submitter name whose classifications the fictional lab mirrors), `synthetic: true` |
| `Person` | `pid`, `label` (name with "(fictional)"), `family`, `sex`, `birth_year`, `deceased`, `contact_pref` (ok, no_contact, not_to_know), `family_share` (none, letter, direct: the person's consent to their result being used to contact relatives), `recontact_ok` (consent to be recontacted about reclassification), `pos` (list of VCVs tested or reported positive), `neg` (list of VCVs tested negative), `synthetic: true` |
| `Report` | `id`, `issued`, `vcv`, `scv`, `scv_version`, `class_at_issue`, `ordering_clinician` (clinician id in the paired hs graph), `hs_tenant` |
| `VariantRef` | `vcv`, `gene` |
| `Test` | `id`, `vcv`, `result` (POS, NEG), `date` |
| `Consent` | `id`, `kind` (family_share, contact_pref, recontact), `value`, `at`, `recorded_by` (append-only history; the Person property is the current value) |
| `Jurisdiction` | `code`, `name`, `direct_allowed`, `note`, `illustrative: true` |
| `Run` | `id`, `change_id`, `vcv`, `release`, `kind`, `at`, `from_cls`, `to_cls`, `engine_version` |
| `Duty` | `id`, `pid`, `role` (CARRIER, RELATIVE), `notice_type`, `verdict`, `channel`, `source_pid`, `degree`, `owner_id`, `owner_status`, `failed` (list), `proof_json` |
| `Notice` | `id`, `pid`, `vcv`, `cls`, `notice_type`, `channel`, `release`, `approved_by`, `approved_at`, `body`, `seeded` |
| `Task` | `id`, `kind`, `state` (OPEN, CLAIMED, AWAITING_APPROVAL, DONE), `lease_until`, `claimed_by`, `created_at`, `created_by_agent`, `draft_title`, `draft_body`, `draft_source` (template, llm), `outcome`, `done_at` |
| `Event` | `id`, `kind` (APPROVED, REJECTED, ACKNOWLEDGED, RECON_CLOSED, ...), `at`, `by`, `by_name`, `reason`, `release`, `outcome` |
| `Handoff` | `id`, `kind`, `from_graph`, `pid`, `vcv`, `payload_json`, `state` (OPEN, CLAIMED, DONE, FAILED), `attempts`, `lease_until`, `claimed_by`, `created_at`, `done_at`, `result_json` |
| `Recon` | `id` = `<scv>@<release>`, `scv`, `vcv`, `gene`, `opened_cls`, `opened_version`, `panel_cls`, `panel`, `opened_release`, `opened_at` |
| `Playbook` | `kind`, `steps` (procedural memory) |
| `Conversation`, `Turn` | MCP and web history: `Turn {id, tool, args_json, summary, at}` |

Relationships: `(Person)-[:PARENT_OF]->(Person)`, `(Person)-[:HAS_REPORT]->(Report)-[:CITES]->(VariantRef)`, `(Person)-[:HAD_TEST]->(Test)`, `(Person)-[:GAVE]->(Consent)`, `(Person)-[:RESIDES_IN]->(Jurisdiction)`, `(Run)-[:PRODUCED]->(Duty)-[:FOR]->(Person)`, `(Duty)-[:BECAME]->(Notice)`, `(Person)-[:WAS_NOTIFIED]->(Notice)`, `(Task)-[:ABOUT]->(Duty|Recon)`, `(Task)-[:FOLLOWS]->(Playbook)`, `(Task)-[:HANDED_OFF_FROM]->(Task)`, `(Event)-[:ON]->(Task|Recon)`, `(Conversation)-[:HAS_TURN]->(Turn)-[:PRODUCED]->(Run)`.

### 5.3 Graph `hs_<slug>` (one health-system tenant; `hs_demo` and sandbox copies)
Nodes: `Org {id, name: "Riverside Health (fictional)", kind: health_system}`, `Clinician {id, name, role (oncologist, cardiologist, general practitioner, genetic_counsellor, medical_director), active, left_at, synthetic}`, `Clinic {id, name, open, closed_at, synthetic}`, `Patient {pid}` (the same pseudonymous pid as in the lab graph), `Team {id, name}`, `Role {name: medical_director}`, `Decision {id, pid, kind (SURVEILLANCE, SURGERY_RECOMMENDATION, DISCHARGE_FROM_SCREENING, CASCADE_NOT_OFFERED, TEST_INTERPRETATION), summary, made_at, synthetic}`, `VariantRef {vcv}`, `Source {url}`, `Event`, `Task`, `Handoff`, `Playbook`.

Relationships: `(Clinician)-[:PRACTICED_AT {at, until}]->(Clinic)`, `(Clinician)-[:HANDED_PANEL_TO {at}]->(Clinician)`, `(Clinic)-[:SUCCEEDED_BY {at}]->(Clinic)`, `(Clinic)-[:LED_BY {at, until}]->(Clinician)` (until null = current lead), `(Patient)-[:UNDER_CARE {from, until}]->(Clinician)`, `(Clinician)-[:MEMBER_OF]->(Team)`, `(Role)-[:HELD_BY]->(Clinician)`, `(Decision)-[:RESTED_ON {vcv, scv, cls_at_time, release}]->(VariantRef)`, `(Decision)-[:OWNED_BY]->(Clinician)`, `(Decision)-[:APPROVED_BY]->(Clinician)`, `(Decision)-[:CITES]->(Source)`, `(Decision)-[:SUPERSEDES]->(Decision)`, `(Event)-[:ON]->(Decision|Task)`.

### 5.4 Privacy and minimum-necessary rule across tenants
- The kb never stores tenant data. Lab and hs graphs never store real people.
- A lab agent never reads the hs graph and vice versa. Cross-tenant requests are `Handoff` nodes written into the target graph with the minimum payload: OWNER_LOOKUP `{pid, clinician_id}`, REOPEN_CHECK `{vcv, new_cls, change_id, release}`, NOTIFY_DIRECT `{pid, vcv, notice_type, notice_id}` (only after approval). No pedigree structure, no source relative identity and no BLOCKED person ever crosses (G064 scans the hs graph after a run).
- Consent-aware memory: a derived risk fact about a relative is written to another tenant only when some derivation permits direct contact; letter-only duties stay inside the lab graph (the letter goes to the consenting carrier through the carrier's owner).

---

## 6. Core logic (the duty engine; `services/api/app/engine/duty.py`)

The engine is a pure function `build_duty_map(change, carriers, derivations, prior_notices, owners, decisions, gene)` over rows from K17, X1, C1, L1, W1-W4 and D1. It applies the tables below and never queries the graph itself.

### 6.1 Change kinds (from K5, stored on ClassChange.kind)
| Kind | Rule (normalised classes) | Plan |
|---|---|---|
| UP_TO_ACTIONABLE | not P/LP -> P/LP | carriers: UPGRADE; relatives: NEW_RISK through C1; decisions: D1 |
| DOWN_FROM_ACTIONABLE | P/LP -> not P/LP | carriers: CORRECTION; previously notified relatives (L1): CORRECTION; others NO_ACTION; decisions: D1 |
| VUS_RESOLVED_BENIGN | VUS -> LB/B | carriers: VUS_RESOLVED; previously notified relatives: CORRECTION; others NO_ACTION; decisions: D1 |
| WITHIN_TIER | LP<->P or LB<->B | carriers: NO_ACTION with notice_type RECORD_UPDATE and an AMEND_REPORT task for the owner; relatives: none; decisions: D1 (returns none by construction) |
| BENIGN_TO_VUS, NEEDS_REVIEW_CLASS | LB/B -> VUS, or either class CONFLICTING/OTHER | carriers: NEEDS_REVIEW; relatives: not evaluated; no notice drafted; no decision reopened |

### 6.2 Carriers (X1 rows: everyone holding a report from this lab citing the variant)
First match wins:
1. Prior Notice for this person with `cls == to_cls` (L1) -> ALREADY_NOTIFIED.
2. Carrier deceased -> NEEDS_REVIEW, reason "carrier is deceased; the counsellor decides whether and how to inform next of kin".
3. `recontact_ok` false -> BLOCKED_NO_PERMITTED_PATH, failed `["carrier declined recontact about reclassification"]`.
4. Otherwise -> DIRECT_NOTICE with the plan's notice type (or NO_ACTION/RECORD_UPDATE for WITHIN_TIER, NEEDS_REVIEW for review kinds). Channel DIRECT (the owning clinician contacts their own patient).

### 6.3 Relatives for UP_TO_ACTIONABLE (C1 rows: every derivation source -> relative)
1. If the gene is not AD or `review_always` is true: every relative in C1 -> NEEDS_REVIEW, reason "automatic relative routing applies only to autosomal dominant genes without a review flag; <gene> is <inheritance> (<review_reason>)". One REVIEW_NEEDS_REVIEW task per duty.
2. Else, per relative, first match wins:
   1. Prior Notice with `cls` actionable for this vcv -> ALREADY_NOTIFIED.
   2. Any derivation with `direct_ok` -> DIRECT_NOTICE; chosen derivation = smallest `up+down`, tie by `source_pid` ascending.
   3. Any derivation with `letter_ok` -> VIA_FAMILY_LETTER; chosen derivation as above; the letter goes to that source carrier.
   4. Any derivation with `needs_review` (open but the source is deceased) -> NEEDS_REVIEW.
   5. No derivation is `open` -> NOT_AT_RISK_NO_INHERITANCE_PATH; proof = every derivation path with its `pruned_by` ("no inheritance path: Rosa (mother) tested negative 2021").
   6. Otherwise -> BLOCKED_NO_PERMITTED_PATH; `failed` = the union of `failed` from open derivations, each prefixed "via <source label>:" and de-duplicated.
3. **Degree** (shown and used for ordering only): for each source, take derivations of minimal `up+down`; lineal (`up == 0` or `down == 0`): degree = `up+down`; collateral: degree = `up+down-1` if two distinct common ancestors exist at that (source, up, down) (full relationship through a couple), else `up+down` (half relationship). Relative degree = minimum over sources. `nominal_prior = 0.5^degree`, labelled "nominal prior for an autosomal dominant variant, ignoring penetrance and de novo"; shown only for AD genes.

### 6.4 Relatives for DOWN_FROM_ACTIONABLE and VUS_RESOLVED_BENIGN
Previously notified people come from L1 (any Notice for this vcv with `cls` different from `to_cls`): channel = the earlier notice's channel if still permitted by the person's current preference (DIRECT needs `contact_pref == ok`; LETTER needs `contact_pref != not_to_know`) -> DIRECT_NOTICE or VIA_FAMILY_LETTER with notice_type CORRECTION; else NEEDS_REVIEW ("the earlier channel is no longer permitted; counsellor decides how to correct"). Deceased -> NEEDS_REVIEW. Everyone else in the family -> NO_ACTION (listed greyed: "never told; nothing to correct").

### 6.5 Owner (who holds the duty today; hs graph through the Steward)
For each carrier: W1 from `Report.ordering_clinician` -> owner with chain (status RESOLVED). No row -> W3 from the carrier's pid (status FALLBACK). No row -> status ORPHAN, `routed_to` = W4 medical director, `dead_ends` = W2 rows, plus an ORPHAN_DUTY task in the hs graph. A relative's owner = the owner of the chosen derivation's source carrier. A decision's owner = its OWNED_BY clinician if active, else W1 from that clinician, else ORPHAN as above. If the hs graph does not answer within 5 s, owners are `PENDING_HANDOFF` and the duty map still renders (G071).

### 6.6 Decisions (reopen on change)
D1 returns active decisions (not superseded) resting on the vcv whose `cls_at_time` is on the other side of the actionable line from `to_cls`, or that rested on a VUS that is now resolved either way. Each gets a REOPENED event (D2, idempotent on `evt_reopen_<decision>_<change>`) and a REOPENED_DECISION task for its owner. Approval of a replacement uses D3 (new decision RESTED_ON the new class, SUPERSEDES the old, APPROVED_BY the counsellor).

### 6.7 Multi-carrier families
A2 (`algo.WCC`) reports connected families with two or more carriers. The engine already ORs over all sources, so each relative appears once; the UI shows "two carriers in this family: duty map merged" and the derivation list shows both sources.

### 6.8 No-path proofs
- **No report cites the variant**: T4 does not contain the vcv -> the duty map is empty with the proof "No report in this organisation cites VCV <n>: no one to tell." (judge input path).
- **No inheritance path**: every derivation pruned (6.3.2.5).
- **No permitted path**: every open derivation failed a condition (6.3.2.6).
- **No owner**: W1 and W3 return nothing; W2 lists the dead ends.

### 6.9 Baseline (what an amended-report lookup does)
`baseline.letters` = one entry per carrier report: `{to: ordering clinician name, active: bool}`; `relatives_reached = 0`; `decisions_reopened = 0`. Shown next to the duty map.

### 6.10 Duty map response (also the MCP `duty_map` payload) - abridged; full type in `docs/API.md`
```json
{
  "change": {"change_id": "SCV000000000@2026-10", "release": "2026-10", "kind": "UP_TO_ACTIONABLE", "vcv": 0, "gene": "BRCA2",
             "submitter": "<real submitter>", "from_cls": "VUS", "to_cls": "LP", "submitter_evaluated": "2026-06-15"},
  "tenant": "demo", "run_id": null, "dry_run": true,
  "gene_rule": {"inheritance": "AD", "review_always": false, "pruning_valid": true, "reason": null},
  "carriers": [{"pid": "A-P", "label": "Ana, proband (fictional)", "verdict": "DIRECT_NOTICE", "notice_type": "UPGRADE",
                "owner": {"status": "RESOLVED", "owner": "Dr Sofia Lindqvist (fictional)", "chain": ["Dr Ama Okafor (fictional)", "Dr Sofia Lindqvist (fictional)"]}}],
  "relatives": [{"pid": "A-S", "verdict": "DIRECT_NOTICE", "notice_type": "NEW_RISK", "channel": "DIRECT", "degree": 1, "source_pid": "A-C",
                 "derivations": [{"source_pid": "A-C", "path": ["A-C", "A-UN", "A-PGF", "A-FA", "A-S"], "open": true, "direct_ok": true, "failed": []},
                                 {"source_pid": "A-P", "path": ["A-P", "A-FA", "A-S"], "open": true, "direct_ok": false,
                                  "failed": ["source Ana, proband (fictional) did not consent to family contact"]}]}],
  "decisions": [{"decision_id": "dec-A-S-2022", "kind": "DISCHARGE_FROM_SCREENING", "rested_on_cls": "VUS"}],
  "baseline": {"letters": [{"to": "Dr Ama Okafor (fictional)", "active": false}], "relatives_reached": 0, "decisions_reopened": 0},
  "disclaimer": "Decision support for genetic counsellors. Not medical advice. Nothing is sent without a named counsellor's approval. People and organisations shown are fictional; ClinVar data are real."
}
```

---

## 7. Agents and handoffs

Agents are deterministic in-process workers with narrow tools. Inside a tenant they hand work to each other through `Task` nodes; across tenants only through `Handoff` nodes written into the target graph.

| Agent | Tenant | Does | Queries |
|---|---|---|---|
| Watcher | kb | daily: checks the archive listing; ingests a new monthly archive as a DELTA (K3, K4, K5, K6); then triggers duty runs for every lab tenant whose reported variants (T4) changed; triggers the Curator | K3-K6, K14, K16, T4 |
| Tracer | lab | builds a duty map: X1, C1, L1; writes OWNER_LOOKUP and REOPEN_CHECK handoffs into the paired hs graph; assembles; writes the Run (L2) | X1, X2, C1, L1, L2, L8, L17, A2 |
| Steward | hs | claims handoffs (L10), resolves owners (W1-W4), finds and reopens decisions (D1, D2), writes replies into the lab graph (L8), completes (L11); on NOTIFY_DIRECT creates a DELIVER_NOTICE task for the owner | L9-L11, W1-W4, D1, D2 |
| Drafter | lab | drafts every DIRECT and LETTER duty from `data/notice_templates.json` (optional LLM rephrase, quote-checked); opens APPROVE_NOTICE tasks with the playbook (L3) | L3, L15 |
| Curator | lab | reconsideration queue: K11 for the mirrored submitter -> Recon items (L12) + RECONSIDER_SUBMISSION tasks; after each new release K12 -> RECON_CLOSED events (L13) | K11, K12, L12-L14 |
| Human | lab/hs | a named genetic counsellor or medical director (a Clinician in the hs graph) claims, approves or rejects tasks | L4-L7, D3 |

Task protocol: OPEN -> CLAIMED (`lease_until = now + 2 min`, L4) -> AWAITING_APPROVAL (when an agent hands off to a human, L15) -> DONE; stale leases return to the pool; every transition writes a signed Event.
Handoff protocol: OPEN -> CLAIMED (`lease_until = now + 60 s`, `attempts + 1`, L10) -> DONE with `result_json` (L11); a crashed worker's handoff is re-claimed after the lease expires; after 5 attempts the sweeper marks it FAILED and opens a HANDOFF_FAILED task. Replies are written into the sender's graph with id `<handoff id>:reply`; the sender polls L17 for up to 5 s, then renders `PENDING_HANDOFF` and the sweeper completes later.

The loop is ClinVar's own update, and we say so: a reconsideration item is closed by evidence from a later monthly archive (the submission's version and class), not by anything our agent caused. What the agent contributes is that the open question is remembered across releases, routed to an owner, and closed with a citation the moment the evidence appears; the same archive ingestion then reopens downstream duties automatically.

---

## 8. API (FastAPI, `services/api`)

Summary only. **`docs/API.md` is the authoritative contract.** Tenant ids in paths are `demo` (graphs `lab_demo` + `hs_demo`) or `sbx_<8hex>` (graphs `sbx_<8hex>_lab` + `sbx_<8hex>_hs`).

| Method and path | Returns |
|---|---|
| `GET /api/health` | FalkorDB status, graphs, kb releases and counts, NCBI status |
| `GET /api/releases`, `/api/releases/{r}/summary` | K14, K15 |
| `GET /api/releases/{r}/submitters`, `/api/releases/{r}/submitters/{id}/changes`, `/api/releases/{r}/submitters/{id}/differs-from-panel` | K8, K7, K11 |
| `GET /api/variants/{vcv}`, `GET /api/changes/{change_id}` | variant status (K9, K10 or live K13), K17 |
| `POST /api/duty-map` | DutyMap (dry run on fixed tenants; writes a Run in sandboxes) |
| `POST /api/sandbox`, `GET /api/tenants`, `GET /api/tenants/{t}/overview`, `/families/{family}`, `/runs`, `/runs/{id}`, `/duties/{id}/trace`, `/events` | tenants and memory |
| `POST /api/tenants/{t}/people/{pid}/consent`, `/tests`, `POST /api/tenants/{t}/families` | consent and test changes, seed a synthetic family around any real change |
| `GET /api/tenants/{t}/tasks`, `POST /api/tenants/{t}/tasks/{id}/claim|approve|reject` | approval queue |
| `GET /api/tenants/{t}/roster`, `/owner`, `/decisions/reopened`, `/decisions/stale`, `POST /decisions/{id}/replace` | the health-system brain |
| `GET /api/tenants/{t}/recon`, `POST /api/tenants/{t}/recon/refresh`, `GET /api/loop/replay` | reconsideration loop |
| `GET /api/tenants/{t}/algo/families`, `/algo/multi-carrier`, `/algo/cascade` | A1, A2, A3 |
| `GET /api/eval` | eval report |
| `POST /api/admin/kb/load`, `/api/admin/watch/run` | admin |

Public access: kb reads and dry-run duty maps on `demo` are open; tenant writes need the sandbox token (visitors) or `ADMIN_TOKEN`. Visitors never write to `lab_demo`/`hs_demo`. Rate limits: duty-map 30/min/IP, variant 60/min/IP, sandbox 3/h/IP, everything else 120/min/IP; NCBI calls go through one shared limiter.

---

## 9. MCP server (`/mcp`, streamable HTTP)
| Tool | Arguments | Returns |
|---|---|---|
| `variant_status` | `vcv` (int), `as_of` (YYYY-MM, optional) | every submission's current class with stars and evaluation date, the aggregate, recent class changes, which submissions differ from an expert-panel review, and the instruction "do not quote one submission's class as the variant's classification" |
| `duty_map` | `change_id` or (`vcv` + `release`), `tenant` (default `demo`), `token` (optional) | counts by verdict, carriers and relatives with verdicts and owners (labels only), reopened decisions, link to `/duty/<change_id>`; full DutyMap as structured content |
| `explain_person` | `change_id`, `pid`, `tenant`, `token` | every derivation with path, pruning and failed conditions, the owner chain, the decision trace |
| `owner_today` | `tenant`, `clinician_id` or `pid` | owner, chain, or ORPHAN with dead ends |
| `submitter_changes` | `submitter_id` or `submitter_name`, `release` | the submitter's class changes in that release |
| `reconsideration_queue` | `submitter_id`, `as_of` | submissions whose class differs from a current expert-panel review (neutral wording) |

Connect from Claude Code (document in README):
```bash
claude mcp add --transport http recontact https://<api-host>/mcp
```
Demo prompt (clinical-assistant role): "You are drafting a clinic letter that mentions BRCA2 VCV 51579. Before you state its classification, check with recontact, and tell me whether any family duties are open for the change in our demo lab."

---

## 10. Web app (`apps/web`, Next.js on Vercel)

Summary only. **`docs/UI.md` is the authoritative page, state and copy specification.**
1. `/` **What changed in ClinVar**: release picker (default 2026-10), "Pick any lab" submitter picker (K8), that submitter's class changes (K7) with kind chips, a VCV search box.
2. `/variant/[vcv]` **Variant status**: per-submission classifications as of a release, history, expert-panel line, neutral "differs from the current expert-panel review" flags, "Seed a synthetic family with this change" (sandbox).
3. `/duty/[changeId]` **Duty map**: pedigree (lit carriers, at-risk relatives, greyed pruned side), green/red derivation edges, verdict table, owner chains, reopened decisions, baseline panel, proof drawer, "How we decided" Cypher.
4. `/queue` **Approval queue**: tasks with drafts and playbook steps; approve/reject as a named counsellor (sandbox).
5. `/org` **Riverside Health (fictional)**: roster, who owns each patient's follow-up today, succession chains, reopened decisions, "decisions resting on releases older than ...".
6. `/loop` **Reconsideration loop**: items opened in 2026-08, closed by the 2026-09/2026-10 archives, with the honest framing.
7. `/mcp`, 8. `/eval`, 9. `/how-it-works`.

---

## 11. Demo tenants (fictional, `data/demo_tenants/`)

### 11.1 Placeholder resolution (`scripts/seed_demo.py`, deterministic)
1. `UP`: among ClassChanges in release 2026-10 with kind UP_TO_ACTIONABLE whose gene is AD and not `review_always`, group by submitter; choose the submitter with the most such changes that also has at least one DOWN_FROM_ACTIONABLE and one VUS_RESOLVED_BENIGN in an AD non-review gene in 2026-10 (ties: submitter name ascending). That submitter is `{{MIRRORED_SUBMITTER}}`. Its UP change with `from_cls == VUS` and the smallest VCV (if none starts at VUS, the smallest VCV of any UP change) is `{{UP_*}}`; likewise `{{DOWN_*}}` and `{{VUSB_*}}` (smallest VCV of each kind).
2. If no submitter has all three kinds in 2026-10, repeat with 2026-09; if still none, choose each change independently (most changes per submitter) and set `mirrors_submitter` to the UP change's submitter; record `"fallback": true`.
3. Write `data/demo_tenants/resolved.json` (`{mirrored_submitter, up:{change_id, vcv, scv, gene, from_cls, to_cls, from_version}, down:{...}, vusb:{...}, fallback}`) and commit it after the first run, so the video stays stable. Re-seeding with an existing resolved.json reuses it.
4. Load `lab_demo` (P6, P1, P2, P3, P4, P5, P15) and `hs_demo` (P6, P7, P8-P14) into empty graphs, then precompute and store one Run per demo change (Tracer, not dry run) so the fixed tenant opens instantly.

### 11.2 Expected duty maps (golden tests)
**Family A, UP change (the cousin path).** Ana (proband) refused family contact; Vera (cousin, carrier) consented to direct contact; Rosa (mother) tested negative; Leo (son) exercised the right not to know; Irena (aunt) lives in the letter-only region J-B; Jan is a half-brother through the father; the paternal grandfather and maternal grandfather are deceased.
| Person | Verdict | Notes |
|---|---|---|
| Ana (A-P) | DIRECT_NOTICE / UPGRADE | owner Dr Lindqvist: Dr Okafor retired 2023-06-30 and handed her panel (1 hop) |
| Vera (A-C) | DIRECT_NOTICE / UPGRADE | owner Dr Chen: Dr Brandt -> Northgate Clinic -> succeeded by Riverside Clinic 2024-03-01 -> led by Dr Chen (3 hops) |
| Mila (A-S), Tomas (A-FA), Pavel (A-UN), Oto (A-CS), paternal grandmother (A-PGM) | DIRECT_NOTICE / NEW_RISK | through Vera; Mila degree 1 |
| Jan (A-HS) | DIRECT_NOTICE / NEW_RISK | through Vera; degree 2 (half-brother) |
| Irena (A-A2) | VIA_FAMILY_LETTER | failed: J-B (illustrative rule) does not allow direct contact |
| Leo (A-CH) | BLOCKED_NO_PERMITTED_PATH | failed: source Ana did not consent to family contact; relative exercised the right not to know |
| Lucia (A-MA), maternal grandmother (A-MGM) | NOT_AT_RISK_NO_INHERITANCE_PATH | pruned by Rosa (tested negative 2021-06-01) |
| Elena (A-OW) | not listed | partner, never a blood relative |
| Decision dec-A-S-2022 | REOPENED | Mila's discharge from screening rested on the old class |

**Family D, same UP change.** Karl (D-P, deceased carrier, ordering clinician Dr Ellis): NEEDS_REVIEW, owner ORPHAN (Harbour Heart Clinic closed 2024-06-30, no successor; Dr Novak's lead ended) -> medical director Dr Garcia; dead ends listed. Greta (D-DA) and Felix (D-SO): NEEDS_REVIEW (source deceased).
**Baseline for the UP change:** 3 letters (Dr Okafor, Dr Brandt, Dr Ellis), 3 of 3 inactive; 0 relatives; 0 decisions.
**Family B, DOWN change.** Noor (B-P): DIRECT_NOTICE / CORRECTION (owner Dr Lindqvist, 0 hops). Sana (B-S, told in March 2024 by direct notice): DIRECT_NOTICE / CORRECTION. Hana, Omar, Lina: NO_ACTION. Decisions dec-B-P-2024 (surgery recommendation) and dec-B-S-2024 (surveillance): REOPENED.
**Family C, VUS_RESOLVED_BENIGN change.** Arun (C-P): DIRECT_NOTICE / VUS_RESOLVED, owner Dr Lindqvist through Dr Okafor's handoff. Dev, Ravi, Meera: NO_ACTION. Decision dec-C-P-2023: REOPENED (its owner Dr Okafor is inactive; resolved to Dr Lindqvist).
**Memory:** after Mila's notice is approved, re-running the UP change gives Mila ALREADY_NOTIFIED. Changing Vera's `family_share` to `none` (C2) and recomputing turns Mila, Tomas, Pavel, Oto, the grandmother and Jan into BLOCKED_NO_PERMITTED_PATH and Irena into BLOCKED as well (Ana refused too).

If the gene chosen for `UP` were not AD, the golden tests would fail by design; the resolver only picks AD non-review genes.

---

## 12. Synthetic pedigree generator (`scripts/generate_world.py`)
- Purpose: eval worlds and "seed a family with this change" in sandboxes. Output has exactly the shape of `data/demo_tenants/lab_demo.json` and `hs_demo.json`, so the same loader (P queries) is used.
- **Seeded and deterministic**: `random.Random(seed)`; identical seed and scenarios produce byte-identical JSON (sorted keys, stable ids `<world>-<family>-<role>-<n>`). Test G107.
- **Calibrated and published**: `data/generator_params.json` lists every parameter with `kind: source` (e.g. first-degree cascade testing uptake 0.41, Frey et al., JCO 2022) or `kind: assumption`. The README states that the people are synthetic and the calibration is partly assumed.
- Structure: 4 generations around the proband (generation index 2), sibships Poisson(2.0) truncated to 0-6, partners, 8% half-sibships, deceased by generation, birth years by generation.
- Genetics: gene drop from one founder carrier among the proband's four grandparents with Mendelian transmission (0.5 per meiosis), no de novo; test results reveal the simulated truth, so negative tests prune consistently. Non-AD genes still get pedigrees (their relatives must be NEEDS_REVIEW).
- Consent, preferences, jurisdictions, recontact and the health system (40 clinicians, 25% departed with a panel handoff, 5% without, 6 clinics with one closure with a successor and one without, decisions resting on the class at issue) follow `generator_params.json`.
- The generator never reads real patient data. It never writes `labels`.

---

## 13. Frozen eval (`eval/`)
Protocol (committed before any rule code exists; G108, G109):
1. **Real transitions.** `scripts/extract_clinvar.py --eval` writes every in-scope SCV class change between the 2024-10 and 2026-10 archives to `eval/transitions_2024-10_2026-10.tsv`. `eval/select_transitions.py` applies `data/eval_skeleton/transitions_selection.json` (seed 20261018): 25 UP_TO_ACTIONABLE, 15 DOWN_FROM_ACTIONABLE, 10 NEEDS_REVIEW_CLASS, 10 unchanged controls (half with a version bump), at most 3 per gene per stratum, at least 5 UP in review genes. Output `eval/selected_transitions.json`.
2. **Hand-labelled hard cases.** Labeller B (a human) completes `data/eval_skeleton/hard_cases.skeleton.json` into `eval/hard_cases.json` (40 cases, 18 categories: pruning, cousin path, deceased source, revoked consent, not to know, letter-only jurisdiction, two-proband family, half sibling, closed-clinic orphan, panel handoff, non-dominant gene, review gene, downgrade correction, VUS resolved, within tier, conflicting class, already notified, no report cites) and writes the per-person labels (verdict, notice type, channel, owner or ORPHAN, reopened decisions) **by reading the rules in this blueprint, before `app/engine/duty.py` exists**.
3. **Independent reference implementation.** Labeller B writes `eval/reference_impl.py` (plain Python over the world JSON, no FalkorDB, no shared code with the engine) from sections 6.1-6.6.
4. **Commit and hash.** `eval/labels.sha256` holds sha256 of `eval/hard_cases.json` and of `eval/reference_impl.py`; `eval/heldout_seeds.sha256` holds sha256 of the JSON list of 30 held-out world seeds chosen by B (commit-reveal: the list is revealed only at the final eval). Git history must show these commits before the first commit of `app/engine/duty.py` (G109 Verify). Hashes go in the README and on `/eval`.
5. **Run.** `python eval/run_eval.py --api <url>` loads each hard case into a scratch sandbox and each world (dev seeds 1-10 during development; the 30 held-out seeds once at the end), runs the duty map, and writes `eval/report.json`.
6. **Metrics.** Per-person verdict accuracy on hard cases vs human labels; **N of 30** held-out worlds whose duty map exactly matches the reference implementation; owner accuracy; reopened-decision precision and recall; **safety count** = notices proposed (DIRECT_NOTICE or VIA_FAMILY_LETTER) where the reference says no permitted path: **must be 0**; NEEDS_REVIEW_CLASS transitions: 10 of 10 with zero notices; unchanged controls: 10 of 10 with no ClassChange created.
7. **Baseline.** The amended-report baseline on the same worlds: relatives reached (always 0), letters addressed to inactive clinicians, decisions reopened (0). Shown on `/eval` beside the engine. This is the answer to "is the graph decoration?": everything beyond the proband list requires the traversals.

---

## 14. Repo layout
```
recontact/
  AGENTS.md  BLUEPRINT.md  CURSOR_PROMPT.md  README.md  LICENSE  Makefile  docker-compose.yml  .env.example
  .cursor/rules/recontact.mdc
  docs/GOALS.md docs/FLOWS.md docs/API.md docs/UI.md docs/queries.cypher docs/REQUIREMENTS.md
  docs/OPEN_POINTS.md docs/EXPLAINER.md docs/TASKS.md docs/RUNBOOK.md (G132) docs/evidence/
  data/genes.json data/normalisation.json data/releases.json data/generator_params.json
  data/notice_templates.json data/playbooks.json
  data/demo_tenants/lab_demo.json data/demo_tenants/hs_demo.json data/demo_tenants/resolved.json (G040)
  data/eval_skeleton/hard_cases.schema.json data/eval_skeleton/hard_cases.skeleton.json data/eval_skeleton/transitions_selection.json
  data/clinvar/variants.tsv.gz data/clinvar/scv_2026-08_base.tsv.gz data/clinvar/scv_2026-09_delta.tsv.gz
  data/clinvar/scv_2026-10_delta.tsv.gz data/clinvar/withdrawn_<release>.txt data/clinvar/MANIFEST.json   (G020-G022)
  scripts/extract_clinvar.py scripts/seed_demo.py scripts/generate_world.py scripts/smoke.sh scripts/mcp_smoke.sh scripts/bench.sh scripts/load.py
  services/api/
    pyproject.toml  Dockerfile
    app/main.py app/config.py app/logging.py app/errors.py app/security.py
    app/graph/db.py app/graph/queries.py app/graph/tenants.py
    app/clinvar/parse.py app/clinvar/load.py app/clinvar/eutils.py app/clinvar/ftp.py
    app/engine/duty.py app/engine/degree.py app/engine/baseline.py
    app/agents/watcher.py app/agents/tracer.py app/agents/steward.py app/agents/drafter.py app/agents/curator.py
    app/agents/handoff.py app/agents/tasks.py app/llm.py
    app/mcp_server.py
    app/routes/health.py app/routes/kb.py app/routes/duty.py app/routes/tenants.py app/routes/tasks.py
    app/routes/org.py app/routes/loop.py app/routes/algo.py app/routes/eval.py app/routes/admin.py
    tests/ (fixtures: the verified query fixture, demo tenants with a resolved.json fixture, golden duty maps)
  apps/web/ (Next.js)
  eval/select_transitions.py eval/selected_transitions.json eval/hard_cases.json eval/reference_impl.py
  eval/labels.sha256 eval/heldout_seeds.sha256 eval/run_eval.py eval/report.json eval/transitions_2024-10_2026-10.tsv
```

---

## 15. Build plan (about 22 hours, two people plus Cursor)
Hour 0 is the moment work starts. Person A: backend and graph. Person B: frontend, eval labels and reference, video. Details in `docs/TASKS.md`; goals in `docs/GOALS.md`.

| Hours | Person A | Person B | Milestone |
|---|---|---|---|
| 0-1 | scaffold, compose, Railway FalkorDB + API, schema (G001-G019) | Vercel, Next.js shell, design tokens | both deploy "hello" |
| 1-5 | start the ClinVar extract in the background (download about 1.6 GB); kb loader with `KB_SCOPE=dev`, then `sf`; kb endpoints; E-utilities client (G020-G039) | `eval/select_transitions.py`; **hard-case labels and reference implementation before the engine exists** (G108, G109); `/` and `/variant` pages against the API | real class changes per submitter on the public URL |
| 5-8 | seed demo tenants; exposure, consent, duty engine, duty-map API, no-path proofs (G040-G054) | `/duty` page with pedigree and derivations (G055-G058) | **hour 8: public URL shows a real submitter's class change and Family A's duty map with the cousin path, the pruned maternal side and the BLOCKED proof** (G059) |
| 8-13 | hs tenant, owners, handoffs, decisions, algorithms (G060-G079) | `/org`, owners and decisions on `/duty` | owners, ORPHAN and reopened decisions live |
| 13-16 | approvals, Drafter, memory, consent/test changes, MCP (G080-G099) | `/queue`, `/mcp`; record Claude Code calling `variant_status` | MCP works from Claude Code |
| 16-19 | Curator loop, Watcher, sandbox, seed-a-family, generator (G100-G107, G117, G118) | eval runner, `/eval`, `/loop` (G110-G116) | all three demo shots work end to end (G119) |
| 19-21 | deploy hardening, load, security, runbook (G120-G134) | polish, empty and error states, mobile | stable deployment |
| 21-23 | README: data model, Cypher, setup, tracks, AI disclosure (G135-G140) | 3-minute video, blog draft | submission assets ready |
| 23-24 | buffer, submit (G141-G146) | buffer | submitted |

**The hour-8 core (never break):** kb with real class changes, submitter picker, variant status, Family A duty map with mechanism 1 (exposure with pruning) and mechanism 3 (AND/OR consent), deployed. Everything after hour 8 is additive.

**Cut order if behind** (cut from the top; never cut the hour 8 core, mechanism 2 (owners), mechanism 4 (reopened decisions), the approval gate, the eval or the README):
1. G147 "Ask the org" templated questions.
2. G143 blog post.
3. G114 `/how-it-works` page (move content into README).
4. G077 playbook steps on task cards (Playbook nodes are still seeded and attached).
5. G104 release replay through GRAPH.COPY (keep the Watcher).
6. G082 LLM rephrasing of drafts (templates only).
7. G106 seed-a-family in sandboxes (keep fixed tenants and consent toggles in sandboxes).
8. G093 and G094 extra MCP tools (keep `variant_status` and `duty_map`).
9. G102 `/loop` page (keep the Recon list in `/queue`).
10. G105 sandboxes (fixed tenants read-only; toggles disabled; approvals demonstrated with `ADMIN_TOKEN` in the video).
11. G030 live E-utilities lookups for out-of-scope VCVs (answer "outside the loaded gene set").

---

## 16. The 3-minute video
| Time | Shot | Track |
|---|---|---|
| 0:00-0:15 | Cold open: "When a lab changes a BRCA call, the cousin who never got tested still never hears. Only 41% of at-risk relatives ever complete cascade testing." | hook |
| 0:15-0:45 | Real data: pick any lab; its ClinVar class changes between the September and October 2026 archives, diffed inside FalkorDB; one click shows the per-submission history and the expert-panel line | Track 1 |
| 0:45-1:35 | Duty map for the upgrade: the pedigree lights; the green derivation through cousin Vera reaches Mila although Ana refused; Leo BLOCKED with every failed condition; the maternal side greyed by Rosa's negative test; owner chains (retired oncologist -> successor; closed clinic -> ORPHAN -> medical director); Mila's 2022 discharge reopened; baseline panel: 3 letters to 3 departed doctors, 0 relatives | Tracks 1 + 3 |
| 1:35-2:05 | Two tenant graphs on one FalkorDB: the lab's Tracer writes handoffs into the health system's graph; the Steward answers; nothing about blocked people crosses. Approve Mila's notice as a counsellor; re-run: ALREADY_NOTIFIED. Downgrade: Sana, told in 2024, gets a correction; two decisions reopen | Tracks 2 + 3 |
| 2:05-2:30 | Claude Code as a clinical assistant calls `variant_status` and `duty_map` over MCP before quoting a class | Track 1 |
| 2:30-2:50 | Loop and eval: an item opened in the August archive closes with the October archive's evidence (ClinVar's own update, cited); eval: N of 30 held-out worlds exact, safety count 0, labels hash | proof |
| 2:50-3:00 | Live URL, MCP command, "Decision support for genetic counsellors. Not medical advice. People shown are fictional; ClinVar data are real." | close |

Record the G054 clip (FalkorDB stopped -> 503) separately for the README.

---

## 17. Risks and answers
| Risk / objection | Answer |
|---|---|
| "Patients are synthetic, so the hard part is assumed" | The real layer is the opener and the judge input: every real submitter's monthly class changes, diffed in FalkorDB, plus live per-submission status for any VCV. People are synthetic only where privacy forces it, generated by a published, seeded, calibrated generator; the eval is frozen with human labels and held-out seeds |
| "Labs already do recontact" | Conceded and shown: the baseline panel is exactly the amended-report list. We claim only relatives, today's owner, a permitted channel and reopened decisions, all measured on the eval |
| "The loop is ClinVar's own update, not caused by the agent" | Agreed and stated in UI copy: the loop closes on evidence from a later archive; the agent's role is memory, routing and citation, and the same ingestion reopens downstream duties |
| "A reconsideration note to a lab has few real targets" (63 of 2,185 expert-panel P/B variants had an older opposite-direction SCV in research) | The Recon queue is a lab-internal task of a fictional tenant, not outreach; its value in the demo is the replayable closure, not volume |
| Wording traps about named labs | Copy rules (UI.md) and a test (G057) forbid "stale/wrong/incorrect/outdated/error/mistake"; neutral phrasing only |
| Clinical oversimplification | Automatic relative routing only for AD genes without a review flag; everything else NEEDS_REVIEW; jurisdiction rules labelled illustrative; drafts are not advice; human approval |
| Scope (buildability was the weakest panel score) | One lab tenant + one health-system tenant; mechanism 2 is a succession chain over 4 edge types; no device stretch; layered plan with a working hour 8; explicit cut order |
| kb size and load time on Railway | Measured scale test; `KB_SCOPE=core` fallback; extracts committed so a reload never needs NCBI |
| NCBI unavailable during judging | Everything except live lookups runs from the kb; live lookups degrade to "outside the loaded gene set" with a 503 code for the lookup only |
| "FalkorDB algorithms are barely used" | We use WCC and BFS where they do work and say why we do not add PageRank or betweenness; the depth is in bounded multi-hop paths with list predicates, multi-graph tenancy and in-graph diffs |
| Overlap with a FalkorDB family-risk tracker entry | Different trigger, outputs and mechanisms (section 1); public material never names other entries (G144) |

---

## 18. Decided on 18 Oct 2026 (do not revisit)
- Product: Recontact. Primary Track 1; also Tracks 2 and 3.
- Hosting: Vercel (web) + Railway (API and FalkorDB in Docker, 2 GB). Not the FalkorDB Cloud free tier.
- MCP SDK pinned `mcp>=1.10,<2`; mount exactly as section 3.
- Data: ClinVar monthly archives 2026-08 (base), 2026-09, 2026-10 (deltas), variant_summary 2026-10; 2024-10 for eval only; Watcher ingests 2026-11 when it appears. No weekly files.
- Scope: ACMG SF v3.3 minus TTN (`KB_SCOPE=sf`); `core` fallback.
- Tenants: one lab (`lab_demo`, fictional, mirroring one real submitter) + one health system (`hs_demo`, fictional) + sandboxes. No second health system.
- Mechanisms: 1 exposure with pruning (X2/C1), 2 owner succession (W1-W4), 3 consent AND/OR (C1), 4 reopen on change (D1-D3). (Milestones are M1-M8; mechanisms are numbered in words to avoid confusion.) Device-recall stretch dropped.
- Algorithms: WCC (A1, A2) and BFS (A3) only.
- Jurisdiction rules: two illustrative regions (J-A direct allowed, J-B letter only).
- Extracts of public ClinVar data are committed to the repo (public data, smaller and reproducible); full archives are never committed.
- Repository licence: MIT (team to confirm ownership per rule 15).

## 19. Submission checklist
- [ ] Live URL (Vercel) and API (Railway) up; `/api/health` green with three releases loaded.
- [ ] Public repo with README: setup, graph data model (sections 5.1-5.4), Cypher queries (link `docs/queries.cypher`; explain K5, X2, C1, W1, D1, K11/K12, A2), algorithms used (`algo.WCC`, `algo.BFS`, bounded variable-length paths), MCP connect command, tracks (Track 1 primary; Tracks 2 and 3), AI coding assistant disclosure, synthetic-data statement and calibration.
- [ ] Demo video (3 minutes) linked in README and the submission form.
- [ ] `eval/labels.sha256` and `eval/heldout_seeds.sha256` committed before the engine and quoted in README; `/eval` shows results; safety count 0.
- [ ] Blog post (side prize) drafted from the README story.
- [ ] Everyone can explain the graph model and the queries (`docs/EXPLAINER.md`).
- [ ] LICENSE file added and ownership agreed (rule 15).
- [ ] Every goal in `docs/GOALS.md` done or struck through with a reason.
