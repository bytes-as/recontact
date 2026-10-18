# Recontact API contract

Base URL: `https://<api-host>` (Railway). All JSON. Times are ISO-8601 UTC strings in responses (epoch ms inside the graph); release ids are `YYYY-MM`. This file is the contract between `services/api`, `apps/web`, the MCP server and the eval runner; change it here first.

## Conventions
- **Tenants** in paths: `demo` (graphs `lab_demo` + `hs_demo`, read-only for visitors) or `sbx_<8 hex>` (graphs `sbx_<8hex>_lab` + `sbx_<8hex>_hs`, writable with the sandbox token).
- **Auth headers**: `X-Tenant-Token: <sandbox token>` or `Authorization: Bearer <ADMIN_TOKEN>`. Tokens are compared in constant time; only their sha256 is kept in memory.
- **Request id**: every response has `X-Request-Id`; log lines carry it.
- **Validation** (422 `INVALID_INPUT` otherwise): `vcv` integer 1-999999999; `release`/`as_of` `^\d{4}-\d{2}$`; `change_id` `^SCV\d{9}@\d{4}-\d{2}$`; `submitter_id` `^[a-z0-9-]{1,80}$`; `tenant` `^(demo|sbx_[0-9a-f]{8})$`; `pid` and clinician ids `^[A-Za-z0-9-]{1,40}$`; `limit` 1-500.
- **Error envelope** (all non-2xx):
```json
{ "error": { "code": "CHANGE_NOT_FOUND", "message": "No class change SCV000000000@2026-10 in the loaded ClinVar releases.", "hint": "Pick a change from the list on the home page.", "retry_after_s": null } }
```
- **Error codes**: `INVALID_INPUT` 422, `VARIANT_NOT_FOUND` 404, `CHANGE_NOT_FOUND` 404, `TENANT_NOT_FOUND` 404, `TASK_NOT_FOUND` 404, `UNAUTHORIZED` 401, `SANDBOX_EXPIRED` 401, `READ_ONLY_TENANT` 403, `NOT_A_COUNSELLOR` 403, `LEASE_HELD` 409, `TASK_NOT_APPROVABLE` 409, `RATE_LIMITED` 429, `GRAPH_UNAVAILABLE` 503, `KB_LOADING` 503, `NCBI_UNAVAILABLE` 503, `INTERNAL` 500.
- **Rate limits** (per IP): duty-map 30/min, variants 60/min, sandbox 3/h, families 10/h, everything else 120/min. 429 includes `retry_after_s`.
- **Disclaimer** (exact string, field `disclaimer` on every variant, change, duty-map, trace and org response): `"Decision support for genetic counsellors. Not medical advice. Nothing is sent without a named counsellor's approval. People and organisations shown are fictional; ClinVar data are real."`

