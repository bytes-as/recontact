# Requirements traceability

Every requirement and judging signal on the hackathon page (overview, tracks, sponsor section, FAQ), the rules page and the schedule, mapped to where Recontact meets it and the goal in `docs/GOALS.md` that proves it. Rows are reused from the ModelBrain pack (source pages: https://www.wemakedevs.org/hackathons/falkordb, `/rules`, `/schedule`, `/resources`, read 17-18 Oct 2026) and re-mapped to Recontact goals.

**Prime constraint: FalkorDB is the heart of the product.** The FAQ says it must be the primary graph database and support a central part of the product; rule 3 disqualifies a graph that is only decoration. Section C lists every FalkorDB capability we use. Row ids: H = hard rule, S = judging signal (not to be confused with query names in `docs/queries.cypher` or flow names F0-F20 in `docs/FLOWS.md`).

## H. Hard rules (failing any of these risks disqualification)

| # | Requirement (source) | How Recontact meets it | Goals |
|---|---|---|---|
| H1 | FalkorDB must be the primary graph database and support a central part of the product (FAQ; rule 2) | The ClinVar release diff (K5), exposure (X2), consent (C1), owners (W1-W4), reopened decisions (D1), reconsideration (K11, K12) and all memory live in FalkorDB; no other database | G010-G014, G025, G042-G053 |
| H2 | The graph must do real work: if the product works without FalkorDB, it is decoration (rule 3) | Every answer is a Cypher traversal or algorithm call; the Python engine only applies a decision table to graph rows; a test proves the endpoints fail without FalkorDB; the eval compares against the amended-report baseline | G054, G110, G111, G123 |
| H3 | Main coding and the FalkorDB implementation are new work during the event (FAQ; rule 8) | All code written 18 Oct; only libraries and public data reused | G001 |
| H4 | Data must be public, synthetic or own; no private, login-protected, paywalled or personal data (rule 6) | ClinVar public archives and E-utilities (NCBI places no restrictions on use); every person, family, consent, clinician, clinic, decision and organisation is synthetic, flagged and labelled "(fictional)"; NCBI calls carry only Variation IDs | G020-G022, G040, G107, G134 |
| H5 | Public source-code repository (rule 10) | GitHub public repo | G135 |
| H6 | README with setup instructions and the graph data model (rule 10) | README "Run locally", "Deploy", "Graph data model" | G136, G137 |
| H7 | The Cypher queries or graph algorithms the product depends on (rule 10) | README "Queries and algorithms" linking `docs/queries.cypher`, explaining K5, X2, C1, W1/W2, D1, K11/K12, A2, A3 | G138 |
| H8 | Demo video showing the working project (rule 10; FAQ) | 3-minute video per BLUEPRINT section 16 | G139 |
| H9 | Live deployment, or complete local setup if it cannot be deployed (rule 10; FAQ "live deployment preferred") | Vercel web + Railway API + Railway FalkorDB; `docker compose up` local path documented | G015, G120-G122 |
| H10 | Name every track entered at submission (rule 5) | Track 1 (primary), Track 2, Track 3 | G141 |
| H11 | AI coding assistants allowed but must be disclosed (rule 11; FAQ) | README "Built with AI assistance" | G140 |
| H12 | Participants understand and can explain the graph model, queries, architecture and decisions (rule 12; FAQ) | `docs/EXPLAINER.md`; every member rehearses | G142 |
| H13 | Not entirely AI-generated without meaningful contribution, verification or understanding (rule 13) | Humans write the eval labels and the reference implementation, check the gene table, review every PR and run the demo | G024, G108, G109, G142 |
| H14 | Solo or up to 4 per team; each person in one team (rule 1) | Team registered on WeMakeDevs | G141 |
| H15 | Respect, no plagiarism, no judging manipulation (rules 16-18) | No copying other entries; other entries are never named in public material | G144 |
| H16 | Submissions close 18 Oct 2026, 11:59 PM IST (rule 7; schedule) | Plan ends at H23 with a buffer; form by 23:00 IST | G141 |
| H17 | Run FalkorDB however suits you: Docker, self-hosted or FalkorDB Cloud; any language or platform (rule 4) | FalkorDB in Docker on Railway and locally | G002, G120 |
| H18 | Frameworks, libraries, public APIs, templates and public datasets may be used; the original work is what is judged (rule 9) | Original work: graph model, in-graph diff, duty engine, agents and handoffs, MCP tools, generator, eval, UI; dependencies listed | G137 |
| H19 | IP belongs to the team; agree on ownership before submitting (rule 15) | Team agrees and adds a LICENSE (MIT suggested) | G135 |
| H20 | WeMakeDevs Code of Conduct applies (rules 16-18) | Respectful conduct; neutral wording about real labs | G032, G057, G144 |

## S. What the brief and tracks ask for (judging signals)

| # | Signal (source) | Where Recontact shows it | Goals |
|---|---|---|---|
| S1 | "Build a working agent, or a group of agents, with FalkorDB as its context layer. The graph has to shape what the agent does" (challenge) | Watcher, Tracer, Steward, Drafter and Curator read and write FalkorDB on every step; their actions (who is notified, through whom, which decision reopens) are decided by graph results | G044, G062, G081, G100, G103 |
| S2 | "An agent that acts on connected data, remembers what it learns, and can show how it got to each answer" (brief) | Acts: duty maps, drafts, reopened decisions, reconsideration items. Remembers: notices, consents, runs across releases. Shows: derivation paths, failed conditions, owner chains, Cypher | G050, G051, G085, G086, G097 |
| S3 | Work the graph has to do: "Follow connections across data" | Variant -> report -> carrier -> common ancestor -> relative; ordering clinician -> handoffs and clinic successions -> current owner; decision -> rested-on class | G042, G061, G065 |
| S4 | "Remember across sessions" | Notices, consents, tests, runs and Recon items persist per tenant; ALREADY_NOTIFIED and CORRECTION across releases | G085, G086, G087 |
| S5 | "Share state between agents" | Task leases inside a tenant; Handoff nodes with leases across tenants; Tracer -> Steward -> Drafter -> human | G062, G063, G075 |
| S6 | "Connect people, projects, and decisions" | Families, carriers, clinicians, clinics, decisions, approvals, notices | G040, G060, G070 |
| S7 | "Show the path behind an answer" | Proof drawer with every derivation, pruning and failed condition; owner chain; Cypher | G051, G055, G097 |
| S8 | "Pick a task where the answer depends on how things connect" | A relative's duty depends on kinship paths, negative tests on those paths, consents along them and today's succession chain | G043, G045 |
| S9 | Track 1 key focus: multi-hop reasoning | X2/C1 up-then-down kinship paths with interior pruning; W1 time-ordered succession chains up to 5 hops | G042, G061 |
| S10 | Track 1: graph queries and algorithms as agent tools | MCP tools `variant_status`, `duty_map`, `explain_person`, `owner_today`, `submitter_changes`, `reconsideration_queue`; `algo.WCC` (A1, A2) and `algo.BFS` (A3) | G073, G091-G094 |
| S11 | Track 1: tool selection through MCP | Claude Code chooses `variant_status` before quoting a class and `duty_map` for open changes | G090, G095 |
| S12 | Track 1: actions based on what the graph shows | Drafted notices behind approval, reopened decisions, ORPHAN routing to the medical director, reconsideration items, delivery tasks | G081, G083, G084, G067 |
| S13 | Track 1: explainable results | Every duty carries its derivations and failed conditions; NOT_AT_RISK and BLOCKED come with proofs | G051, G053 |
| S14 | Track 2: episodic, semantic and procedural memory | Episodic: runs, duties, notices, events. Semantic: the kb (genes, variants, SCV versions, class changes). Procedural: Playbook nodes on every task | G077, G085 |
| S15 | Track 2: persistent conversation history | `(:Conversation)-[:HAS_TURN]->(:Turn)-[:PRODUCED]->(:Run)` for MCP and web | G089 |
| S16 | Track 2: shared state and handoffs between agents | Handoff nodes written into the target tenant's graph, leases, retries, FAILED after 5 attempts | G062, G063 |
| S17 | Track 2: high-concurrency reads and writes | `ro_query` for reads; idempotent MERGE writes; leases with exactly one winner; 20 concurrent runs | G075, G124 |
| S18 | Track 2: separate memory per user or tenant | `kb` + lab + health-system graphs + per-visitor sandbox pairs (GRAPH.COPY) on one instance; minimum-necessary handoffs; consent-aware memory | G041, G064, G105 |
| S19 | Track 3: knowledge from docs, tickets and chats in one graph | ClinVar submissions (the field's public "tickets" about each variant) in kb; the organisation's decisions, approvals and duties in tenant graphs | G025, G069 |
| S20 | Track 3: who owns what, and who knows what | "Who owns each patient's follow-up today" (W1/W3), roster (W5), decision OWNED_BY / APPROVED_BY | G061, G072 |
| S21 | Track 3: tracing decisions back to their source | Decision -> RESTED_ON {class, release, SCV version} -> ClinVar URL; duty -> run -> class change -> release file sha256 | G070, G097, G038 |
| S22 | Track 3: keeping knowledge current as things change | Watcher ingests each monthly archive; reopen-on-change; Recon closure | G103, G065, G101 |
| S23 | Track 3: answers with clear sources | Every view cites the ClinVar release and SCV version; decisions cite sources | G036, G070 |
| S24 | "What breaks if this service goes down?" style questions (why graphs) | "Who must be told if this classification changes?" and "Which decisions break if this variant is downgraded?" | G050, G065 |
| S25 | Prize "best agent that uses a graph to make decisions and take action" (T1) | Primary track narrative | G139 |
| S26 | Side prize: best blog post | Blog post drafted from the README | G143 |
| S27 | Top 50 projects get T-shirts | Polish, live URL, clear README | G120-G138 |

## C. FalkorDB capabilities we use (the sponsor section, line by line)

| Sponsor claim | Our use | Goals |
|---|---|---|
| "Traversals are fast enough to run on every step of an agent loop" | Every MCP call runs K9 or X2/C1/W1/D1 live; duty map p95 under 1.5 s | G056, G124 |
| "One instance can hold thousands of isolated graphs, so each user, agent, or tenant gets its own" | `kb`, `lab_demo`, `hs_demo` and `sbx_*_lab/_hs` pairs on one instance; `kb_eval` and `kb_replay` scratch graphs | G041, G105, G104 |
| "Run it locally with Docker" | `docker compose up` with `falkordb/falkordb:latest` | G002 |
| Official clients | `falkordb` Python client | G010 |
| Cypher: match patterns, follow paths, return what the agent needs | All 81 blocks in `docs/queries.cypher`, including bounded variable-length paths with list predicates and the in-graph release diff | G011 |
| Context for AI agents: agent memory, multi-agent state, connected company knowledge | Ledger of runs and notices; Handoff and Task state; the health-system brain | G062, G085, G069 |
| Connect your agent stack: MCP | Our MCP server with six tools | G090-G096 |
| Connect your agent stack: GraphRAG-SDK, QueryWeaver, Graphiti, Cognee, LangChain, LlamaIndex | Not used in the core (our ontology is explicit and the answers must be deterministic); optional "ask the org" router over templated Cypher | G147 |
| One graph per user or tenant (multigraph topology) | Lab and health-system tenants and sandboxes | G041, G105 |
| Graph algorithms as agent tools: shortest path, PageRank, centrality, connected components, community detection | Connected components (`algo.WCC`: families, multi-carrier merge), traversal (`algo.BFS`: cascade view); we deliberately do not add PageRank or centrality where they would be decoration; "no path" proofs come from bounded MATCH patterns | G073, G074 |
| Explore the graph with FalkorDB Browser | Local compose exposes the Browser on port 3000; README walkthrough with screenshots of a ClassChange and Family A | G138 |

## E. Official resources (from the Resources page) and where we use them
| Resource | Use |
|---|---|
| Getting started: https://docs.falkordb.com/getting-started/ | Block 0 setup |
| Docs and Cypher: https://docs.falkordb.com/ , https://docs.falkordb.com/cypher/ | All queries |
| Docker and Compose: https://docs.falkordb.com/operations/docker | `docker-compose.yml`, Railway (data path `/var/lib/falkordb/data`, `REDIS_ARGS`, `FALKORDB_ARGS`) |
| FalkorDB Cloud: https://app.falkordb.cloud/ | Allowed fallback; free tier unsuitable (100 MB; stops after 1 day idle) |
| FalkorDB Browser: https://docs.falkordb.com/browser/ | README walkthrough (port 3000 locally) |
| Clients: https://docs.falkordb.com/getting-started/clients | `falkordb` Python client |
| Algorithms: https://docs.falkordb.com/algorithms/ | WCC, BFS |
| Integrations: https://docs.falkordb.com/integration/ | MCP |
| Community projects: https://www.falkordb.com/community-projects/ | Check before submission that we do not duplicate a listed project |
| Blog, How to build an agent that reasons over a graph: https://www.wemakedevs.org/blogs/how-to-build-an-agent-that-reasons-over-a-graph | Align README vocabulary |
| FalkorDB Discord: https://discord.com/invite/Y2mMT9VdMy | Ask if blocked |

## D. Gaps we accept (stated honestly in the README)
- People, families, consents, clinicians, clinics, decisions and both organisations are synthetic (privacy forces it); the ClinVar layer is real and the generator is published with its calibration.
- The demo lab is fictional and mirrors one real submitter's public classifications; real labs are described only neutrally and never contacted.
- Jurisdiction rules are an illustrative two-region rule set, not law.
- Automatic relative routing covers autosomal dominant genes without a review flag; all other genes go to a counsellor.
- The reconsideration loop closes on ClinVar's own updates; we claim memory and citation, not causation.
- Decision support for genetic counsellors, not medical advice; every notice needs a named counsellor's approval and is delivered outside the system.
