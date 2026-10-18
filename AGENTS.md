# AGENTS.md: rules for every coding agent working on Recontact

Read `BLUEPRINT.md` section 0 (document map) before writing code. The binding documents are AGENTS.md, BLUEPRINT.md, docs/GOALS.md, docs/FLOWS.md, docs/API.md, docs/UI.md, docs/queries.cypher, docs/REQUIREMENTS.md and data/*; this file is the short list of rules. When the spec and your instinct disagree, follow the spec and leave a note in `docs/TASKS.md` under "Questions for the owner".

## Deadline and priorities
- Submissions close Sunday 18 Oct 2026, 11:59 PM IST. Work through `docs/GOALS.md` top to bottom (147 goals with Accept and Verify); `docs/TASKS.md` is the hour-by-hour summary. Do not stop until every goal is done or explicitly struck through with a reason.
- The hour-8 core (real ClinVar class changes per submitter, variant status, and Family A's duty map with pruning and AND/OR consent, deployed) must never break. Every later feature is additive.
- If you are behind, cut only goals marked *(cuttable)*, in the order of BLUEPRINT.md section 15. Never cut the core, owner resolution (mechanism 2), reopened decisions (mechanism 4), the approval gate, the eval or the README requirements.

## Product rules (do not break)
1. Every answer comes from FalkorDB using the Cypher in `docs/queries.cypher`: the release diff (K5), exposure (X2), consent (C1), owners (W1-W4), decisions (D1), reconsideration (K11, K12). Never walk a pedigree, a succession chain or a release history in Python and only store the result.
2. Deterministic code decides. The duty engine (`app/engine/duty.py`) applies the tables of BLUEPRINT section 6 to graph rows. An LLM may only rephrase a draft from fixed slots (quote-checked) or route a question to a templated query. With no LLM key, templates are used and everything works.
3. Human approval before any outward action. A `Notice` exists only through L5, approved by a counsellor or medical director from the paired health-system graph. Recontact never sends email, letters or messages, and never contacts ClinVar or any real lab.
4. Append-only: runs, duties, notices, events, consents, tests, decisions, SCV versions. A changed answer is a new run; a replaced decision SUPERSEDES the old one; reopening is an Event.
5. Wording about real labs: never "stale", "wrong", "incorrect", "outdated", "error", "mistake". Say "updated its classification", "differs from the current expert-panel review". Wording about people: never diagnose or recommend treatment; every page with people shows the disclaimer from `docs/API.md`.
6. All people, families, consents, tests, clinicians, clinics, decisions and organisations are synthetic, carry `synthetic: true`, and are labelled "(fictional)". No personal data anywhere. NCBI requests carry only Variation IDs.
7. Organisations never read each other's graphs. Cross-tenant work moves only as `Handoff` nodes with the minimum payloads in BLUEPRINT 5.4; nothing about a BLOCKED, NOT_AT_RISK or letter-only person crosses. Dry runs on the fixed `demo` tenant write nothing.
8. Automatic relative routing only for genes with `inheritance: AD` and `review_always: false` in `data/genes.json`; everything else is NEEDS_REVIEW.
9. Do not write `eval/hard_cases.json` labels, `eval/reference_impl.py` or the held-out seeds. A human does (G108, G109). Stop and ask when you reach them.

## Engineering rules
- FalkorDB is the heart of the product (sponsor constraint): every answer and every memory write goes through FalkorDB; caches may hold raw NCBI HTTP responses only, never graph answers.
- Python 3.12, FastAPI, pydantic v2, httpx (async), `falkordb` client, `mcp>=1.10,<2` (mcp 2.x renamed FastMCP; do not upgrade). Next.js App Router with TypeScript for the web app.
- All Cypher lives in `services/api/app/graph/queries.py`, copied verbatim from `docs/queries.cypher` (block header regex `^// ([A-Z][A-Z0-9_]*): `), parameterised. No string-built Cypher with user input. If you need a new query, add it to `docs/queries.cypher` first, run it on FalkorDB, then copy it.
- Bounded variable-length paths only (`*0..3`, `*0..5`, `*1..4`). No unbounded `*`.
- Use `ro_query` for reads. Use MERGE on ids for idempotent writes; deterministic ids where FLOWS gives them.
- Every NCBI call goes through `app/clinvar/eutils.py` or `app/clinvar/ftp.py`: shared limiter (3 rps; 10 with `NCBI_API_KEY`), `tool=recontact`, `email=NCBI_EMAIL`, 10 s timeout, 3 retries on 429/5xx, clear 503 when NCBI is unavailable.
- FalkorDB container: data at `/var/lib/falkordb/data`; `REDIS_ARGS="--appendonly yes --requirepass ..."`; `FALKORDB_ARGS="MAX_QUEUED_QUERIES 25 TIMEOUT 5000 RESULTSET_SIZE 10000"` (the image default timeout is 1000 ms).
- Every endpoint validates input (API "Conventions"), returns typed errors, and logs with a request id. No secrets or person labels in logs.
- Tests: pytest against a FalkorDB service container; golden duty maps in `services/api/tests/golden/` must stay green. Add a regression test for every bug fixed.
- Do not commit secrets. `.env` is git-ignored; `.env.example` lists every variable.
- Git: conventional commits (`feat(api): ...`, `fix(web): ...`), one logical change per commit, stage only the files the task touched. Humans decide when to push.

## Definition of done for any task
- Build passes, tests pass, the deployed `/api/health` is green.
- The README section affected is updated (data model, queries, setup, tracks, AI disclosure, synthetic-data statement).
- The goal's Accept condition in `docs/GOALS.md` is met, its Verify step was run, and it is ticked with the date.
