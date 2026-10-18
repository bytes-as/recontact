# Recontact flows

Every flow the product runs, step by step (F0-F20). Each step names the component, the query (from `docs/queries.cypher`) or endpoint (from `docs/API.md`), and what happens on failure. If code behaves differently from this file, the code is wrong.

Conventions
- Graph names: `kb`; tenant `demo` = graphs `lab_demo` + `hs_demo`; sandbox `sbx_<8hex>` = graphs `sbx_<8hex>_lab` + `sbx_<8hex>_hs`.
- `now` is milliseconds since epoch (UTC) inside the graph; ISO-8601 in responses. Release ids are `YYYY-MM`.
- Ids are prefixed: `run_`, `duty_`, `task_`, `evt_`, `notice_`, `ho_`, `cons_`, `turn_`, `conv_`, `sbx_`. Ids of runs and duties are random (uuid4 hex, 12 chars); ids of events that must be idempotent are deterministic (given below).
- "Template text" means the deterministic drafts in `data/notice_templates.json`, used when no LLM key is set or the LLM output fails the quote check.
- All reads use `ro_query`; all writes use `query`; batches are 2000 rows.

---

## F0. Startup (API process boot)
1. Load config (`.env.example` lists all). Missing `ADMIN_TOKEN` -> refuse to start. Missing `NCBI_EMAIL` -> warning; live lookups disabled (`/api/health.ncbi = "disabled"`).
2. Connect to FalkorDB (`FALKORDB_HOST/PORT/PASSWORD`), 10 tries with 2 s backoff; if still down, start anyway and report `falkordb: "down"` (the web shows the maintenance banner).
3. Run SCHEMA_KB on `kb`, SCHEMA_LAB on every graph ending `_lab` or named `lab_demo`, SCHEMA_HS on every graph ending `_hs` or named `hs_demo` (`GRAPH.LIST`); ignore "already indexed".
4. If `kb` has no Release nodes (K14 empty) and `KB_AUTOLOAD=true`: start F2 in the background (does not block startup); `/api/health.kb.loading = {release, rows_done, rows_total}`. Endpoints that need kb return 503 `KB_LOADING` until the first BASE release and its variants are loaded.
5. If `lab_demo` or `hs_demo` does not exist and kb is loaded: run F6 (seed demo tenants).
6. Load `data/genes.json`, `data/normalisation.json`, `data/notice_templates.json`, `data/playbooks.json` into memory.
7. Start APScheduler: Watcher daily at `WATCH_CRON` (default 06:00 UTC, F15); handoff sweeper every 30 s (F8.6); sandbox cleanup every 15 min (F16.5).
8. Mount the MCP server at `/mcp` after all routes (F17). Serve.

## F1. Build-time extract (`scripts/extract_clinvar.py`, run once on a laptop; outputs committed)
1. Read `data/releases.json` and `data/genes.json`; scope genes = `kb_scope: true` (or `core: true` with `--scope core`, or the dev list with `--scope dev`).
2. **Variants**: stream `archive/variant_summary_2026-10.txt.gz` with `httpx.stream` + `gzip` line by line (never write the archive to disk unless `--keep`). Find the header line starting `#AlleleID`; map columns by name. Keep rows with `Assembly == "GRCh38"`; split `GeneSymbol` on `;`; keep only if exactly one symbol is a scope gene. Write `vcv, gene, name, agg_cls, agg_cls_raw, agg_review, agg_stars` to `data/clinvar/variants.tsv.gz` (one row per VariationID; if duplicated, keep the first).
3. **Submissions**: for each release in `releases.json` stream the archive; skip `##` lines and `#Name:` description lines; the header is the line starting `#VariationID`; map columns by name (the 2024-10 file has 15 columns). Keep rows with VariationID in the variant set; skip `ReviewStatus` in `skip_scv_rows_with_review_status`; split `SCV` on `.` into `acc`, `version` (int); normalise class, stars, date, submitter id. For the BASE release write all rows; for each DELTA release write rows whose `(acc, version, cls)` differs from the previous release's row for that acc, or whose acc is new, and write accs present in the previous release but absent now to `withdrawn_<release>.txt`.
4. `--eval`: compare 2024-10 and 2026-10 snapshots the same way and write `eval/transitions_2024-10_2026-10.tsv` (`acc, vcv, gene, submitter, from_cls, to_cls, from_version, to_version, kind`) and `eval/unchanged_2024-10_2026-10.tsv`.
5. Compute sha256 of every downloaded archive while streaming; write `data/clinvar/MANIFEST.json` (`file, bytes, sha256, rows_in, rows_out, scope, extracted_at`). Fail if the total size of `data/clinvar/` exceeds 60 MB (then use `--scope core`).
6. Failure: on a network error, retry the stream 3 times with 5/15/45 s backoff (HTTP range requests are not required); on persistent failure exit non-zero with the file name.

