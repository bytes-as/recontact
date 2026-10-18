# Recontact task board

This is the hour-by-hour summary. The complete, numbered work list with acceptance tests is `docs/GOALS.md`; Cursor works from GOALS.md and ticks both.

Hour 0 = the moment the build starts. A = backend and graph. B = frontend, eval labels and reference implementation, video. Tick boxes as you go. Do not start a later block while an earlier block's acceptance criteria fail (except the B-side eval work, which runs in parallel by design).

## Block 0 (hour 0-1): scaffold and deploy "hello" (G001-G019)
- [ ] A: repo layout (BLUEPRINT 14); `docker compose up` starts FalkorDB (TIMEOUT 5000) + API; schema bootstrap.
- [ ] A: Railway `falkordb` (volume `/var/lib/falkordb/data`, requirepass, private, 2 GB) and `api`; `/api/health` green.
- [ ] B: Vercel project for `apps/web`; layout, nav, footer disclaimer, health dot.
- [ ] A: `queries.py` generated from `docs/queries.cypher` with the sync test (81 blocks).
- **Accept:** both URLs live; health green from the deployed web app.

## Block 1 (hour 1-5): ClinVar into FalkorDB (G020-G039) and the frozen eval protocol (G108, G109)
- [ ] A: start `scripts/extract_clinvar.py` early (streams about 1.6 GB; run variants, then scv, then --eval); meanwhile build the loader against `KB_SCOPE=dev`.
- [ ] A: kb loader (K1-K6), resumable, idempotent; endpoints for releases, submitters, changes, variants; E-utilities client with `is_variationid`.
- [ ] A: load `sf` scope locally, then on Railway (watch memory); record counts in OPEN_POINTS.
- [ ] B: `/` and `/variant/[vcv]` pages.
- [ ] B: **before any engine code**: `eval/select_transitions.py` -> `selected_transitions.json`; complete `eval/hard_cases.json` with labels from the skeleton; write `eval/reference_impl.py`; commit `eval/labels.sha256` and `eval/heldout_seeds.sha256`.
- [ ] B: check `data/genes.json` against the ACMG SF v3.3 table (G024).
- **Accept:** the public URL lists a real submitter's class changes for 2026-10 and shows VCV 51579's submissions; label hashes committed.

## Block 2 (hour 5-8): the core duty map (G040-G059; protect forever)
- [ ] A: `scripts/seed_demo.py` (resolver, resolved.json, P queries); exposure (X1, X2), consent (C1), degree rule; duty engine tables; `POST /api/duty-map`; no-report proof; FalkorDB-down test.
- [ ] A: golden tests for Family A and D, gene rule, needs-review class, safety invariant.
- [ ] B: `/duty/[changeId]` with pedigree, derivation edges, verdict table, proof drawer, baseline panel.
- **Accept (hour 8 milestone):** on the public URL a stranger picks the mirrored submitter, opens the UP change and sees Mila's direct notice through Vera, Leo's BLOCKED proof and the pruned maternal side, in under 2 s.

## Block 3 (hour 8-13): health system, owners, decisions, handoffs (G060-G079)
- [ ] A: hs_demo; owner service (W1-W4); handoff protocol with leases and the sweeper; decisions (D1, D2, D3, D4, D5); A1-A3 endpoints; concurrency tests.
- [ ] B: owner chains, ORPHAN card and reopened decisions on `/duty`; `/org` page.
- **Accept:** UP map shows owners (one ORPHAN routed to the medical director) and the reopened decision; DOWN map shows two corrections and two reopened decisions.

## Block 4 (hour 13-16): approvals, memory, MCP (G080-G099)
- [ ] A: Drafter, approvals (counsellor check), NOTIFY_DIRECT, memory rules, consent and test endpoints, conversation turns, MCP server and tools.
- [ ] B: `/queue`, `/mcp`; record Claude Code calling `variant_status` and `duty_map`.
- **Accept:** approve Mila's notice in a sandbox; re-run shows ALREADY_NOTIFIED; MCP works from Claude Code.

## Block 5 (hour 16-19): loop, Watcher, sandbox, eval (G100-G119)
- [ ] A: Curator (K11 -> Recon, K12 closure), Watcher with a fake archive test, sandbox, seed-a-family, generator, prewarmed runs.
- [ ] B: `eval/run_eval.py`, `/eval`, `/loop`.
- **Accept:** all three demo shots in BLUEPRINT section 1 run end to end on the deployed site; safety count 0.

## Block 6 (hour 19-21): hardening (G120-G134)
- [ ] Rate limits, validation, mobile, error and empty states, security, export/restore, runbook, synthetic-data audit, load test.
- **Accept:** a cold visitor on a phone can open a duty map; a judge's own VCV gives a status page or a clear "outside the loaded gene set".

## Block 7 (hour 21-23): submission assets (G135-G146)
- [ ] README (what, live URL, video, MCP command, setup, data model, queries and algorithms, tracks, eval hashes, AI disclosure, synthetic-data statement, limitations), video, blog draft.
- **Accept:** BLUEPRINT section 19 fully ticked.

## Block 8 (hour 23-24): buffer and submit
- [ ] Submit with all tracks named. Re-check the live URL from a private window.

## Verification log (pre-filled from the spec author's checks on 18 Oct 2026)
- FalkorDB `falkordb/falkordb:latest` module 42201; default TIMEOUT 1000 (set 5000); all 81 query blocks execute; 52 behavioural checks pass.
- `algo.BFS(node, depth, 'TYPE')` follows outgoing edges only; `algo.WCC` with a config map works; `GRAPH.COPY` fails if the destination exists.
- MCP mount: reuse ModelBrain's verified pattern (mcp 1.30.0; pin `mcp>=1.10,<2`).
- ClinVar: monthly archives exist for 2026-08/09/10 and 2024-10; headers recorded in BLUEPRINT 4.1; efetch needs `is_variationid`.

## Questions for the owner
- No GitHub repo for Recontact yet (bytes-as/reconstruct is Landfall). Need a public repo name before G009 and G135. Not pushing until you say so.
- Railway CLI is logged in as mnkreddy7833@gmail.com. Confirm that account, a project name, and a spend limit before G015/G120. Expected cost about $10-25 for the judging window. Vercel CLI is not installed and not logged in.
- NCBI_EMAIL (any address you control) is required for live variant lookups. NCBI_API_KEY is optional (free, raises the limit from 3 to 10 requests/second). OpenRouter key and LLM_MODEL are optional; templates work with neither.
- Human-only, and the engine must not be merged before they land: G024 (check data/genes.json against ACMG SF v3.3), G108 and G109 (eval labels, reference implementation, held-out seed hashes).
- Ports 3000, 6379 and 8000 are already taken by ModelBrain and a local Redis, so the spec compose stack cannot start beside it. Recontact's FalkorDB for tests is on host port 6391 (browser 3012).
- Still needed from a person later, not a key: 3-minute video (G139), submission form (G141), team agreement on the MIT licence (G135).
