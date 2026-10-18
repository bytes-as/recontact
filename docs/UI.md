# Recontact web app specification

Next.js (App Router, TypeScript, Tailwind) on Vercel. Calls the API at `NEXT_PUBLIC_API_URL`. Every page works at 375 px wide. Every page with people or verdicts shows the disclaimer.

## Visual language
- Background warm off-white `#f7f5f0` (light default) with dark mode `#12161b`; surface `#ffffff` / `#1a2027`; text `#1d232a` / `#e6ebf0`; muted `#6b7480` / `#98a3b1`; one accent deep teal `#0f766e`.
- Verdict colours (semantic, not accent): DIRECT_NOTICE green `#1f9d55`; VIA_FAMILY_LETTER blue `#2f6fd6`; BLOCKED_NO_PERMITTED_PATH red `#d64545`; NOT_AT_RISK_NO_INHERITANCE_PATH grey `#9aa3ae` (node drawn faded); NEEDS_REVIEW amber `#d9a21b`; NO_ACTION light grey `#c4c9cf`; ALREADY_NOTIFIED violet `#7c5cc4`.
- Change-kind chips: UP_TO_ACTIONABLE "Upgraded to actionable" (red outline), DOWN_FROM_ACTIONABLE "Downgraded from actionable" (blue outline), VUS_RESOLVED_BENIGN "Uncertain -> benign" (green outline), WITHIN_TIER "Same tier" (grey), BENIGN_TO_VUS / NEEDS_REVIEW_CLASS "Needs review" (amber).
- Pedigree: squares male, circles female, slash = deceased; carriers filled dark; at-risk relatives ringed in their verdict colour; pruned side faded with a dashed boundary; partners joined by a horizontal line; parent-child lines vertical. Derivation edges overlay the pedigree: green = permitted (direct), blue = permitted (letter), red = open but a consent condition failed, grey dashed = cut by a negative test.
- Typeface: Inter for UI, Source Serif 4 for page titles, JetBrains Mono for ids (VCV, SCV, change ids) and Cypher.

## Global layout
- Top bar: logo "Recontact", nav: What changed, Duty maps, Approval queue, Organisation, Loop, MCP, Eval, How it works. Status dot reads `/api/health` (green up; amber when `kb.loading` or `ncbi` degraded; red down with the banner "The graph database is restarting. Try again in a minute.").
- Tenant switcher (right of nav): "Demo lab (fictional)" or "Your sandbox (expires 14:32)"; button "Try it as the lab" -> `POST /api/sandbox`.
- Footer (every page): "Built for Graph Hacks with FalkorDB · Decision support for genetic counsellors. Not medical advice. · ClinVar data: NCBI monthly archives, public · People, families, clinicians and organisations shown are fictional."

## Pages

### `/` What changed in ClinVar
- Title: "When ClinVar changes, who must be told?" Sub: "Real ClinVar submissions, diffed month by month inside FalkorDB. Pick any lab to see the classifications it changed."
- Controls: release select (from `/api/releases`, default newest; label "ClinVar monthly archive"), "Pick any lab" searchable list (K8 rows: name, "<n> changes, <m> actionable"), VCV search box (placeholder "Variation ID, e.g. 51579", Enter -> `/variant/<vcv>`).
- Change list for the selected submitter: columns Gene, Variant (mono), Submission (SCV.version), Change ("Uncertain significance -> Likely pathogenic"), Kind chip, "Submitter evaluated <date>", actions "Variant" and (if `reported_by_demo` includes the vcv) "Duty map".
- Explainer line under the list: "A change appears in the month it first reached the public archive, which can be later than the submitter's evaluation date."
- States: loading skeleton "Reading the release from the graph..."; empty "This submitter changed no classifications in our gene set this month."; kb loading "Loading ClinVar into the graph: <n>%"; error envelope + hint + "Try again".

### `/variant/[vcv]` Variant status
- Header: gene, variant name (mono), "VCV<9 digits>", aggregate class + review status + stars, "as of ClinVar <release>" with an as-of select.
- Submissions table: Submitter, Classification, Stars, Evaluated, Since release; a neutral tag "Differs from the current expert-panel review" when applicable (amber outline, tooltip "This submission's classification falls on the other side of the actionable line from the expert-panel review of the same variant.").
- Expert-panel line (if any): "Expert-panel review: <class> by <panel>, evaluated <date>."
- History: list of class changes (release, submitter, from -> to).
- Live source (source = live): banner "This variant is outside the gene set loaded into our graph; showing ClinVar's current record. No release history or duty maps are available for it."
- Actions: "Open duty map" (if a demo lab report cites it); "Seed a synthetic family with this change" (sandbox only; disabled with tooltip "Start a sandbox to seed a fictional family").
- Line: "Do not quote one submission's classification as the variant's classification."