## F2. kb load (`app/clinvar/load.py`; `make kb-load`; `POST /api/admin/kb/load`)
1. K1 with all genes from `data/genes.json` (all 84, so K9 can show gene facts for every SF gene).
2. K2 with `variants.tsv.gz` in batches of 2000 (`release = "2026-10"`).
3. For each release in order (2026-08 BASE, 2026-09, 2026-10): if K14 already lists it and not `--force`, skip. Else K4 then K5 with the release rows in batches of 2000 (K4 before K5 for the same batch), then K6 with the withdrawn list, then K3 to record the Release node with `file_sha256` from MANIFEST (K3 last, so a crash mid-release re-runs it; K4 and K5 are idempotent).
4. Report progress to an in-memory status read by `/api/health`.
5. Failure: a FalkorDB error aborts the release; the next run resumes it. Query timeouts mean `TIMEOUT 5000` was not applied (check `FALKORDB_ARGS`) or the batch is too big (halve it, minimum 250).

## F3. The release diff (inside K5)
For every row: find the SCV's current version (`superseded_in IS NULL`). If none, create the version (first time seen). If its id differs from `<acc>.<version>|<cls>`, create the new version, set `superseded_in` on the old one, link `NEXT`, and if the normalised class differs create `ClassChange {id: <acc>@<release>, kind}` with kind computed in Cypher. Same id -> nothing. This is why the diff is a graph operation, and why re-running a release is a no-op.

## F4. Variant status (web `/variant/[vcv]`, `GET /api/variants/{vcv}`, MCP `variant_status`)
1. Validate `vcv` (integer 1-999999999) and `as_of` (`YYYY-MM`, default the latest Release).
2. K9 with `vcv`, `as_of`. If a row exists: K10 for history; mark each submission `differs_from_panel = true` when a submission with stars >= 3 exists and the actionable side differs (computed from the K9 rows, which come from FalkorDB). Respond `source: "kb"`.
3. If no row and live lookups are enabled: esummary + efetch (`is_variationid`) through `app/clinvar/eutils.py`; build the same response shape from the XML (classes normalised); write K13; respond `source: "live"`, with the note "This variant is outside the gene set loaded into our graph; showing ClinVar's current record. No release history or duty maps are available for it."
4. If no row and live lookups are disabled or NCBI fails: 404 `VARIANT_NOT_FOUND` with hint "We load ACMG secondary-findings genes only. Check the Variation ID on ClinVar." (or 503 `NCBI_UNAVAILABLE` if NCBI errored).
5. Response always includes `disclaimer` and `source_line` ("Source: ClinVar monthly archive <as_of> (NCBI, public)").

## F5. What changed (web `/`, `GET /api/releases/...`, MCP `submitter_changes`)
1. `GET /api/releases` (K14) fills the release picker (default the newest DELTA).
2. `GET /api/releases/{r}/submitters?limit=50` (K8) fills "Pick any lab", ordered by actionable changes.
3. `GET /api/releases/{r}/submitters/{id}/changes?limit=200` (K7) lists changes; each row links to `/variant/<vcv>` and, if a lab tenant reports the VCV (T4 on `lab_demo`), to `/duty/<change_id>`.
4. MCP `submitter_changes` accepts a name: resolve by case-insensitive match on K8 rows of that release, then K7.