## Shared types
```ts
type Cls = "P" | "LP" | "VUS" | "LB" | "B" | "CONFLICTING" | "OTHER"
type ChangeKind = "UP_TO_ACTIONABLE" | "DOWN_FROM_ACTIONABLE" | "VUS_RESOLVED_BENIGN" | "BENIGN_TO_VUS" | "WITHIN_TIER" | "NEEDS_REVIEW_CLASS"
type Change = {
  change_id: string; release: string; kind: ChangeKind; vcv: number; variant: string; gene: string
  scv: string; submitter_id: string; submitter: string
  from_cls: Cls; to_cls: Cls; from_version: number; to_version: number; submitter_evaluated: string | null
  inheritance: "AD" | "AR" | "XL"; review_always: boolean; review_reason: string | null
}
type Submission = { scv: string; version: number; cls: Cls; cls_raw: string; stars: number; review: string
  evaluated: string | null; since_release: string; submitter: string; submitter_id: string; differs_from_panel: boolean }
type VariantStatus = {
  vcv: number; variant: string; gene: string | null; inheritance: string | null; review_always: boolean | null
  aggregate: { cls: Cls; cls_raw: string; review: string; stars: number; release: string }
  as_of: string; submissions: Submission[]
  history: { change_id: string; release: string; scv: string; submitter: string; from_cls: Cls; to_cls: Cls; kind: ChangeKind; submitter_evaluated: string | null }[]
  panel: { scv: string; submitter: string; cls: Cls; evaluated: string | null } | null
  source: "kb" | "live"; source_line: string; note: string | null; disclaimer: string
}
type Verdict = "DIRECT_NOTICE" | "VIA_FAMILY_LETTER" | "BLOCKED_NO_PERMITTED_PATH" | "NOT_AT_RISK_NO_INHERITANCE_PATH"
             | "NEEDS_REVIEW" | "NO_ACTION" | "ALREADY_NOTIFIED"
type NoticeType = "UPGRADE" | "NEW_RISK" | "CORRECTION" | "VUS_RESOLVED" | "RECORD_UPDATE" | "NONE"
type Owner = {
  status: "RESOLVED" | "FALLBACK" | "ORPHAN" | "PENDING_HANDOFF"
  owner_id: string | null; owner: string | null; role: string | null; hops: number | null
  chain: string[]; steps: string[]                        // W1: node names and "TYPE date" steps
  dead_ends: { kind: "Clinician" | "Clinic"; name: string; left_at: string | null; closed_at: string | null }[]
  routed_to: { owner_id: string; owner: string } | null   // medical director when ORPHAN
}
type Derivation = { source_pid: string; source_label: string; common_ancestor: string; up: number; down: number
  path: string[]; pruned_by: string[]; open: boolean; direct_ok: boolean; letter_ok: boolean; needs_review: boolean
  failed: string[]; jurisdiction: string }
type DutyRow = {
  duty_id: string | null; pid: string; label: string; role: "CARRIER" | "RELATIVE"
  verdict: Verdict; notice_type: NoticeType; channel: "DIRECT" | "LETTER" | null
  degree: number | null; nominal_prior: number | null; source_pid: string | null
  owner: Owner | null; reason: string; failed: string[]; derivations: Derivation[]; task_id: string | null
}
type ReopenedDecision = { decision_id: string; pid: string; kind: string; summary: string; made_at: string
  rested_on_cls: Cls; rested_on_release: string; rested_on_scv: string; owner: Owner; approved_by: string | null
  sources: string[]; event_id: string | null; task_id: string | null }
type DutyMap = {
  change: Change; tenant: string; run_id: string | null; dry_run: boolean
  gene_rule: { inheritance: string; review_always: boolean; pruning_valid: boolean; reason: string | null }
  carriers: DutyRow[]; relatives: DutyRow[]; decisions: ReopenedDecision[] | "pending"
  multi_carrier_families: { component_id: number; carriers: string[] }[]
  baseline: { letters: { to: string; clinician_id: string; active: boolean | null }[]; relatives_reached: 0; decisions_reopened: 0 }
  counts: { direct: number; letter: number; blocked: number; not_at_risk: number; needs_review: number; no_action: number; already_notified: number; decisions: number }
  proof_none: string | null
  handoffs: { mode: "handoff" | "readonly"; owner_lookup: "done" | "pending" | "failed"; reopen_check: "done" | "pending" | "failed" }
  cypher: { x2: string; c1: string; w1: string; d1: string }
  disclaimer: string; computed_ms: number
}
type Task = { task_id: string; kind: string; state: "OPEN" | "CLAIMED" | "AWAITING_APPROVAL" | "DONE"; created_at: string
  agent: string; draft_title: string | null; draft_body: string | null; about_kind: string; about_id: string
  verdict: string | null; playbook: string[] | null; handed_off_from: string | null; graph: "lab" | "hs" }
```

## Endpoints

### Health and admin
| Method | Path | Auth | Response |
|---|---|---|---|
| GET | `/api/health` | none | `{ok, falkordb:"up"|"down", graphs:string[], kb:{releases:[{id, kind, rows, file_sha256}], variants, scvs, loading:{release, rows_done, rows_total}|null, scope:"sf"|"core"|"dev"}, ncbi:"ok"|"degraded"|"disabled", version}` |
| POST | `/api/admin/kb/load` | admin | `{started: true}`; body `{force?: boolean}` (F2) |
| POST | `/api/admin/watch/run` | admin | `{month, new_release: boolean, class_changes, runs:{tenant: count}}` (F15) |
| POST | `/api/admin/watch/replay` | admin | `{release, class_changes}` (G104, graph `kb_replay`) |
| POST | `/api/admin/eval/load-case` | admin | body `{case | world, change}` -> `{kb_graph:"kb_eval", tenant:"sbx_e0e0e0e0", change_id}` (F18) |
| GET | `/api/admin/handoffs` | admin | `[{graph, handoff_id, kind, state, attempts}]` |