### `/duty/[changeId]` Duty map
States:
- Loading (< 2 s): "Walking the families in FalkorDB..."
- Degraded: owners show "Waiting for Riverside Health (fictional) to answer..." and refresh every 3 s up to 30 s.
- No report: grey card with the `proof_none` sentence, e.g. "No report in this organisation cites VCV 2877: no one to tell."
- Error: envelope message + hint + "Try again".
Content:
1. Header: change chip, "<Submitter> updated its classification of <gene> <variant> from <from words> to <to words> in the <release> ClinVar archive (evaluated <date>)." Line: "Lab: Demo Diagnostics Lab (fictional), whose classifications mirror public ClinVar submissions by <submitter>. Families are synthetic."
2. Gene rule strip: AD auto: "Autosomal dominant: relatives are routed automatically; a negative test cuts that side of the family." Review gene: "<gene> is <inheritance> (<reason>): relatives go to a genetic counsellor for review."
3. Counts row: Direct notices, Family letters, Blocked (no permitted path), Not at risk (no inheritance path), Needs review, Decisions reopened.
4. Pedigree graph per family (tabs "Family A", "Family D"...), styles above; clicking a person opens the proof drawer. A2 banner when applicable: "Two carriers in this family: their duty maps are merged so nobody is told twice."
5. Verdict table: Person, Role, Verdict pill, Notice ("Upgrade", "New risk", "Correction", "Uncertain finding resolved"), Channel ("Direct contact by the care team", "Family letter through <source label>"), Degree, Owner, "Why".
6. Proof drawer for one person: every derivation as a path of names with the common ancestor highlighted; cut derivations "No inheritance path: <name> tested negative on <date>"; failed conditions as a list; chosen derivation marked "Used"; owner chain "Dr Ama Okafor (fictional) -> handed panel 2023-06-30 -> Dr Sofia Lindqvist (fictional)"; ORPHAN card "No one holds this duty today. Dead ends: Dr Ruth Ellis (fictional) left 2024-06-30; Harbour Heart Clinic (fictional) closed 2024-06-30 with no successor. Routed to Dr Lucia Garcia, medical director (fictional)."; consent history (C3).
7. Reopened decisions: card per decision: "<summary> - rested on <class> (<release>, <SCV.version>); now <to class>. Owner: <owner>. Approved by <approver>. Sources: <links>." Button (sandbox) "Open task".
8. Baseline panel (right column on desktop, below on mobile): title "What an amended-report lookup does"; list of letters "Letter to <clinician> - <active ? 'in post' : 'no longer in post'>"; "Relatives reached: 0"; "Decisions reopened: 0".
9. "How we decided" collapsible: the X2, C1, W1, D1 Cypher with parameters, `computed_ms`, and the legend of edge colours.
10. Sandbox controls (only in a sandbox): per person "Change consent" (select family share / contact preference / recontact) and "Record a test"; button "Recompute"; button "Save as run" (writes a Run and drafts tasks).
11. Disclaimer line.

### `/queue` Approval queue
- Tabs: "Lab tasks" (APPROVE_NOTICE, REVIEW_NEEDS_REVIEW, ACK_BLOCKED, AMEND_REPORT, RECONSIDER_SUBMISSION), "Health-system tasks" (REOPENED_DECISION, ORPHAN_DUTY, DELIVER_NOTICE, HANDOFF_FAILED).
- Task card: kind, about (person label or decision), verdict pill, draft title and body (editable textarea in a sandbox), playbook steps, "handed off from" link, events.
- Acting as: select of counsellors from the paired hs graph ("Yuki Sato, genetic counsellor (fictional)", "Amal Ibrahim, genetic counsellor (fictional)", "Dr Lucia Garcia, medical director (fictional)"). Buttons: Claim, Approve, Reject (reason required), Acknowledge (for ACK_BLOCKED).
- After approve: toast "Approved. A delivery task was created for <owner>. Recontact never sends anything itself."
- Fixed tenant: buttons disabled with tooltip "Start a sandbox to act as the lab."
- Events timeline (right): newest first.