## F6. Seed demo tenants (`scripts/seed_demo.py`; also F0.5)
1. If `data/demo_tenants/resolved.json` exists, use it. Else resolve per BLUEPRINT 11.1 using K8 (for submitters) and K7 (per submitter, kinds and genes; filter genes with `inheritance == "AD"` and `review_always == false` via K17), and write resolved.json.
2. Replace placeholders in `lab_demo.json` and `hs_demo.json` (`*_VCV` and `*_VERSION` as integers, others as strings).
3. `GRAPH.DELETE lab_demo` and `hs_demo` (ignore missing). SCHEMA_LAB / SCHEMA_HS.
4. lab_demo: P6 (org + playbooks from `data/playbooks.json`), P1 people, P2 parent_of, P3 reports, P4 tests, P5 jurisdictions + residence, P15 notices.
5. hs_demo: P6 (org + playbooks), P7 clinicians + clinics, P8 practiced_at, P9 handed_panel_to, P10 succeeded_by, P11 led_by, P12 patients, P13 members + medical director, P14 decisions.
6. For each of the three resolved changes: run F7 with `dry_run = false` as agent `seeder` (stores Runs and drafts, so the fixed tenant opens instantly). Then run F14 steps 1-3 for the Recon replay.
7. Failure: if kb is not loaded, abort with "load kb first (make kb-load)".

## F7. Duty map (Tracer; web `/duty/[changeId]`, `POST /api/duty-map`, MCP `duty_map`)
Input: `change_id`, `tenant` (default `demo`), `dry_run` (forced true for visitors on `demo`), optional token.
1. **Validate** ids (API "Conventions"). Resolve the tenant to its lab and hs graphs; unknown -> 404 `TENANT_NOT_FOUND`; expired sandbox -> 401 `SANDBOX_EXPIRED`.
2. **Change**: K17 on `kb` -> change, gene facts. Missing -> 404 `CHANGE_NOT_FOUND`.
3. **Does the tenant report it?** X1 on the lab graph. No rows -> respond with empty lists and `proof_none` (BLUEPRINT 6.8); write nothing.
4. **Exposure and consent**: C1 on the lab graph (only for UP_TO_ACTIONABLE; other kinds skip to step 5). For the A2 banner run A2 with the vcv.
5. **Memory**: L1 on the lab graph.
6. **Handoffs to the health system** (one hs graph per tenant).
   - **Real runs** (sandbox, seeder, Watcher; `dry_run = false`): for each carrier, L8 into the hs graph: `OWNER_LOOKUP`, id `ho_<run_id>_<pid>`, payload `{pid, clinician_id: Report.ordering_clinician, reply_graph: <lab graph>, change_id}`; and one `REOPEN_CHECK`, id `ho_<run_id>_reopen`, payload `{vcv, new_cls: to_cls, change_id, release, reply_graph}`. Then invoke the Steward worker for that hs graph in-process (F8) and poll L17 on the lab graph for `<id>:reply` every 100 ms for up to 5 s.
   - **Dry runs** (visitors on `demo`, MCP without a token): no Handoff nodes are written (fixed tenants stay read-only). The Tracer calls `steward.resolve_readonly(hs_graph, carriers, change)`, which runs only the read queries of F9 and F10 (W1-W4, D1) and returns the same result shapes. Same 5 s budget.
