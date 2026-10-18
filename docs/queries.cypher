// Recontact: every Cypher query the product runs, for FalkorDB.
// Graphs: "kb" (real public ClinVar, shared, read-mostly), "lab_demo" (fictional lab tenant, synthetic people),
// "hs_demo" (fictional health-system tenant, synthetic clinicians and decisions), sandboxes "sbx_<8hex>_lab" / "sbx_<8hex>_hs".
// Block format: a header line "// NAME: purpose (graph)" followed by the query. Code copies each block verbatim into
// services/api/app/graph/queries.py as a constant with the same NAME (goal G011 tests that they stay in sync).
// All parameters are passed with falkordb-py: graph.query(q, params) / graph.ro_query(q, params). Never build Cypher strings.
//
// Verified: every block below (81 blocks; 52 behavioural checks) was executed on 18 Oct 2026 against falkordb/falkordb:latest (graph module version 42201)
// via `docker exec rc-test redis-cli GRAPH.QUERY <graph> "CYPHER k=v ... <query>"` on a fixture that contains:
// a 4-generation family with a tested-negative mother (pruning), a cousin carrier with direct consent and a proband who
// refused family contact (cousin path), a relative with "not_to_know", a letter-only jurisdiction, a deceased source,
// a half-sibling, a retired clinician with a panel handoff, a closed clinic with a successor, a closed clinic with no
// successor (ORPHAN), decisions resting on VUS and on LP, and three monthly ClinVar releases (base + two deltas).
// Verified behaviours: *0..3 zero-length segments; node membership `n IN nodes(p)`; list slicing nodes(p)[1..-1];
// CASE without ELSE inside list comprehensions; OPTIONAL MATCH ... WHERE; pattern predicates `NOT (n)-[:T]->()`;
// time-ordered paths via all(i IN range(...)) over relationships(p); idempotent re-run of K5 (no duplicate versions or
// ClassChange nodes); algo.WCC with a config map; algo.BFS(node, depth, 'TYPE') follows OUTGOING edges only;
// GRAPH.COPY (destination must not exist). The image default query TIMEOUT is 1000 ms: run with TIMEOUT 5000.
// Known FalkorDB caveat (kept from ModelBrain): reference every relationship alias you bind, or counts can be wrong.
// Bounded variable-length paths only. No unbounded `*`.

// ===========================================================================
// SCHEMA
// ===========================================================================

// SCHEMA_KB: indexes for the shared ClinVar graph (kb)
CREATE INDEX FOR (v:Variant) ON (v.vcv);
CREATE INDEX FOR (g:Gene) ON (g.symbol);
CREATE INDEX FOR (s:SCV) ON (s.acc);
CREATE INDEX FOR (x:SCVVersion) ON (x.id);
CREATE INDEX FOR (u:Submitter) ON (u.id);
CREATE INDEX FOR (r:Release) ON (r.id);
CREATE INDEX FOR (c:ClassChange) ON (c.id);
CREATE INDEX FOR (c:ClassChange) ON (c.release);
CREATE INDEX FOR (l:LiveLookup) ON (l.vcv);

// SCHEMA_LAB: indexes for a lab tenant graph (lab_demo, sbx_*_lab)
CREATE INDEX FOR (p:Person) ON (p.pid);
CREATE INDEX FOR (r:Report) ON (r.id);
CREATE INDEX FOR (v:VariantRef) ON (v.vcv);
CREATE INDEX FOR (d:Duty) ON (d.id);
CREATE INDEX FOR (r:Run) ON (r.id);
CREATE INDEX FOR (t:Task) ON (t.id);
CREATE INDEX FOR (n:Notice) ON (n.vcv);
CREATE INDEX FOR (h:Handoff) ON (h.id);
CREATE INDEX FOR (r:Recon) ON (r.id);
CREATE INDEX FOR (j:Jurisdiction) ON (j.code);

// SCHEMA_HS: indexes for a health-system tenant graph (hs_demo, sbx_*_hs)
CREATE INDEX FOR (c:Clinician) ON (c.id);
CREATE INDEX FOR (c:Clinic) ON (c.id);
CREATE INDEX FOR (p:Patient) ON (p.pid);
CREATE INDEX FOR (d:Decision) ON (d.id);
CREATE INDEX FOR (v:VariantRef) ON (v.vcv);
CREATE INDEX FOR (t:Task) ON (t.id);
CREATE INDEX FOR (h:Handoff) ON (h.id);

// ===========================================================================
// KB (real ClinVar, graph "kb")
// ===========================================================================

// K1: upsert ACMG secondary-findings genes from data/genes.json (kb)
UNWIND $rows AS r
MERGE (g:Gene {symbol: r.symbol})
SET g.inheritance = r.inheritance, g.review_always = r.review_always, g.review_reason = r.review_reason,
    g.category = r.category, g.condition = r.condition, g.sf_version = r.sf_version
RETURN count(g) AS genes;

// K2: upsert variants from the variant_summary extract (GRCh38 rows only), batch of up to 2000 (kb)
UNWIND $rows AS r
MATCH (g:Gene {symbol: r.gene})
MERGE (v:Variant {vcv: r.vcv})
SET v.name = r.name, v.gene = r.gene, v.agg_cls = r.agg_cls, v.agg_cls_raw = r.agg_cls_raw,
    v.agg_review = r.agg_review, v.agg_stars = r.agg_stars, v.agg_release = $release
MERGE (v)-[:IN_GENE]->(g)
RETURN count(v) AS variants;

// K3: record a loaded release (append-only; one node per monthly archive) (kb)
MERGE (r:Release {id: $release})
ON CREATE SET r.kind = $kind, r.file = $file, r.file_sha256 = $file_sha256, r.rows = $rows, r.loaded_at = $now
RETURN r.id AS release, r.loaded_at AS loaded_at;

// K4: upsert submitters and SCV records, batch (kb)
UNWIND $rows AS r
MATCH (v:Variant {vcv: r.vcv})
MERGE (u:Submitter {id: r.submitter_id})
ON CREATE SET u.name = r.submitter
MERGE (s:SCV {acc: r.acc})
ON CREATE SET s.vcv = r.vcv, s.submitter_id = r.submitter_id
MERGE (s)-[:ABOUT]->(v)
MERGE (s)-[:SUBMITTED_BY]->(u)
RETURN count(s) AS scvs;

// K5: the release diff, done in FalkorDB. For each row of a release: if the SCV's current version differs
// (new version or new class), close the current version (superseded_in = release), add the new version,
// link NEXT, and create a ClassChange when the class differs. Idempotent: re-running a release changes nothing. (kb)
UNWIND $rows AS r
MATCH (s:SCV {acc: r.acc})
OPTIONAL MATCH (s)-[hv:HAS_VERSION]->(cur:SCVVersion)
WHERE cur.superseded_in IS NULL
WITH s, r, cur, r.acc + '.' + toString(r.version) + '|' + r.cls AS new_id
WHERE cur IS NULL OR cur.id <> new_id
CREATE (nv:SCVVersion {id: new_id, acc: r.acc, version: r.version, cls: r.cls, cls_raw: r.cls_raw,
                       dle: r.dle, review: r.review, stars: r.stars, first_release: $release})