### `/org` Riverside Health (fictional)
- Header: "Riverside Health (fictional): who owns what, and which decisions rest on which ClinVar release".
- "Who owns each patient's follow-up today": table of carriers with owner, status (Resolved / Fallback / Orphan) and chain.
- Roster (W5): clinicians with role, team, active, left at, number of patients.
- "Decisions resting on old releases": cutoff select (default 2026-01) -> D4 rows with owner (flag "no longer in post"), approver, sources; trace drawer (decision -> release, SCV version with ClinVar link -> owner -> approver -> sources).
- "Reopened decisions awaiting review" (D5).
- Optional (G147): "Ask the organisation" box with example chips.

### `/loop` Reconsideration loop
- Title: "Open questions that ClinVar's own archives closed".
- Intro (verbatim): "Each item below is a submission whose classification differed from the current expert-panel review in the August 2026 archive. Recontact remembered it, routed it to the lab's curation queue, and closed it when a later monthly archive showed the submission updated. These closures come from ClinVar's own monthly archives. We do not claim our reminder caused them: we remember the open question, route it, and close it with a citation when the evidence appears."
- Timeline: 2026-08 opened (<n>), 2026-09 closed (<n>), 2026-10 closed (<n>), still open (<n>); each item: gene, VCV, SCV, "submission <class> v<n> -> <class> v<m> (archive <release>)" or "version updated, classification kept".
- Note: "The demo lab is fictional; the submissions are real public ClinVar records shown neutrally."

### `/mcp`
- Command block with copy button: `claude mcp add --transport http recontact https://<api-host>/mcp`; Cursor config snippet `{"mcpServers": {"recontact": {"url": "https://<api-host>/mcp"}}}`; tool table from `docs/API.md`; the demo prompt from BLUEPRINT section 9; a short recording of Claude Code calling `variant_status`.

### `/eval`
- Hash line: "Labels and reference implementation committed before the engine: sha256 <...>. Held-out seeds: sha256 <...> (revealed <date>)."
- Headline cards: "N of 30 held-out worlds exactly right", "Safety count: 0 notices without a permitted path", per-person accuracy on 40 hand-labelled hard cases, owner accuracy, reopened-decision precision and recall, "Needs-review transitions: 10 of 10 with no notice", "Unchanged controls: 10 of 10 with no class change".
- Comparison table: Recontact vs amended-report baseline (relatives reached, letters to clinicians no longer in post, decisions reopened).
- Per-case table with filters by category.

### `/how-it-works`
- Diagram of the graphs on one FalkorDB instance (kb, lab, health system, sandboxes) and the handoff arrows; the four mechanisms (exposure with pruning, owner succession, consent AND/OR, reopen on change) with one query each; the algorithms (WCC, BFS) and why we use no others; the privacy and minimum-necessary rule; links to the repo and `docs/queries.cypher`.

## Copy rules (enforced by G057, G116)
- About real labs and submissions, never use: "stale", "wrong", "incorrect", "outdated", "error", "mistake", "faulty", "negligent", "failed to". Use: "updated its classification", "differs from the current expert-panel review", "submitted before the most recent expert-panel review", "first appeared in the <release> archive".
- About people and medicine, never use: "you have", "you will develop", "diagnosis" (except the fixed template sentence "This letter is not a diagnosis."), "must have surgery", "cure". Use: "may be relevant to your health", "would like to talk with you", "discuss with your care team".
- Always label fictional people, clinicians and organisations with "(fictional)". Never invent a real person's name for a clinician.
- Verdict names in the UI: "Direct notice", "Family letter", "Blocked: no permitted path", "Not at risk: no inheritance path", "Needs review", "No action", "Already notified".
- Error messages say what went wrong and how to fix it, without apologies.
- The words "proof" and "no path" are used only for graph results (no inheritance path, no permitted path, no owner, no report cites).
- Test scope (G057, G116): `data/notice_templates.json`; every string returned by the routes in `app/routes/kb.py`, `duty.py`, `loop.py`, `org.py` and `tasks.py` for the demo tenant (collected by the test from live calls); and the source files under `apps/web/app/` for the pages `/`, `/variant`, `/duty`, `/queue`, `/org`, `/loop`. Generic error components in `apps/web/components/errors/` are excluded from the lab-word list (they may say "error"). Matching is case-insensitive on whole words, except the prefixes "diagnos", "negligen" and the phrase "failed to".