7. **Engine**: `build_duty_map(...)` (BLUEPRINT 6) -> carriers, relatives, decisions, baseline, counts. Owners not yet answered -> `PENDING_HANDOFF`.
8. **Persist (not dry run)**: L2 (Run + Duties, `engine_version` = git short sha), then the Drafter (F11.1) opens tasks. For an A2 multi-carrier family the engine has already merged; nothing extra.
9. **Respond** with `DutyMap` including `cypher` (exact X2, C1, W1, D1 text), `computed_ms` and the disclaimer. Record a Turn (L16) when the call came through MCP or a sandbox.
Failure handling: FalkorDB error -> 503 `GRAPH_UNAVAILABLE`; hs timeout -> degraded response (owners `PENDING_HANDOFF`, decisions `pending`), handoffs stay for the sweeper.

## F8. Steward (hs worker) and the handoff protocol
1. `process(hs_graph)`: L9 lists ready handoffs (OPEN, or CLAIMED with an expired lease), oldest first, limit 50.
2. For each: L10 claim with agent id `steward-<pid of process>-<n>`; no row -> someone else holds it; skip.
3. OWNER_LOOKUP: F9 for `clinician_id` and `pid`; result `{status, owner_id, owner, chain, steps, hops, dead_ends, routed_to}`.
4. REOPEN_CHECK: F10; result `{decisions:[...]}`.
5. NOTIFY_DIRECT: L19 creates a `DELIVER_NOTICE` task about the handoff (id `task_deliver_<notice_id>`), assigned to the carrier's or source carrier's owner (F9) and following the DELIVER_NOTICE playbook if present. No reply content beyond `{task_id}`.
6. Write the reply into the sender's graph: L8 on `reply_graph` with id `<id>:reply`, kind `REPLY`, `payload_json = result`; then L11 on the hs graph with `result_json`. Sweeper (every 30 s): (a) runs `process` for every hs graph; (b) for every graph, L9 finds handoffs with `attempts >= 5` that are not DONE: L21 marks them FAILED with `result_json = {"error": "max attempts"}` and L19 opens a HANDOFF_FAILED task (id `task_hofail_<handoff id>`, no assignee) in the same graph; (c) REPLY handoffs in lab graphs are completed by the Tracer that reads them (L10 + L11 as agent `tracer`); REPLY handoffs older than 10 minutes are completed by the sweeper the same way.
7. Failure: any exception inside a handoff leaves it CLAIMED; the lease expires after 60 s and it is retried.

## F9. Owner resolution (Steward)
1. W1 with `clinician_id` -> row: status RESOLVED.
2. Else W3 with `pid` -> row: status FALLBACK (chain = [ordering clinician, "clinician of record"]).
3. Else: status ORPHAN; W2 dead ends; W4 medical director as `routed_to`; unless the run is a dry run, L19 creates an ORPHAN_DUTY task about the OWNER_LOOKUP handoff (idempotent id `task_orphan_<change_id>_<pid>`), assigned to the medical director.
4. Relatives: owner = owner of the chosen derivation's source carrier (engine side).

## F10. Decisions reopen (Steward)
1. D1 with `vcv`, `new_cls`.
2. For each row, resolve the owner: if `owner_active`, RESOLVED; else F9 from `owner_id`.
3. If not a dry run: D2 with `event_id = evt_reopen_<decision_id>_<change_id>`, reason "rested on <cls_at_time> (<rested_on_release>); now <new_cls> in ClinVar <release>"; then L18 creates a REOPENED_DECISION task about the decision (id `task_reopen_<decision_id>_<change_id>`), assigned to the resolved owner (or the medical director when ORPHAN).
4. Approve a replacement: `POST /api/tenants/{t}/decisions/{id}/replace` -> D3 (new id `dec_<12 hex>`, event `evt_sup_<old id>`).