CREATE (s)-[:HAS_VERSION]->(nv)
WITH s, r, cur, nv
WHERE cur IS NOT NULL
SET cur.superseded_in = $release
CREATE (cur)-[:NEXT {release: $release}]->(nv)
WITH s, r, cur, nv
WHERE cur.cls <> nv.cls
CREATE (cc:ClassChange {id: r.acc + '@' + $release, acc: r.acc, vcv: r.vcv, submitter_id: s.submitter_id,
                        release: $release, from_cls: cur.cls, to_cls: nv.cls,
                        from_version: cur.version, to_version: nv.version, to_dle: nv.dle, to_stars: nv.stars,
                        kind: CASE
                          WHEN cur.cls IN ['CONFLICTING', 'OTHER'] OR nv.cls IN ['CONFLICTING', 'OTHER'] THEN 'NEEDS_REVIEW_CLASS'
                          WHEN NOT cur.cls IN ['P', 'LP'] AND nv.cls IN ['P', 'LP'] THEN 'UP_TO_ACTIONABLE'
                          WHEN cur.cls IN ['P', 'LP'] AND NOT nv.cls IN ['P', 'LP'] THEN 'DOWN_FROM_ACTIONABLE'
                          WHEN cur.cls = 'VUS' AND nv.cls IN ['LB', 'B'] THEN 'VUS_RESOLVED_BENIGN'
                          WHEN cur.cls IN ['LB', 'B'] AND nv.cls = 'VUS' THEN 'BENIGN_TO_VUS'
                          ELSE 'WITHIN_TIER' END})
CREATE (cc)-[:OF]->(s)
CREATE (cc)-[:FROM]->(cur)
CREATE (cc)-[:TO]->(nv)
RETURN count(cc) AS class_changes;

// K6: SCVs withdrawn in a release (listed in the delta file): close their current version (kb)
UNWIND $accs AS acc
MATCH (s:SCV {acc: acc})-[hv:HAS_VERSION]->(cur:SCVVersion)
WHERE cur.superseded_in IS NULL
SET cur.superseded_in = $release, cur.withdrawn_in = $release
RETURN count(cur) AS withdrawn;

// K7: "pick any lab": one submitter's class changes in a release, real data (kb, read-only)
MATCH (u:Submitter {id: $submitter_id})<-[sb:SUBMITTED_BY]-(s:SCV)<-[o:OF]-(cc:ClassChange {release: $release})
MATCH (s)-[ab:ABOUT]->(v:Variant)-[ig:IN_GENE]->(g:Gene)
RETURN cc.id AS change_id, v.vcv AS vcv, v.name AS variant, g.symbol AS gene, g.inheritance AS inheritance,
       s.acc AS scv, cc.from_cls AS from_cls, cc.to_cls AS to_cls, cc.from_version AS from_version,
       cc.to_version AS to_version, cc.to_dle AS submitter_evaluated, cc.kind AS kind, u.name AS submitter
ORDER BY CASE cc.kind WHEN 'UP_TO_ACTIONABLE' THEN 0 WHEN 'DOWN_FROM_ACTIONABLE' THEN 1
                      WHEN 'VUS_RESOLVED_BENIGN' THEN 2 ELSE 3 END, g.symbol, v.vcv
LIMIT $limit;

// K8: submitters ranked by class changes in a release (the submitter picker) (kb, read-only)
MATCH (cc:ClassChange {release: $release})-[o:OF]->(s:SCV)-[sb:SUBMITTED_BY]->(u:Submitter)
RETURN u.id AS submitter_id, u.name AS submitter, count(cc) AS changes,
       sum(CASE WHEN cc.kind IN ['UP_TO_ACTIONABLE', 'DOWN_FROM_ACTIONABLE'] THEN 1 ELSE 0 END) AS actionable_changes
ORDER BY actionable_changes DESC, changes DESC, submitter ASC
LIMIT $limit;

// K9: variant_status: every submission's classification as of a release, plus gene facts (kb, read-only)
MATCH (v:Variant {vcv: $vcv})-[ig:IN_GENE]->(g:Gene)
OPTIONAL MATCH (v)<-[ab:ABOUT]-(s:SCV)-[hv:HAS_VERSION]->(x:SCVVersion)
WHERE x.first_release <= $as_of AND (x.superseded_in IS NULL OR x.superseded_in > $as_of)
OPTIONAL MATCH (s)-[sb:SUBMITTED_BY]->(u:Submitter)
RETURN v.vcv AS vcv, v.name AS variant, v.agg_cls AS aggregate_cls, v.agg_review AS aggregate_review,
       v.agg_stars AS aggregate_stars, v.agg_release AS aggregate_release,
       g.symbol AS gene, g.inheritance AS inheritance, g.review_always AS review_always,
       collect(CASE WHEN x IS NULL THEN null ELSE
         {scv: s.acc, version: x.version, cls: x.cls, cls_raw: x.cls_raw, stars: x.stars, review: x.review,
          evaluated: x.dle, since_release: x.first_release, submitter: u.name, submitter_id: u.id} END) AS submissions;

// K10: class-change history of one variant, newest first (kb, read-only)
MATCH (cc:ClassChange {vcv: $vcv})-[o:OF]->(s:SCV)-[sb:SUBMITTED_BY]->(u:Submitter)
RETURN cc.id AS change_id, cc.release AS release, s.acc AS scv, u.name AS submitter, cc.from_cls AS from_cls,
       cc.to_cls AS to_cls, cc.kind AS kind, cc.to_dle AS submitter_evaluated
ORDER BY release DESC, scv ASC
LIMIT 100;

// K11: reconsideration candidates for one submitter as of a release: its current classification falls on the other
// side of the actionable line from a current expert-panel or practice-guideline review (stars >= 3) of the same
// variant. Wording rule: "this submission's classification differs from the current expert-panel review". (kb, read-only)
MATCH (u:Submitter {id: $submitter_id})<-[sb:SUBMITTED_BY]-(s:SCV)-[hv:HAS_VERSION]->(x:SCVVersion)
WHERE x.stars < 3 AND x.first_release <= $as_of AND (x.superseded_in IS NULL OR x.superseded_in > $as_of)
  AND x.cls IN ['P', 'LP', 'VUS', 'LB', 'B']
MATCH (s)-[ab:ABOUT]->(v:Variant)
WHERE $gene IS NULL OR v.gene = $gene
MATCH (v)<-[ab2:ABOUT]-(e:SCV)-[hv2:HAS_VERSION]->(ex:SCVVersion)
WHERE e.acc <> s.acc AND ex.stars >= 3 AND ex.first_release <= $as_of
  AND (ex.superseded_in IS NULL OR ex.superseded_in > $as_of)
  AND ex.cls IN ['P', 'LP', 'VUS', 'LB', 'B']
  AND (x.cls IN ['P', 'LP']) <> (ex.cls IN ['P', 'LP'])