### ClinVar (graph `kb`, read-only)
| Method | Path | Query | Response |
|---|---|---|---|
| GET | `/api/releases` | | `[{release, kind, rows, loaded_at}]` (K14) |
| GET | `/api/releases/{release}/summary` | | `[{kind, pruning_valid, changes}]` (K15) |
| GET | `/api/releases/{release}/submitters` | `limit=50` | `[{submitter_id, submitter, changes, actionable_changes}]` (K8) |
| GET | `/api/releases/{release}/submitters/{submitter_id}/changes` | `limit=200` | `{submitter, release, changes: Change[] (K7), reported_by_demo: number[] (vcvs in T4 of lab_demo)}` |
| GET | `/api/releases/{release}/submitters/{submitter_id}/differs-from-panel` | `gene?`, `limit=200` | `[{vcv, gene, scv, version, submission_cls, submission_evaluated, panel_cls, panel, panel_scv, panel_evaluated}]` (K11) with `wording: "This submission's classification differs from the current expert-panel review."` |
| GET | `/api/variants/{vcv}` | `as_of?` | `VariantStatus` (K9, K10; or live + K13) |
| GET | `/api/changes/{change_id}` | | `Change` (K17) |

### Duty maps (lab + hs graphs)
| Method | Path | Auth | Body / query | Response |
|---|---|---|---|---|
| POST | `/api/duty-map` | none for dry runs on `demo`; token/admin otherwise | `{change_id, tenant?="demo", dry_run?=true, kb_graph?: "kb_eval" (admin only)}` | `DutyMap` |
| GET | `/api/tenants/{t}/runs` | read: none for `demo` | `limit=20` | `[{run_id, change_id, vcv, release, kind, at, duties, notices}]` (T2) |
| GET | `/api/tenants/{t}/runs/{run_id}` | same | | `DutyMap` rebuilt from T5 rows and stored `proof_json` (no recomputation) |
| GET | `/api/tenants/{t}/duties/{duty_id}/trace` | same | | `{run, change_id, person, verdict, notice_type, channel, failed, proof, owner, task:{id, state, events:[{kind, at, by}]}, notice_id, consent_history:[{kind, value, at, recorded_by}] (C3)}` (T1) |