## F11. Drafts, approvals, notices (Drafter, humans)
1. For each duty of a written Run: DIRECT_NOTICE/VIA_FAMILY_LETTER -> draft from `notice_templates.json` (UPGRADE, NEW_RISK_DIRECT, NEW_RISK_LETTER (addressed to the source carrier), CORRECTION, VUS_RESOLVED); slots from the change and the owner; optional LLM rephrase (F11.2); L3 with kind APPROVE_NOTICE. NEEDS_REVIEW -> L3 kind REVIEW_NEEDS_REVIEW (one per duty). BLOCKED -> ACK_BLOCKED. WITHIN_TIER carriers -> AMEND_REPORT. NOT_AT_RISK, NO_ACTION, ALREADY_NOTIFIED -> no task.
2. LLM rephrase (only if `OPENROUTER_API_KEY` and budget): prompt = the template text and the slot JSON; instruction "rephrase for warmth and clarity; keep every slot value verbatim; add no facts". Check: every slot value present verbatim; no class word other than the from/to class words; no forbidden phrase; length under 1,500 characters. Fail or 6 s timeout -> template, `draft_source = "template"`.
3. Claim (L4) by a human (`person_id` must be a Clinician in the paired hs graph with role `genetic_counsellor` or `medical_director`; else 403 `NOT_A_COUNSELLOR`). Approve (L5, notice id `notice_<12 hex>`, event `evt_<12 hex>`): creates the Notice; L5 returns no row for BLOCKED/NEEDS_REVIEW duties -> 409 `TASK_NOT_APPROVABLE`. Reject (L6, `event_kind = REJECTED`, reason required). Acknowledge (L6, `event_kind = ACKNOWLEDGED`).
4. After approval of a DIRECT notice: NOTIFY_DIRECT handoff into the hs graph (payload `{pid, vcv, notice_type, notice_id}`, no source identity), processed by F8.
5. Nothing is ever sent outside the system. The UI says "Approved. A delivery task was created for <owner>."

## F12. Memory rules (applied by the engine from L1)
1. Same vcv, Notice `cls == to_cls` -> ALREADY_NOTIFIED (no new task).
2. DOWN or VUS_RESOLVED and an earlier Notice with a different class -> CORRECTION through the earlier channel if still permitted (BLUEPRINT 6.4).
3. `contact_pref = not_to_know` always blocks drafting for that person (C1 failed condition), across releases.
4. Seeded historical notices (`seeded: true`) count like approved notices.

## F13. Consent and test changes (sandbox or admin)
1. `POST /api/tenants/{t}/people/{pid}/consent {kind, value, recorded_by}`: validate `kind` in family_share (none, letter, direct), contact_pref (ok, no_contact, not_to_know), recontact (yes, no); C2 with id `cons_<12 hex>`. Response: the new current values and a hint "Re-run the duty map to see the effect."
2. `POST /api/tenants/{t}/people/{pid}/tests {vcv, result, date}`: P4 with one row (id `test_<12 hex>`).
3. The web duty page offers "Recompute" (F7, dry run in sandbox unless the user clicks "Save as run").

## F14. Reconsideration loop (Curator)
1. As of release R (default the BASE release), for the tenant's `mirrors_submitter` (or `recon_submitter` from resolved.json): K11 (gene = null; on timeout, iterate genes in scope and merge).
2. For each row: L12 with `recon_id = <scv>@<R>`, then L20 opens a RECONSIDER_SUBMISSION task about it (id `task_recon_<scv>_<R>`; draft title "Reconsideration item: <gene> VCV <vcv>"; body "This submission's classification (<class words>) differs from the current expert-panel review (<panel class words>, <panel>). Route to the curation team."). Both are idempotent.
3. Closure, for each later release R2 in order: L14 open items -> K12 with `as_of = R2` and `items = [{recon_id, scv, opened_cls, opened_version}]` -> for rows with `class_changed` -> L13 outcome CLASS_CHANGED, `event_id = evt_recon_<recon_id>_<R2>`; rows with only `version_changed` -> L13 outcome VERSION_UPDATED_SAME_CLASS; items for which K12 returns no row (the SCV was withdrawn by R2) -> L13 outcome WITHDRAWN; others stay open.
4. `GET /api/loop/replay` returns `{submitter, opened: {release, count, items}, closed: [{release, count, items}], still_open}`.
5. Copy (UI `/loop`): "These closures come from ClinVar's own monthly archives. We do not claim our reminder caused them: we remember the open question, route it, and close it with a citation when the evidence appears."