MATCH (e)-[sb2:SUBMITTED_BY]->(panel:Submitter)
RETURN v.vcv AS vcv, v.gene AS gene, s.acc AS scv, x.version AS version, x.cls AS submission_cls,
       x.dle AS submission_evaluated, ex.cls AS panel_cls, panel.name AS panel, e.acc AS panel_scv, ex.dle AS panel_evaluated
ORDER BY gene, vcv
LIMIT $limit;

// K12: close-the-loop check for open reconsideration items: the submission's version and class as of a later release (kb, read-only)
UNWIND $items AS it
MATCH (s:SCV {acc: it.scv})-[hv:HAS_VERSION]->(x:SCVVersion)
WHERE x.first_release <= $as_of AND (x.superseded_in IS NULL OR x.superseded_in > $as_of)
RETURN it.recon_id AS recon_id, s.acc AS scv, x.version AS version, x.cls AS cls, x.dle AS evaluated,
       x.first_release AS since_release, x.cls <> it.opened_cls AS class_changed, x.version <> it.opened_version AS version_changed;

// K13: record a live E-utilities lookup for a variant outside the loaded gene scope (memory write; raw XML is not stored) (kb)
MERGE (l:LiveLookup {vcv: $vcv})
SET l.fetched_at = $now, l.accession = $accession, l.name = $name, l.gene = $gene, l.agg_cls = $agg_cls,
    l.agg_review = $agg_review, l.submissions_json = $submissions_json, l.date_last_updated = $date_last_updated
RETURN l.vcv AS vcv;

// K14: loaded releases and counts (health, release picker) (kb, read-only)
MATCH (r:Release)
RETURN r.id AS release, r.kind AS kind, r.rows AS rows, r.loaded_at AS loaded_at
ORDER BY release ASC;

// K15: release summary: class changes per kind, restricted to genes where pedigree pruning is valid or not (kb, read-only)
MATCH (cc:ClassChange {release: $release})-[o:OF]->(s:SCV)-[ab:ABOUT]->(v:Variant)-[ig:IN_GENE]->(g:Gene)
RETURN cc.kind AS kind, g.inheritance = 'AD' AND NOT g.review_always AS pruning_valid, count(cc) AS changes
ORDER BY kind;

// K16: current classification of every SCV of the given accessions (used by the Watcher to build the next delta) (kb, read-only)
UNWIND $accs AS acc
MATCH (s:SCV {acc: acc})-[hv:HAS_VERSION]->(x:SCVVersion)
WHERE x.superseded_in IS NULL
RETURN s.acc AS scv, x.version AS version, x.cls AS cls;

// K17: one class change with its gene facts (input to a duty-map run) (kb, read-only)
MATCH (cc:ClassChange {id: $change_id})-[o:OF]->(s:SCV)-[ab:ABOUT]->(v:Variant)-[ig:IN_GENE]->(g:Gene)
MATCH (s)-[sb:SUBMITTED_BY]->(u:Submitter)
RETURN cc.id AS change_id, cc.release AS release, cc.kind AS kind, cc.from_cls AS from_cls, cc.to_cls AS to_cls,
       cc.from_version AS from_version, cc.to_version AS to_version, cc.to_dle AS submitter_evaluated,
       s.acc AS scv, u.id AS submitter_id, u.name AS submitter, v.vcv AS vcv, v.name AS variant,
       g.symbol AS gene, g.inheritance AS inheritance, g.review_always AS review_always, g.review_reason AS review_reason;

// ===========================================================================
// EXPOSURE (mechanism 1, lab tenant graph)
// ===========================================================================

// X1: carriers of the variant: everyone holding a report from this lab that cites it (lab, read-only)
MATCH (vr:VariantRef {vcv: $vcv})<-[ci:CITES]-(rep:Report)<-[hr:HAS_REPORT]-(c:Person)
RETURN c.pid AS pid, c.label AS label, c.family AS family, coalesce(c.deceased, false) AS deceased,
       coalesce(c.recontact_ok, false) AS recontact_ok, c.family_share AS family_share,
       rep.id AS report_id, rep.issued AS issued, rep.class_at_issue AS class_at_issue, rep.scv AS scv,
       rep.ordering_clinician AS ordering_clinician, rep.hs_tenant AS hs_tenant
ORDER BY family, pid;

// X2: kinship derivations from each carrier to each untested living relative, via a common ancestor
// (up the tree, then down: never through a partner), at most 4 hops, with the tested-negative people that cut
// each derivation. An empty pruned_by list means the derivation is open. (lab, read-only)
MATCH (vr:VariantRef {vcv: $vcv})<-[ci:CITES]-(rep:Report)<-[hr:HAS_REPORT]-(src:Person)
WHERE $vcv IN src.pos
MATCH p1 = (src)<-[:PARENT_OF*0..3]-(anc:Person)
MATCH p2 = (anc)-[:PARENT_OF*0..3]->(rel:Person)
WHERE rel.pid <> src.pid AND length(p1) + length(p2) >= 1 AND length(p1) + length(p2) <= 4
  AND none(n IN nodes(p2)[1..] WHERE n IN nodes(p1))
  AND NOT $vcv IN rel.pos AND NOT $vcv IN rel.neg AND coalesce(rel.deceased, false) = false
WITH src, rel, anc, p1, p2, nodes(p1)[1..] + nodes(p2)[1..-1] AS interior
RETURN rel.pid AS pid, rel.label AS label, src.pid AS source_pid, anc.pid AS common_ancestor,
       length(p1) AS up, length(p2) AS down,
       [n IN nodes(p1) | n.pid] + [n IN nodes(p2)[1..] | n.pid] AS path,
       [n IN interior WHERE $vcv IN n.neg | n.pid] AS pruned_by
ORDER BY pid, source_pid, up + down;

// X3: people tested for the variant (shown greyed on the pedigree with the test date) (lab, read-only)
MATCH (p:Person)-[ht:HAD_TEST]->(t:Test {vcv: $vcv})
RETURN p.pid AS pid, p.label AS label, t.result AS result, t.date AS date
ORDER BY date;

// X4: one family for drawing the pedigree (lab, read-only)
MATCH (p:Person {family: $family})
OPTIONAL MATCH (p)-[po:PARENT_OF]->(c:Person)
RETURN p.pid AS pid, p.label AS label, p.sex AS sex, p.birth_year AS birth_year, coalesce(p.deceased, false) AS deceased,
       p.pos AS pos, p.neg AS neg, p.contact_pref AS contact_pref, p.family_share AS family_share,
       collect(c.pid) AS children;

// ===========================================================================
// CONSENT (mechanism 3, lab tenant graph): AND along a derivation, OR across derivations
// ===========================================================================

// C1: every derivation with the conditions it passes or fails. A derivation permits DIRECT contact only if it is open
// (not pruned) AND the source is alive AND the source consented to direct family contact AND the relative has not asked
// for no contact or not to know AND the relative's jurisdiction (illustrative rule) allows direct contact. It permits a
// FAMILY LETTER if it is open AND the source is alive AND consented to at least a letter AND the relative has not
// exercised the right not to know. The engine ORs across derivations. (lab, read-only)
MATCH (vr:VariantRef {vcv: $vcv})<-[ci:CITES]-(rep:Report)<-[hr:HAS_REPORT]-(src:Person)
WHERE $vcv IN src.pos
MATCH p1 = (src)<-[:PARENT_OF*0..3]-(anc:Person)
MATCH p2 = (anc)-[:PARENT_OF*0..3]->(rel:Person)
WHERE rel.pid <> src.pid AND length(p1) + length(p2) >= 1 AND length(p1) + length(p2) <= 4
  AND none(n IN nodes(p2)[1..] WHERE n IN nodes(p1))
  AND NOT $vcv IN rel.pos AND NOT $vcv IN rel.neg AND coalesce(rel.deceased, false) = false