### Tenants and memory
| Method | Path | Auth | Body | Response |
|---|---|---|---|---|
| GET | `/api/tenants` | none | | `[{tenant, lab:{name, mirrors_submitter}, hs:{name}, kind:"fixed"|"sandbox", expires_at?}]` (fixed + caller's sandbox) |
| POST | `/api/sandbox` | none | `{template:"demo"}` | `{tenant, token, expires_at}` (F16) |
| GET | `/api/tenants/{t}/overview` | read | | `{lab:{name, mirrors_submitter, people, families, reports, synthetic_people} (T3), reported_variants:[{vcv, reports, scvs}] (T4), families:[{component_id, size, sample}] (A1)}` |
| GET | `/api/tenants/{t}/families/{family}` | read | | `{people:[...X4 rows], tests:[...X3 rows for each reported vcv]}` |
| POST | `/api/tenants/{t}/people/{pid}/consent` | token/admin | `{kind:"family_share"|"contact_pref"|"recontact", value, recorded_by}` | `{pid, family_share, contact_pref, recontact_ok}` (C2) |
| POST | `/api/tenants/{t}/people/{pid}/tests` | token/admin | `{vcv, result:"POS"|"NEG", date}` | `{tests: 1}` (P4) |
| POST | `/api/tenants/{t}/families` | token | `{change_id, template:"cousin"|"simple"}` | `{family, duty_map_url}` (F16.6) |
| GET | `/api/tenants/{t}/events` | read | `limit=50` | `[{graph, kind, at, by, reason, on_kind, on_id}]` newest first |
| GET | `/api/tenants/{t}/conversations` | token/admin | | `[{conversation_id, channel, started_at, turns:[{tool, summary, at, run_id}]}]` |

### Tasks and approvals
| Method | Path | Auth | Body | Response |
|---|---|---|---|---|
| GET | `/api/tenants/{t}/tasks` | read | `states=OPEN,CLAIMED,AWAITING_APPROVAL&graph=lab|hs|all&limit=50` | `Task[]` (L7 on each graph) |
| POST | `/api/tenants/{t}/tasks/{task_id}/claim` | token/admin | `{person_id}` | `{claimed: true}` or 409 `LEASE_HELD` (L4) |
| POST | `/api/tenants/{t}/tasks/{task_id}/approve` | token/admin | `{person_id, edited_body?}` | `{notice_id, delivery_task_id}` (L5 + NOTIFY_DIRECT) or 409 `TASK_NOT_APPROVABLE`; `person_id` must be a counsellor or medical director in the paired hs graph (403 `NOT_A_COUNSELLOR`) |
| POST | `/api/tenants/{t}/tasks/{task_id}/reject` | token/admin | `{person_id, reason, kind?:"REJECTED"|"ACKNOWLEDGED"}` | `{ok: true}` (L6) |

`edited_body` replaces the draft text before L5 runs (the edited text is quote-checked like an LLM draft; failures return 422 with the failing rule).

### Health-system brain (hs graph)
| Method | Path | Auth | Query / body | Response |
|---|---|---|---|---|
| GET | `/api/tenants/{t}/roster` | read | | W5 rows |
| GET | `/api/tenants/{t}/owner` | read | `clinician_id` and/or `pid` | `Owner` (W1 -> W3 -> W2/W4) |
| GET | `/api/tenants/{t}/follow-up` | read | | `[{pid, label, owner: Owner}]` for every carrier of a reported variant |
| GET | `/api/tenants/{t}/decisions/reopened` | read | | D5 rows |
| GET | `/api/tenants/{t}/decisions/stale` | read | `cutoff_release` | D4 rows |
| GET | `/api/tenants/{t}/decisions/{decision_id}/trace` | read | | `{decision, rested_on:{cls, release, scv, clinvar_url}, owner: Owner, approved_by, sources, events}` |
| POST | `/api/tenants/{t}/decisions/{decision_id}/replace` | token/admin | `{approver_id, kind, summary}` | `{decision_id}` (D3) |

### Reconsideration loop
| Method | Path | Auth | Response |
|---|---|---|---|
| GET | `/api/tenants/{t}/recon` | read | L14 rows + closed items with their RECON_CLOSED events |
| POST | `/api/tenants/{t}/recon/refresh` | token/admin | body `{as_of}` -> `{opened, closed}` (F14) |
| GET | `/api/loop/replay` | none | `{submitter, opened:{release, count, items}, closed:[{release, count, items}], still_open, note}` (F14.4) |

### Algorithms (also used by MCP tools and the duty page)
| Method | Path | Response |
|---|---|---|
| GET | `/api/tenants/{t}/algo/families` | `[{component_id, size, sample}]` (A1, WCC) |
| GET | `/api/tenants/{t}/algo/multi-carrier?vcv=` | `[{component_id, carriers}]` (A2, WCC) |
| GET | `/api/tenants/{t}/algo/cascade?pid=` | `{descendants: string[]}` (A3, BFS) |

### Eval
| Method | Path | Response |
|---|---|---|
| GET | `/api/eval` | `eval/report.json` |

### Optional: ask the org (G147)
| POST | `/api/tenants/{t}/ask` | `{question}` -> `{template, params, rows, cypher, sources, answer_text}` |
|---|---|---|

## MCP tools (`/mcp`, streamable HTTP)
Descriptions are written for the calling agent; keep them verbatim in code.

| Tool | Description (verbatim) | Input schema | Output |
|---|---|---|---|
| `variant_status` | "Get the current ClinVar classification of a variant by Variation ID: every submitting lab's classification with review stars and evaluation date, the aggregate, recent class changes, and which submissions differ from an expert-panel review. Call this before you state a variant's classification." | `{vcv: integer, as_of?: string}` | text (FLOWS F17.2) + structured `VariantStatus` |
| `duty_map` | "For a ClinVar class change, list who must be told in a lab's families, through which permitted channel, who owns each duty today, and which decisions must reopen. Decision support for genetic counsellors; nothing is sent." | `{change_id?: string, vcv?: integer, release?: string, tenant?: string, token?: string}` (either `change_id` or `vcv` + `release`; with `vcv` + `release` the tool runs K9 for that vcv, takes the SCV of the tenant's `mirrors_submitter`, forms `<scv>@<release>` and validates it with K17; no match -> `CHANGE_NOT_FOUND`) | text (FLOWS F17.3) + structured `DutyMap` |
| `explain_person` | "Explain one person's duty for a class change: every derivation path, what cut it or which consent condition failed, and who owns the duty." | `{change_id: string, pid: string, tenant: string, token?: string}` | text + structured `DutyRow` |
| `owner_today` | "Find who holds a patient's follow-up today across retirements, panel handoffs and clinic closures, or prove that nobody does." | `{tenant: string, clinician_id?: string, pid?: string}` | text + structured `Owner` |
| `submitter_changes` | "List the classifications a ClinVar submitter changed in a monthly release." | `{submitter_id?: string, submitter_name?: string, release: string}` | text + structured `Change[]` |
| `reconsideration_queue` | "List a submitter's classifications that differ from a current expert-panel review, as of a release. Neutral information for the lab's own curation team." | `{submitter_id: string, as_of: string}` | text + structured K11 rows |

Every MCP call with a tenant writes a `Turn` (L16). Without a token, `duty_map` and `explain_person` return BLOCKED and NOT_AT_RISK people as counts only (no labels).