## F15. Watcher (monthly archive ingest)
1. Daily at `WATCH_CRON`: GET `https://ftp.ncbi.nlm.nih.gov/pub/clinvar/tab_delimited/archive/` (HTML listing); parse `submission_summary_(\d{4}-\d{2})\.txt\.gz` names; new = newer than the newest Release in K14.
2. For a new month M: stream the file (F1.3 parsing) keeping only VariationIDs present in kb (load the VCV set with a paged read of Variant ids); collect accs; K16 in batches to get current `(version, cls)`; rows that differ or are new -> delta; accs in kb's current set for those variants but absent from M -> withdrawn.
3. Load as DELTA: K4, K5, K6, K3 (`kind = DELTA`, sha256 computed while streaming).
4. For each lab tenant (registry): T4 -> VCVs reported; for each new ClassChange in M (K7-style read by release, all submitters, filtered to the tenant's mirrored submitter) whose vcv is reported: F7 with `dry_run = false`, agent `watcher`.
5. Curator closure (F14.3) with R2 = M.
6. Manual trigger: `POST /api/admin/watch/run {month?}`. Replay for the video: `POST /api/admin/watch/replay {release}` (G104).
7. Failure: download errors retry 3 times; a partial ingest aborts before K3 (the next run retries); NCBI listing unreachable -> log and try tomorrow.

## F16. Sandbox and seed-a-family
1. `POST /api/sandbox {template: "demo"}`: 3 per hour per IP; at most 50 live (oldest deleted first).
2. Name `sbx_<8 hex>`; `GRAPH.COPY lab_demo sbx_<id>_lab` and `GRAPH.COPY hs_demo sbx_<id>_hs` (fails if the destination exists: regenerate once).
3. Token = 32 random bytes urlsafe; keep `{tenant, sha256(token), expires_at}` in memory (and lose sandboxes on restart: acceptable; the web shows "Your sandbox expired"). Never store the token in a graph.
4. Return `{tenant, token, expires_at}`; the web stores the token in sessionStorage and sends `X-Tenant-Token`.
5. Cleanup every 15 min: `GRAPH.DELETE` both graphs of expired sandboxes.
6. Seed a family: `POST /api/tenants/{t}/families {change_id, template}` (sandbox only): K17 for the change; run the generator (G107) with `seed = int(sha256(t + change_id)[:8], 16)`, `families = 1`, template `cousin` (forces the Family A structure) or `simple`; load with P1-P5 (lab) and P7-P14 subsets (hs: new clinicians and decisions only); return `{family, duty_map_url}`.

## F17. MCP
1. Client connects to `https://<api>/mcp` (streamable HTTP, stateless). Tools: `variant_status`, `duty_map`, `explain_person`, `owner_today`, `submitter_changes`, `reconsideration_queue` with schemas from `docs/API.md`.
2. `variant_status` text block: first line `VARIANT VCV<9 digits> <gene> <name>: aggregate <class words> (<review status>) as of ClinVar <release>.`; then up to 10 lines `- <submitter>: <class words> (<stars> stars, evaluated <date>, since <release>)`, flagging `[differs from the current expert-panel review]` neutrally; then `Recent changes: ...`; then `Do not quote one submission's classification as the variant's classification.`; then the disclaimer. Structured content: the full response.
3. `duty_map` calls F7 (dry run unless a sandbox token is given). Text block: `DUTY MAP <change_id> for <tenant>: <n> direct notices, <n> family letters, <n> blocked (no permitted path), <n> not at risk (no inheritance path), <n> need review, <n> decisions reopened.`; then carriers and relatives with verdicts and owners by label, except BLOCKED and NOT_AT_RISK people, who appear as counts only unless a token is given; then `Details: <web url>/duty/<change_id>`; then the disclaimer.
4. Rate limit 30 calls per minute per MCP session; errors return the API code in the text (`ERROR CHANGE_NOT_FOUND: ...`).
5. Every call with a tenant writes a Turn (L16).

## F18. Eval
1. `eval/selected_transitions.json`, `eval/hard_cases.json`, `eval/reference_impl.py`, `eval/labels.sha256`, `eval/heldout_seeds.sha256` committed before the engine (G108, G109).
2. `python eval/run_eval.py --api <url> --admin-token <t> [--heldout <seeds.json>]`:
   - **Scratch kb**: the eval never touches `kb`. For each case or transition it calls `POST /api/admin/eval/load-case`, which deletes and recreates graph `kb_eval` with SCHEMA_KB and then K1 (the case's gene), K2 (one variant), and K4 + K5 twice: release `2024-10` (BASE) with the SCV at `from_cls`, then release `2026-10` (DELTA) with the SCV at `to_cls` and version + 1 (for unchanged controls the DELTA row has the same class, so K5 creates no ClassChange: that is the control's test). Hard cases use acc `SCV9<case number, 8 digits>` and vcv `900000000 + case number`; real transitions use their real acc, vcv and gene.
   - **Scratch tenant**: the same endpoint deletes and recreates `sbx_e0e0e0e0_lab` and `sbx_e0e0e0e0_hs` from the case or world JSON with the P queries (F6 steps 4-5).
   - **Run**: `POST /api/duty-map` with `tenant = sbx_e0e0e0e0`, `dry_run = false` and the admin-only field `kb_graph = "kb_eval"`; compare per person with the human labels (hard cases) or with `reference_impl.py` output on the same JSON (worlds).
3. Metrics per BLUEPRINT 13 step 6, plus per-case rows; write `eval/report.json`. `GET /api/eval` serves it; `/eval` renders it with both hashes.

## F19. Deploy
1. Railway `falkordb`: image `falkordb/falkordb:latest`, volume `/var/lib/falkordb/data`, `REDIS_ARGS="--appendonly yes --requirepass ${FALKORDB_PASSWORD}"`, `FALKORDB_ARGS="MAX_QUEUED_QUERIES 25 TIMEOUT 5000 RESULTSET_SIZE 10000"`, private networking only, memory 2 GB.
2. Railway `api`: `services/api/Dockerfile` (copies `data/` and `docs/queries.cypher` into the image); env from `.env.example`; health check `/api/health`; one replica.
3. First boot: `KB_AUTOLOAD=true` loads kb from the committed extracts (F2), then seeds tenants (F6). Watch `/api/health.kb.loading`.
4. Vercel: project root `apps/web`; env `NEXT_PUBLIC_API_URL`; production branch `main`.
5. After deploy: `scripts/smoke.sh <api> <web>`.

## F20. Failure modes (applies everywhere)
| Failure | Behaviour |
|---|---|
| FalkorDB down | `/api/health` `falkordb: "down"`; endpoints 503 `GRAPH_UNAVAILABLE`; web maintenance banner |
| kb still loading | 503 `KB_LOADING` with `retry_after_s: 60`; web shows "Loading ClinVar into the graph: <n>%" |
| NCBI down or rate-limited | live lookups 503 `NCBI_UNAVAILABLE` with `retry_after_s`; kb answers unaffected; Watcher retries tomorrow |
| hs graph slow or Steward crashed | duty map degraded (`PENDING_HANDOFF`); sweeper retries; after 5 attempts HANDOFF_FAILED task |
| Unknown change or tenant | 404 `CHANGE_NOT_FOUND` / `TENANT_NOT_FOUND` |
| Variant outside loaded genes | live record (F4.3) or 404 `VARIANT_NOT_FOUND` |
| LLM error | template text; never blocks a draft |
| Concurrent claims | exactly one winner (lease); losers get 409 `LEASE_HELD` |
| Approving a non-approvable duty | 409 `TASK_NOT_APPROVABLE` |
| Sandbox expired | 401 `SANDBOX_EXPIRED` with "create a new sandbox" action |
| Visitor writes to `demo` | 403 `READ_ONLY_TENANT` |