MATCH (rel)-[ri:RESIDES_IN]->(j:Jurisdiction)
WITH src, rel, anc, j, p1, p2, [n IN nodes(p1)[1..] + nodes(p2)[1..-1] WHERE $vcv IN n.neg | n.pid] AS pruned_by
WITH src, rel, anc, j, p1, p2, pruned_by, size(pruned_by) = 0 AS open,
     coalesce(src.deceased, false) AS src_dead
RETURN rel.pid AS pid, rel.label AS label, src.pid AS source_pid, src.label AS source_label,
       anc.pid AS common_ancestor, length(p1) AS up, length(p2) AS down,
       [n IN nodes(p1) | n.pid] + [n IN nodes(p2)[1..] | n.pid] AS path, pruned_by, open,
       open AND NOT src_dead AND src.family_share = 'direct' AND rel.contact_pref = 'ok' AND j.direct_allowed AS direct_ok,
       open AND NOT src_dead AND src.family_share IN ['letter', 'direct'] AND rel.contact_pref <> 'not_to_know' AS letter_ok,
       open AND src_dead AS needs_review,
       [x IN [
          CASE WHEN NOT open THEN 'no inheritance path: ' + pruned_by[0] + ' tested negative' END,
          CASE WHEN src_dead THEN 'source ' + src.label + ' is deceased' END,
          CASE WHEN src.family_share = 'none' THEN 'source ' + src.label + ' did not consent to family contact' END,
          CASE WHEN src.family_share = 'letter' THEN 'source ' + src.label + ' consented to a family letter only' END,
          CASE WHEN rel.contact_pref = 'no_contact' THEN 'relative asked not to be contacted by the clinic' END,
          CASE WHEN rel.contact_pref = 'not_to_know' THEN 'relative exercised the right not to know' END,
          CASE WHEN NOT j.direct_allowed THEN 'jurisdiction ' + j.code + ' (illustrative rule) does not allow direct contact' END
        ] WHERE x IS NOT NULL] AS failed,
       j.code AS jurisdiction
ORDER BY pid, up + down, source_pid;

// C2: record a consent or preference change (append-only Consent node; the Person property is the current value) (lab)
MATCH (p:Person {pid: $pid})
CREATE (c:Consent {id: $consent_id, kind: $kind, value: $value, at: $now, recorded_by: $recorded_by})
CREATE (p)-[:GAVE]->(c)
SET p.family_share = CASE WHEN $kind = 'family_share' THEN $value ELSE p.family_share END,
    p.contact_pref = CASE WHEN $kind = 'contact_pref' THEN $value ELSE p.contact_pref END,
    p.recontact_ok = CASE WHEN $kind = 'recontact' THEN $value = 'yes' ELSE p.recontact_ok END
RETURN p.pid AS pid, p.family_share AS family_share, p.contact_pref AS contact_pref, p.recontact_ok AS recontact_ok;

// C3: consent history of one person (decision trace) (lab, read-only)
MATCH (p:Person {pid: $pid})-[g:GAVE]->(c:Consent)
RETURN c.kind AS kind, c.value AS value, c.at AS at, c.recorded_by AS recorded_by
ORDER BY at DESC;

// ===========================================================================
// OWNER (mechanism 2, health-system tenant graph)
// ===========================================================================

// W1: who holds the duty today: the shortest time-ordered succession chain from the ordering clinician to an active
// clinician over panel handoffs, practice, clinic successions and current clinic leads. No row = no path. (hs, read-only)
MATCH (c0:Clinician {id: $clinician_id})
MATCH p = (c0)-[:HANDED_PANEL_TO|PRACTICED_AT|SUCCEEDED_BY|LED_BY*0..5]->(c:Clinician)
WHERE c.active = true
  AND all(i IN range(0, size(relationships(p)) - 2) WHERE relationships(p)[i].at <= relationships(p)[i + 1].at)
  AND all(r IN relationships(p) WHERE type(r) <> 'LED_BY' OR r.until IS NULL)
RETURN c.id AS owner_id, c.name AS owner, c.role AS role, length(p) AS hops,
       [n IN nodes(p) | coalesce(n.name, n.id)] AS chain,
       [r IN relationships(p) | type(r) + ' ' + r.at] AS steps
ORDER BY hops ASC
LIMIT 1;

// W2: dead ends behind an ORPHAN: every node reachable from the ordering clinician that has no onward succession (hs, read-only)
MATCH (c0:Clinician {id: $clinician_id})
MATCH p = (c0)-[:HANDED_PANEL_TO|PRACTICED_AT|SUCCEEDED_BY|LED_BY*0..5]->(n)
WHERE NOT (n)-[:HANDED_PANEL_TO|SUCCEEDED_BY]->() AND NOT (n:Clinician AND n.active = true)
WITH DISTINCT n
RETURN labels(n)[0] AS kind, coalesce(n.name, n.id) AS name, n.active AS active, n.left_at AS left_at,
       n.open AS open, n.closed_at AS closed_at;

// W3: fallback owner: the patient's current active clinician of record (hs, read-only)
MATCH (pt:Patient {pid: $pid})-[u:UNDER_CARE]->(c:Clinician)
WHERE c.active = true AND u.until IS NULL
RETURN c.id AS owner_id, c.name AS owner, c.role AS role, u.from AS since
ORDER BY since DESC
LIMIT 1;

// W4: the medical director who receives ORPHAN duties (hs, read-only)
MATCH (r:Role {name: 'medical_director'})-[h:HELD_BY]->(c:Clinician)
RETURN c.id AS owner_id, c.name AS owner;

// W5: roster: who owns what today (company-brain view) (hs, read-only)
MATCH (c:Clinician)
OPTIONAL MATCH (c)-[m:MEMBER_OF]->(t:Team)
OPTIONAL MATCH (pt:Patient)-[u:UNDER_CARE]->(c)
WITH c, t, count(DISTINCT CASE WHEN u.until IS NULL THEN pt END) AS patients
RETURN c.id AS id, c.name AS name, c.role AS role, c.active AS active, c.left_at AS left_at,
       t.name AS team, patients
ORDER BY active DESC, team, name;

// ===========================================================================
// DECISIONS (mechanism 4, health-system tenant graph): reopen on change, append-only
// ===========================================================================

// D1: active decisions that rested on this variant and must reopen for the new class: the class they rested on is on
// the other side of the actionable line (P/LP vs not), or they rested on a VUS that is now resolved either way. (hs, read-only)
MATCH (d:Decision)-[ro:RESTED_ON]->(vr:VariantRef {vcv: $vcv})
OPTIONAL MATCH (newer:Decision)-[sp:SUPERSEDES]->(d)
WITH d, ro, newer, sp
WHERE newer IS NULL
  AND (((ro.cls_at_time IN ['P', 'LP']) <> ($new_cls IN ['P', 'LP'])) OR (ro.cls_at_time = 'VUS' AND $new_cls <> 'VUS'))
OPTIONAL MATCH (d)-[ob:OWNED_BY]->(o:Clinician)
OPTIONAL MATCH (d)-[ap:APPROVED_BY]->(a:Clinician)
OPTIONAL MATCH (d)-[cs:CITES]->(src:Source)
RETURN d.id AS decision_id, d.pid AS pid, d.kind AS kind, d.summary AS summary, d.made_at AS made_at,
       ro.cls_at_time AS rested_on_cls, ro.release AS rested_on_release, ro.scv AS rested_on_scv,
       o.id AS owner_id, o.name AS owner, coalesce(o.active, false) AS owner_active, a.name AS approved_by,
       collect(DISTINCT src.url) AS sources
ORDER BY made_at;

// D2: reopen a decision (append-only Event; the decision itself is never edited; idempotent on event id) (hs)
MATCH (d:Decision {id: $decision_id})
MERGE (e:Event {id: $event_id})
ON CREATE SET e.kind = 'REOPENED', e.at = $now, e.reason = $reason, e.release = $release, e.change_id = $change_id
MERGE (e)-[:ON]->(d)
RETURN e.id AS event_id;

// D3: replace a reopened decision after human approval: new decision resting on the new class, SUPERSEDES the old (hs)
MATCH (old:Decision {id: $old_id}), (by:Clinician {id: $approver_id})
MERGE (vr:VariantRef {vcv: $vcv})
CREATE (d:Decision {id: $new_id, pid: old.pid, kind: $kind, summary: $summary, made_at: $now})
CREATE (d)-[:RESTED_ON {vcv: $vcv, scv: $scv, cls_at_time: $new_cls, release: $release}]->(vr)
CREATE (d)-[:SUPERSEDES]->(old)
CREATE (d)-[:APPROVED_BY]->(by)
CREATE (d)-[:OWNED_BY]->(by)
CREATE (e:Event {id: $event_id, kind: 'SUPERSEDED', at: $now, reason: $reason})
CREATE (e)-[:ON]->(old)
RETURN d.id AS decision_id;

// D4: company-brain question: which active decisions still rest on a ClinVar release older than a cutoff, who owns and
// approved them, and what they cited (hs, read-only)
MATCH (d:Decision)-[ro:RESTED_ON]->(vr:VariantRef)
OPTIONAL MATCH (newer:Decision)-[sp:SUPERSEDES]->(d)
WITH d, ro, vr, newer, sp
WHERE newer IS NULL AND ro.release < $cutoff_release
OPTIONAL MATCH (d)-[ob:OWNED_BY]->(o:Clinician)
OPTIONAL MATCH (d)-[ap:APPROVED_BY]->(a:Clinician)
OPTIONAL MATCH (d)-[cs:CITES]->(src:Source)
RETURN d.id AS decision_id, d.kind AS kind, vr.vcv AS vcv, ro.cls_at_time AS cls, ro.release AS release,
       o.name AS owner, coalesce(o.active, false) AS owner_active, a.name AS approved_by, collect(DISTINCT src.url) AS sources
ORDER BY release ASC;

// D5: reopened decisions still awaiting a human (REOPENED event, not yet superseded) (hs, read-only)
MATCH (e:Event {kind: 'REOPENED'})-[on:ON]->(d:Decision)
OPTIONAL MATCH (newer:Decision)-[sp:SUPERSEDES]->(d)
WITH e, d, newer, sp
WHERE newer IS NULL
RETURN d.id AS decision_id, d.pid AS pid, d.kind AS kind, d.summary AS summary, e.at AS reopened_at,
       e.reason AS reason, e.change_id AS change_id
ORDER BY reopened_at DESC;

// ===========================================================================
// LEDGER, TASKS, HANDOFFS (Track 2 memory and coordination; lab and hs graphs)
// ===========================================================================

// L1: earlier approved notices about this variant (memory across releases) (lab, read-only)
MATCH (p:Person)-[wn:WAS_NOTIFIED]->(n:Notice {vcv: $vcv})
RETURN p.pid AS pid, p.contact_pref AS contact_pref, coalesce(p.deceased, false) AS deceased, n.id AS notice_id,
       n.cls AS cls, n.notice_type AS notice_type, n.channel AS channel, n.release AS release, n.approved_at AS approved_at
ORDER BY approved_at DESC;

// L2: write a duty-map run and its per-person duties (append-only) (lab)
CREATE (r:Run {id: $run_id, change_id: $change_id, vcv: $vcv, release: $release, kind: $kind, at: $now,
               from_cls: $from_cls, to_cls: $to_cls, engine_version: $engine_version})
WITH r
UNWIND $duties AS d
MATCH (p:Person {pid: d.pid})
CREATE (x:Duty {id: d.id, pid: d.pid, role: d.role, notice_type: d.notice_type, verdict: d.verdict,
                channel: d.channel, source_pid: d.source_pid, degree: d.degree, owner_id: d.owner_id,
                owner_status: d.owner_status, failed: d.failed, proof_json: d.proof_json})
CREATE (r)-[:PRODUCED]->(x)
CREATE (x)-[:FOR]->(p)
RETURN count(x) AS duties;

// L3: open an approval task for a drafted notice and attach the playbook (lab)
UNWIND $tasks AS t
MATCH (d:Duty {id: t.duty_id})
CREATE (k:Task {id: t.id, kind: t.kind, state: 'OPEN', created_at: $now, created_by_agent: t.agent,
                draft_title: t.draft_title, draft_body: t.draft_body, draft_source: t.draft_source})
CREATE (k)-[:ABOUT]->(d)
WITH k, t
OPTIONAL MATCH (pb:Playbook {kind: t.kind})
FOREACH (x IN CASE WHEN pb IS NULL THEN [] ELSE [pb] END | CREATE (k)-[:FOLLOWS]->(x))
RETURN count(k) AS tasks;

// L4: claim a task with a 2-minute lease; stale leases return to the pool (lab or hs)
MATCH (t:Task {id: $task_id})
WHERE t.state = 'OPEN' OR (t.state = 'CLAIMED' AND t.lease_until < $now)
SET t.state = 'CLAIMED', t.lease_until = $now + 120000, t.claimed_by = $claimer
RETURN t.id AS claimed;

// L5: approve a notice: the only path by which a Notice exists. Signed Event; Task done. (lab)
MATCH (k:Task {id: $task_id})-[ab:ABOUT]->(d:Duty)-[f:FOR]->(p:Person)
WHERE k.state IN ['OPEN', 'CLAIMED', 'AWAITING_APPROVAL'] AND d.verdict IN ['DIRECT_NOTICE', 'VIA_FAMILY_LETTER']
SET k.state = 'DONE', k.done_at = $now
CREATE (n:Notice {id: $notice_id, pid: p.pid, vcv: $vcv, cls: $cls, notice_type: d.notice_type, channel: d.channel,
                  release: $release, approved_by: $approver_id, approved_at: $now, body: k.draft_body})
CREATE (d)-[:BECAME]->(n)
CREATE (p)-[:WAS_NOTIFIED]->(n)
CREATE (e:Event {id: $event_id, kind: 'APPROVED', at: $now, by: $approver_id, by_name: $approver_name})
CREATE (e)-[:ON]->(k)
RETURN n.id AS notice_id;

// L6: reject or route a task; signed Event; nothing leaves the system (lab or hs)
MATCH (k:Task {id: $task_id})
WHERE k.state IN ['OPEN', 'CLAIMED', 'AWAITING_APPROVAL']
SET k.state = 'DONE', k.done_at = $now, k.outcome = $outcome
CREATE (e:Event {id: $event_id, kind: $event_kind, at: $now, by: $by, by_name: $by_name, reason: $reason})
CREATE (e)-[:ON]->(k)
RETURN k.id AS task_id;

// L7: open tasks with what they are about (approval queue) (lab or hs, read-only)
MATCH (k:Task)
WHERE k.state IN $states
OPTIONAL MATCH (k)-[ab:ABOUT]->(x)
OPTIONAL MATCH (k)-[fo:FOLLOWS]->(pb:Playbook)
OPTIONAL MATCH (k)-[hf:HANDED_OFF_FROM]->(prev:Task)
RETURN k.id AS task_id, k.kind AS kind, k.state AS state, k.created_at AS created_at, k.created_by_agent AS agent,
       k.draft_title AS draft_title, k.draft_body AS draft_body, labels(x)[0] AS about_kind,
       coalesce(x.id, x.pid) AS about_id, x.verdict AS verdict, pb.steps AS playbook, prev.id AS handed_off_from
ORDER BY created_at DESC
LIMIT $limit;

// L8: write a cross-tenant handoff into the TARGET graph (minimum-necessary payload, lease fields) (lab or hs)
MERGE (h:Handoff {id: $handoff_id})
ON CREATE SET h.kind = $kind, h.from_graph = $from_graph, h.pid = $pid, h.vcv = $vcv, h.payload_json = $payload_json,
              h.state = 'OPEN', h.attempts = 0, h.created_at = $now
RETURN h.id AS handoff_id, h.state AS state;

// L9: handoffs ready for a worker (open, or claimed with an expired lease) (lab or hs, read-only)
MATCH (h:Handoff)
WHERE h.state = 'OPEN' OR (h.state = 'CLAIMED' AND h.lease_until < $now)
RETURN h.id AS handoff_id, h.kind AS kind, h.pid AS pid, h.vcv AS vcv, h.payload_json AS payload_json, h.attempts AS attempts
ORDER BY h.created_at ASC
LIMIT $limit;

// L10: claim a handoff with a 60 s lease; at most 5 attempts (lab or hs)
MATCH (h:Handoff {id: $handoff_id})
WHERE (h.state = 'OPEN' OR (h.state = 'CLAIMED' AND h.lease_until < $now)) AND h.attempts < 5
SET h.state = 'CLAIMED', h.lease_until = $now + 60000, h.claimed_by = $agent, h.attempts = h.attempts + 1
RETURN h.id AS claimed, h.attempts AS attempts;

// L11: complete a handoff with its result (the reply is a new Handoff written into the sender's graph) (lab or hs)
MATCH (h:Handoff {id: $handoff_id})
WHERE h.state = 'CLAIMED' AND h.claimed_by = $agent
SET h.state = 'DONE', h.done_at = $now, h.result_json = $result_json
RETURN h.id AS done;

// L17: read one handoff (the sender polls for the reply written into its own graph) (lab or hs, read-only)
MATCH (h:Handoff {id: $handoff_id})
RETURN h.id AS handoff_id, h.kind AS kind, h.state AS state, h.payload_json AS payload_json, h.result_json AS result_json,
       h.attempts AS attempts;

// L18: open a task about a decision, assigned to a clinician (idempotent on task id) (hs)
MATCH (d:Decision {id: $about_id})
MERGE (k:Task {id: $task_id})
ON CREATE SET k.kind = $kind, k.state = 'OPEN', k.created_at = $now, k.created_by_agent = $agent,
              k.assignee_id = $assignee_id, k.draft_title = $draft_title, k.draft_body = $draft_body
MERGE (k)-[:ABOUT]->(d)
WITH k
OPTIONAL MATCH (c:Clinician {id: $assignee_id})
FOREACH (x IN CASE WHEN c IS NULL THEN [] ELSE [c] END | MERGE (k)-[:ASSIGNED_TO]->(x))
WITH k
OPTIONAL MATCH (pb:Playbook {kind: $kind})
FOREACH (x IN CASE WHEN pb IS NULL THEN [] ELSE [pb] END | MERGE (k)-[:FOLLOWS]->(x))
RETURN k.id AS task_id;

// L19: open a task about a handoff (ORPHAN_DUTY, DELIVER_NOTICE, HANDOFF_FAILED), assigned to a clinician when one is
// given (idempotent on task id) (hs or lab)
MATCH (h:Handoff {id: $about_id})
MERGE (k:Task {id: $task_id})
ON CREATE SET k.kind = $kind, k.state = 'OPEN', k.created_at = $now, k.created_by_agent = $agent,
              k.assignee_id = $assignee_id, k.draft_title = $draft_title, k.draft_body = $draft_body
MERGE (k)-[:ABOUT]->(h)
WITH k
OPTIONAL MATCH (c:Clinician {id: $assignee_id})
FOREACH (x IN CASE WHEN c IS NULL THEN [] ELSE [c] END | MERGE (k)-[:ASSIGNED_TO]->(x))
WITH k
OPTIONAL MATCH (pb:Playbook {kind: $kind})
FOREACH (x IN CASE WHEN pb IS NULL THEN [] ELSE [pb] END | MERGE (k)-[:FOLLOWS]->(x))
RETURN k.id AS task_id;

// L20: open a task about a reconsideration item (idempotent on task id) (lab)
MATCH (r:Recon {id: $about_id})
MERGE (k:Task {id: $task_id})
ON CREATE SET k.kind = 'RECONSIDER_SUBMISSION', k.state = 'OPEN', k.created_at = $now, k.created_by_agent = 'curator',
              k.draft_title = $draft_title, k.draft_body = $draft_body
MERGE (k)-[:ABOUT]->(r)
WITH k
OPTIONAL MATCH (pb:Playbook {kind: 'RECONSIDER_SUBMISSION'})
FOREACH (x IN CASE WHEN pb IS NULL THEN [] ELSE [pb] END | MERGE (k)-[:FOLLOWS]->(x))
RETURN k.id AS task_id;

// L21: give up on a handoff after 5 attempts (sweeper) (lab or hs)
MATCH (h:Handoff {id: $handoff_id})
WHERE h.state <> 'DONE' AND h.state <> 'FAILED' AND h.attempts >= 5
SET h.state = 'FAILED', h.done_at = $now, h.result_json = $result_json
RETURN h.id AS failed;

// L12: open a reconsideration item (lab-side memory of a discordance; idempotent per SCV and release) (lab)
MERGE (r:Recon {id: $recon_id})
ON CREATE SET r.scv = $scv, r.vcv = $vcv, r.gene = $gene, r.opened_cls = $opened_cls, r.opened_version = $opened_version,
              r.panel_cls = $panel_cls, r.panel = $panel, r.opened_release = $release, r.opened_at = $now
RETURN r.id AS recon_id;

// L13: close a reconsideration item with the evidence from a later archive (append-only Event) (lab)
MATCH (r:Recon {id: $recon_id})
MERGE (e:Event {id: $event_id})
ON CREATE SET e.kind = 'RECON_CLOSED', e.at = $now, e.release = $release, e.outcome = $outcome,
              e.new_cls = $new_cls, e.new_version = $new_version
MERGE (e)-[:ON]->(r)
RETURN e.id AS event_id;

// L14: reconsideration items still open (no RECON_CLOSED event) (lab, read-only)
MATCH (r:Recon)
OPTIONAL MATCH (e:Event {kind: 'RECON_CLOSED'})-[on:ON]->(r)
WITH r, e, on
WHERE e IS NULL
RETURN r.id AS recon_id, r.scv AS scv, r.vcv AS vcv, r.gene AS gene, r.opened_cls AS opened_cls,
       r.opened_version AS opened_version, r.panel_cls AS panel_cls, r.panel AS panel, r.opened_release AS opened_release
ORDER BY opened_release, gene;

// L15: hand a task from one agent to the next (Track 2 handoff inside a tenant) (lab or hs)
MATCH (prev:Task {id: $prev_task_id})
CREATE (k:Task {id: $task_id, kind: $kind, state: 'OPEN', created_at: $now, created_by_agent: $agent,
                draft_title: $draft_title, draft_body: $draft_body})
CREATE (k)-[:HANDED_OFF_FROM]->(prev)
SET prev.state = 'AWAITING_APPROVAL'
WITH k
OPTIONAL MATCH (pb:Playbook {kind: $kind})
FOREACH (x IN CASE WHEN pb IS NULL THEN [] ELSE [pb] END | CREATE (k)-[:FOLLOWS]->(x))
RETURN k.id AS task_id;

// L16: record a conversation turn (MCP or web), linked to the run it produced when there is one (lab)
MERGE (c:Conversation {id: $conversation_id})
ON CREATE SET c.channel = $channel, c.started_at = $now
CREATE (t:Turn {id: $turn_id, tool: $tool, args_json: $args_json, summary: $summary, at: $now})
CREATE (c)-[:HAS_TURN]->(t)
WITH t
OPTIONAL MATCH (r:Run {id: $run_id})
FOREACH (x IN CASE WHEN r IS NULL THEN [] ELSE [r] END | CREATE (t)-[:PRODUCED]->(x))
RETURN t.id AS turn_id;

// ===========================================================================
// TENANT VIEWS AND TRACES
// ===========================================================================

// T1: decision trace for one duty: the run, the class change it came from, the proof, the task, who approved (lab, read-only)
MATCH (r:Run)-[pr:PRODUCED]->(d:Duty {id: $duty_id})-[f:FOR]->(p:Person)
OPTIONAL MATCH (k:Task)-[ab:ABOUT]->(d)
OPTIONAL MATCH (e:Event)-[on:ON]->(k)
OPTIONAL MATCH (d)-[bc:BECAME]->(n:Notice)
RETURN r.id AS run_id, r.change_id AS change_id, r.release AS release, r.from_cls AS from_cls, r.to_cls AS to_cls,
       p.pid AS pid, p.label AS label, d.verdict AS verdict, d.notice_type AS notice_type, d.channel AS channel,
       d.failed AS failed, d.proof_json AS proof_json, d.owner_id AS owner_id, d.owner_status AS owner_status,
       k.id AS task_id, k.state AS task_state,
       collect(DISTINCT {kind: e.kind, at: e.at, by: e.by_name}) AS events, n.id AS notice_id;

// T2: latest runs (lab, read-only)
MATCH (r:Run)
OPTIONAL MATCH (r)-[pr:PRODUCED]->(d:Duty)
RETURN r.id AS run_id, r.change_id AS change_id, r.vcv AS vcv, r.release AS release, r.kind AS kind, r.at AS at,
       count(d) AS duties, sum(CASE WHEN d.verdict IN ['DIRECT_NOTICE', 'VIA_FAMILY_LETTER'] THEN 1 ELSE 0 END) AS notices
ORDER BY at DESC
LIMIT $limit;

// T3: lab overview counts (lab, read-only)
MATCH (p:Person)
OPTIONAL MATCH (p)-[hr:HAS_REPORT]->(rep:Report)
RETURN count(DISTINCT p) AS people, count(DISTINCT p.family) AS families, count(DISTINCT rep) AS reports,
       count(DISTINCT CASE WHEN p.synthetic = true THEN p END) AS synthetic_people;

// T4: variants this lab has reported (to intersect with a release's class changes) (lab, read-only)
MATCH (vr:VariantRef)<-[ci:CITES]-(rep:Report)
RETURN vr.vcv AS vcv, count(rep) AS reports, collect(DISTINCT rep.scv) AS scvs
ORDER BY reports DESC;

// T5: duties of one run (the duty map table) (lab, read-only)
MATCH (r:Run {id: $run_id})-[pr:PRODUCED]->(d:Duty)-[f:FOR]->(p:Person)
RETURN d.id AS duty_id, p.pid AS pid, p.label AS label, d.role AS role, d.verdict AS verdict, d.notice_type AS notice_type,
       d.channel AS channel, d.degree AS degree, d.source_pid AS source_pid, d.owner_id AS owner_id,
       d.owner_status AS owner_status, d.failed AS failed, d.proof_json AS proof_json
ORDER BY CASE d.role WHEN 'CARRIER' THEN 0 ELSE 1 END, degree, pid;

// ===========================================================================
// GRAPH ALGORITHMS AS AGENT TOOLS
// ===========================================================================

// A1: families as connected components of the pedigree graph (algo.WCC); does not trust the family property (lab, read-only)
CALL algo.WCC({nodeLabels: ['Person'], relationshipTypes: ['PARENT_OF']})
YIELD node, componentId
WITH componentId, collect(node.pid) AS members
RETURN componentId, size(members) AS size, members[0..25] AS sample
ORDER BY size DESC
LIMIT $limit;

// A2: multi-carrier families for one variant (two probands in one connected family): their duty maps are merged so
// no relative is notified twice (algo.WCC) (lab, read-only)
CALL algo.WCC({nodeLabels: ['Person'], relationshipTypes: ['PARENT_OF']})
YIELD node, componentId
WITH componentId, node
WHERE $vcv IN node.pos
WITH componentId, collect(node.pid) AS carriers
WHERE size(carriers) >= 2
RETURN componentId, carriers;

// A3: descendants reachable from a founder within 4 generations (algo.BFS follows outgoing PARENT_OF edges only),
// used to draw the at-risk cascade below a carrier (lab, read-only)
MATCH (f:Person {pid: $pid})
CALL algo.BFS(f, 4, 'PARENT_OF')
YIELD nodes
RETURN [n IN nodes | n.pid] AS descendants;

// ===========================================================================
// SEEDING AND GENERATOR WRITES (lab and hs graphs)
// ===========================================================================

// P1: people (all synthetic, labelled fictional) (lab)
UNWIND $rows AS r
CREATE (:Person {pid: r.pid, label: r.label, family: r.family, sex: r.sex, birth_year: r.birth_year,
                 deceased: r.deceased, contact_pref: r.contact_pref, family_share: r.family_share,
                 recontact_ok: r.recontact_ok, pos: [], neg: [], synthetic: true})
RETURN count(*) AS people;

// P2: parent-child edges (lab)
UNWIND $rows AS r
MATCH (a:Person {pid: r.parent}), (b:Person {pid: r.child})
CREATE (a)-[:PARENT_OF]->(b)
RETURN count(*) AS edges;

// P3: lab reports citing a variant (the lab's own classification at issue time), carriers become sources (lab)
UNWIND $rows AS r
MATCH (p:Person {pid: r.pid})
MERGE (vr:VariantRef {vcv: r.vcv})
ON CREATE SET vr.gene = r.gene
CREATE (rep:Report {id: r.id, issued: r.issued, vcv: r.vcv, scv: r.scv, scv_version: r.scv_version,
                    class_at_issue: r.class_at_issue, ordering_clinician: r.ordering_clinician, hs_tenant: r.hs_tenant})
CREATE (p)-[:HAS_REPORT]->(rep)
CREATE (rep)-[:CITES]->(vr)
SET p.pos = CASE WHEN r.vcv IN p.pos THEN p.pos ELSE p.pos + [r.vcv] END
RETURN count(rep) AS reports;

// P4: test results (a negative test is what prunes a side of the family) (lab)
UNWIND $rows AS r
MATCH (p:Person {pid: r.pid})
CREATE (t:Test {id: r.id, vcv: r.vcv, result: r.result, date: r.date})
CREATE (p)-[:HAD_TEST]->(t)
SET p.neg = CASE WHEN r.result = 'NEG' AND NOT r.vcv IN p.neg THEN p.neg + [r.vcv] ELSE p.neg END,
    p.pos = CASE WHEN r.result = 'POS' AND NOT r.vcv IN p.pos THEN p.pos + [r.vcv] ELSE p.pos END
RETURN count(t) AS tests;

// P5: jurisdictions (illustrative rule set) and residence (lab)
UNWIND $jurisdictions AS j
MERGE (x:Jurisdiction {code: j.code})
SET x.name = j.name, x.direct_allowed = j.direct_allowed, x.note = j.note, x.illustrative = true
WITH count(x) AS n
UNWIND $residence AS r
MATCH (p:Person {pid: r.pid}), (j:Jurisdiction {code: r.code})
CREATE (p)-[:RESIDES_IN]->(j)
RETURN count(*) AS residents;

// P6: lab tenant identity and playbooks (procedural memory) (lab or hs)
MERGE (o:Org {id: $org_id})
SET o.name = $org_name, o.kind = $org_kind, o.mirrors_submitter = $mirrors_submitter, o.synthetic = true
WITH o
UNWIND $playbooks AS pb
MERGE (x:Playbook {kind: pb.kind})
SET x.steps = pb.steps
RETURN count(x) AS playbooks;

// P7: clinicians and clinics (hs)
UNWIND $clinicians AS c
CREATE (:Clinician {id: c.id, name: c.name, role: c.role, active: c.active, left_at: c.left_at, synthetic: true})
WITH count(*) AS n
UNWIND $clinics AS k
CREATE (:Clinic {id: k.id, name: k.name, open: k.open, closed_at: k.closed_at, synthetic: true})
RETURN count(*) AS clinics;

// P8: clinician practiced at clinic (hs)
UNWIND $rows AS r
MATCH (a:Clinician {id: r.from}), (b:Clinic {id: r.to})
CREATE (a)-[:PRACTICED_AT {at: r.at, until: r.until}]->(b)
RETURN count(*) AS edges;

// P9: panel handed from one clinician to another (hs)
UNWIND $rows AS r
MATCH (a:Clinician {id: r.from}), (b:Clinician {id: r.to})
CREATE (a)-[:HANDED_PANEL_TO {at: r.at}]->(b)
RETURN count(*) AS edges;

// P10: clinic succeeded by clinic (hs)
UNWIND $rows AS r
MATCH (a:Clinic {id: r.from}), (b:Clinic {id: r.to})
CREATE (a)-[:SUCCEEDED_BY {at: r.at}]->(b)
RETURN count(*) AS edges;

// P11: clinic led by clinician (until null = current lead) (hs)
UNWIND $rows AS r
MATCH (a:Clinic {id: r.from}), (b:Clinician {id: r.to})
CREATE (a)-[:LED_BY {at: r.at, until: r.until}]->(b)
RETURN count(*) AS edges;

// P12: patients and their clinician of record (hs)
UNWIND $patients AS r
MERGE (pt:Patient {pid: r.pid})
WITH pt, r
MATCH (c:Clinician {id: r.clinician})
CREATE (pt)-[:UNDER_CARE {from: r.from, until: r.until}]->(c)
RETURN count(*) AS links;

// P13: teams, memberships and roles (hs)
UNWIND $members AS m
MERGE (t:Team {id: m.team_id})
ON CREATE SET t.name = m.team_name
WITH t, m
MATCH (c:Clinician {id: m.clinician})
CREATE (c)-[:MEMBER_OF]->(t)
WITH count(*) AS n
MATCH (md:Clinician {id: $medical_director})
MERGE (r:Role {name: 'medical_director'})
MERGE (r)-[:HELD_BY]->(md)
RETURN n AS memberships;

// P14: decisions that rested on a variant class (hs)
UNWIND $rows AS r
MATCH (o:Clinician {id: r.owner}), (a:Clinician {id: r.approved_by})
MERGE (vr:VariantRef {vcv: r.vcv})
CREATE (d:Decision {id: r.id, pid: r.pid, kind: r.kind, summary: r.summary, made_at: r.made_at, synthetic: true})
CREATE (d)-[:RESTED_ON {vcv: r.vcv, scv: r.scv, cls_at_time: r.cls_at_time, release: r.release}]->(vr)
CREATE (d)-[:OWNED_BY]->(o)
CREATE (d)-[:APPROVED_BY]->(a)
MERGE (s:Source {url: r.source_url})
CREATE (d)-[:CITES]->(s)
RETURN count(d) AS decisions;

// P15: historical notices for the demo ledger (seed only; at runtime a Notice is created only by L5 after approval) (lab)
UNWIND $rows AS r
MATCH (p:Person {pid: r.pid})
CREATE (n:Notice {id: r.id, pid: r.pid, vcv: r.vcv, cls: r.cls, notice_type: r.notice_type, channel: r.channel,
                  release: r.release, approved_by: r.approved_by, approved_at: r.approved_at, body: r.body, seeded: true})
CREATE (p)-[:WAS_NOTIFIED]->(n)
RETURN count(n) AS notices;
