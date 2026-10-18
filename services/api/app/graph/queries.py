"""Cypher copied verbatim from docs/queries.cypher. Do not edit by hand.

Names come from the block headers in that file.
"""

# fmt: off

QUERIES: dict[str, str] = {
    'SCHEMA_KB': (
        """\
CREATE INDEX FOR (v:Variant) ON (v.vcv);
CREATE INDEX FOR (g:Gene) ON (g.symbol);
CREATE INDEX FOR (s:SCV) ON (s.acc);
CREATE INDEX FOR (x:SCVVersion) ON (x.id);
CREATE INDEX FOR (u:Submitter) ON (u.id);
CREATE INDEX FOR (r:Release) ON (r.id);
CREATE INDEX FOR (c:ClassChange) ON (c.id);
CREATE INDEX FOR (c:ClassChange) ON (c.release);
CREATE INDEX FOR (l:LiveLookup) ON (l.vcv);
"""
    ),
    'SCHEMA_LAB': (
        """\
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
"""
    ),
    'SCHEMA_HS': (
        """\
CREATE INDEX FOR (c:Clinician) ON (c.id);
CREATE INDEX FOR (c:Clinic) ON (c.id);
CREATE INDEX FOR (p:Patient) ON (p.pid);
CREATE INDEX FOR (d:Decision) ON (d.id);
CREATE INDEX FOR (v:VariantRef) ON (v.vcv);
CREATE INDEX FOR (t:Task) ON (t.id);
CREATE INDEX FOR (h:Handoff) ON (h.id);
"""
    ),
    'K1': (
        """\
UNWIND $rows AS r
MERGE (g:Gene {symbol: r.symbol})
SET g.inheritance = r.inheritance, g.review_always = r.review_always, g.review_reason = r.review_reason,
    g.category = r.category, g.condition = r.condition, g.sf_version = r.sf_version
RETURN count(g) AS genes;
"""
    ),
    'K2': (
        """\
UNWIND $rows AS r
MATCH (g:Gene {symbol: r.gene})
MERGE (v:Variant {vcv: r.vcv})
SET v.name = r.name, v.gene = r.gene, v.agg_cls = r.agg_cls, v.agg_cls_raw = r.agg_cls_raw,
    v.agg_review = r.agg_review, v.agg_stars = r.agg_stars, v.agg_release = $release
MERGE (v)-[:IN_GENE]->(g)
RETURN count(v) AS variants;
"""
    ),
    'K3': (
        """\
MERGE (r:Release {id: $release})
ON CREATE SET r.kind = $kind, r.file = $file, r.file_sha256 = $file_sha256, r.rows = $rows, r.loaded_at = $now
RETURN r.id AS release, r.loaded_at AS loaded_at;
"""
    ),
    'K4': (
        """\
UNWIND $rows AS r
MATCH (v:Variant {vcv: r.vcv})
MERGE (u:Submitter {id: r.submitter_id})
ON CREATE SET u.name = r.submitter
MERGE (s:SCV {acc: r.acc})
ON CREATE SET s.vcv = r.vcv, s.submitter_id = r.submitter_id
MERGE (s)-[:ABOUT]->(v)
MERGE (s)-[:SUBMITTED_BY]->(u)
RETURN count(s) AS scvs;
"""
    ),
    'K5': (
        """\
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
"""
    ),
    'K6': (
        """\
UNWIND $accs AS acc
MATCH (s:SCV {acc: acc})-[hv:HAS_VERSION]->(cur:SCVVersion)
WHERE cur.superseded_in IS NULL
SET cur.superseded_in = $release, cur.withdrawn_in = $release
RETURN count(cur) AS withdrawn;
"""
    ),
    'K7': (
        """\
MATCH (u:Submitter {id: $submitter_id})<-[sb:SUBMITTED_BY]-(s:SCV)<-[o:OF]-(cc:ClassChange {release: $release})
MATCH (s)-[ab:ABOUT]->(v:Variant)-[ig:IN_GENE]->(g:Gene)
RETURN cc.id AS change_id, v.vcv AS vcv, v.name AS variant, g.symbol AS gene, g.inheritance AS inheritance,
       s.acc AS scv, cc.from_cls AS from_cls, cc.to_cls AS to_cls, cc.from_version AS from_version,
       cc.to_version AS to_version, cc.to_dle AS submitter_evaluated, cc.kind AS kind, u.name AS submitter
ORDER BY CASE cc.kind WHEN 'UP_TO_ACTIONABLE' THEN 0 WHEN 'DOWN_FROM_ACTIONABLE' THEN 1
                      WHEN 'VUS_RESOLVED_BENIGN' THEN 2 ELSE 3 END, g.symbol, v.vcv
LIMIT $limit;
"""
    ),
    'K8': (
        """\
MATCH (cc:ClassChange {release: $release})-[o:OF]->(s:SCV)-[sb:SUBMITTED_BY]->(u:Submitter)
RETURN u.id AS submitter_id, u.name AS submitter, count(cc) AS changes,
       sum(CASE WHEN cc.kind IN ['UP_TO_ACTIONABLE', 'DOWN_FROM_ACTIONABLE'] THEN 1 ELSE 0 END) AS actionable_changes
ORDER BY actionable_changes DESC, changes DESC, submitter ASC
LIMIT $limit;
"""
    ),
    'K9': (
        """\
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
"""
    ),
    'K10': (
        """\
MATCH (cc:ClassChange {vcv: $vcv})-[o:OF]->(s:SCV)-[sb:SUBMITTED_BY]->(u:Submitter)
RETURN cc.id AS change_id, cc.release AS release, s.acc AS scv, u.name AS submitter, cc.from_cls AS from_cls,
       cc.to_cls AS to_cls, cc.kind AS kind, cc.to_dle AS submitter_evaluated
ORDER BY release DESC, scv ASC
LIMIT 100;
"""
    ),
    'K11': (
        """\
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
"""
    ),
    'K12': (
        """\
UNWIND $items AS it
MATCH (s:SCV {acc: it.scv})-[hv:HAS_VERSION]->(x:SCVVersion)
WHERE x.first_release <= $as_of AND (x.superseded_in IS NULL OR x.superseded_in > $as_of)
RETURN it.recon_id AS recon_id, s.acc AS scv, x.version AS version, x.cls AS cls, x.dle AS evaluated,
       x.first_release AS since_release, x.cls <> it.opened_cls AS class_changed, x.version <> it.opened_version AS version_changed;
"""
    ),
    'K13': (
        """\
MERGE (l:LiveLookup {vcv: $vcv})
SET l.fetched_at = $now, l.accession = $accession, l.name = $name, l.gene = $gene, l.agg_cls = $agg_cls,
    l.agg_review = $agg_review, l.submissions_json = $submissions_json, l.date_last_updated = $date_last_updated
RETURN l.vcv AS vcv;
"""
    ),
    'K14': (
        """\
MATCH (r:Release)
RETURN r.id AS release, r.kind AS kind, r.rows AS rows, r.loaded_at AS loaded_at
ORDER BY release ASC;
"""
    ),
    'K15': (
        """\
MATCH (cc:ClassChange {release: $release})-[o:OF]->(s:SCV)-[ab:ABOUT]->(v:Variant)-[ig:IN_GENE]->(g:Gene)
RETURN cc.kind AS kind, g.inheritance = 'AD' AND NOT g.review_always AS pruning_valid, count(cc) AS changes
ORDER BY kind;
"""
    ),
    'K16': (
        """\
UNWIND $accs AS acc
MATCH (s:SCV {acc: acc})-[hv:HAS_VERSION]->(x:SCVVersion)
WHERE x.superseded_in IS NULL
RETURN s.acc AS scv, x.version AS version, x.cls AS cls;
"""
    ),
    'K17': (
        """\
MATCH (cc:ClassChange {id: $change_id})-[o:OF]->(s:SCV)-[ab:ABOUT]->(v:Variant)-[ig:IN_GENE]->(g:Gene)
MATCH (s)-[sb:SUBMITTED_BY]->(u:Submitter)
RETURN cc.id AS change_id, cc.release AS release, cc.kind AS kind, cc.from_cls AS from_cls, cc.to_cls AS to_cls,
       cc.from_version AS from_version, cc.to_version AS to_version, cc.to_dle AS submitter_evaluated,
       s.acc AS scv, u.id AS submitter_id, u.name AS submitter, v.vcv AS vcv, v.name AS variant,
       g.symbol AS gene, g.inheritance AS inheritance, g.review_always AS review_always, g.review_reason AS review_reason;
"""
    ),
    'X1': (
        """\
MATCH (vr:VariantRef {vcv: $vcv})<-[ci:CITES]-(rep:Report)<-[hr:HAS_REPORT]-(c:Person)
RETURN c.pid AS pid, c.label AS label, c.family AS family, coalesce(c.deceased, false) AS deceased,
       coalesce(c.recontact_ok, false) AS recontact_ok, c.family_share AS family_share,
       rep.id AS report_id, rep.issued AS issued, rep.class_at_issue AS class_at_issue, rep.scv AS scv,
       rep.ordering_clinician AS ordering_clinician, rep.hs_tenant AS hs_tenant
ORDER BY family, pid;
"""
    ),
    'X2': (
        """\
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
"""
    ),
    'X3': (
        """\
MATCH (p:Person)-[ht:HAD_TEST]->(t:Test {vcv: $vcv})
RETURN p.pid AS pid, p.label AS label, t.result AS result, t.date AS date
ORDER BY date;
"""
    ),
    'X4': (
        """\
MATCH (p:Person {family: $family})
OPTIONAL MATCH (p)-[po:PARENT_OF]->(c:Person)
RETURN p.pid AS pid, p.label AS label, p.sex AS sex, p.birth_year AS birth_year, coalesce(p.deceased, false) AS deceased,
       p.pos AS pos, p.neg AS neg, p.contact_pref AS contact_pref, p.family_share AS family_share,
       collect(c.pid) AS children;
"""
    ),
    'C1': (
        """\
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
"""
    ),
    'C2': (
        """\
MATCH (p:Person {pid: $pid})
CREATE (c:Consent {id: $consent_id, kind: $kind, value: $value, at: $now, recorded_by: $recorded_by})
CREATE (p)-[:GAVE]->(c)
SET p.family_share = CASE WHEN $kind = 'family_share' THEN $value ELSE p.family_share END,
    p.contact_pref = CASE WHEN $kind = 'contact_pref' THEN $value ELSE p.contact_pref END,
    p.recontact_ok = CASE WHEN $kind = 'recontact' THEN $value = 'yes' ELSE p.recontact_ok END
RETURN p.pid AS pid, p.family_share AS family_share, p.contact_pref AS contact_pref, p.recontact_ok AS recontact_ok;
"""
    ),
    'C3': (
        """\
MATCH (p:Person {pid: $pid})-[g:GAVE]->(c:Consent)
RETURN c.kind AS kind, c.value AS value, c.at AS at, c.recorded_by AS recorded_by
ORDER BY at DESC;
"""
    ),
    'W1': (
        """\
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
"""
    ),
    'W2': (
        """\
MATCH (c0:Clinician {id: $clinician_id})
MATCH p = (c0)-[:HANDED_PANEL_TO|PRACTICED_AT|SUCCEEDED_BY|LED_BY*0..5]->(n)
WHERE NOT (n)-[:HANDED_PANEL_TO|SUCCEEDED_BY]->() AND NOT (n:Clinician AND n.active = true)
WITH DISTINCT n
RETURN labels(n)[0] AS kind, coalesce(n.name, n.id) AS name, n.active AS active, n.left_at AS left_at,
       n.open AS open, n.closed_at AS closed_at;
"""
    ),
    'W3': (
        """\
MATCH (pt:Patient {pid: $pid})-[u:UNDER_CARE]->(c:Clinician)
WHERE c.active = true AND u.until IS NULL
RETURN c.id AS owner_id, c.name AS owner, c.role AS role, u.from AS since
ORDER BY since DESC
LIMIT 1;
"""
    ),
    'W4': (
        """\
MATCH (r:Role {name: 'medical_director'})-[h:HELD_BY]->(c:Clinician)
RETURN c.id AS owner_id, c.name AS owner;
"""
    ),
    'W5': (
        """\
MATCH (c:Clinician)
OPTIONAL MATCH (c)-[m:MEMBER_OF]->(t:Team)
OPTIONAL MATCH (pt:Patient)-[u:UNDER_CARE]->(c)
WITH c, t, count(DISTINCT CASE WHEN u.until IS NULL THEN pt END) AS patients
RETURN c.id AS id, c.name AS name, c.role AS role, c.active AS active, c.left_at AS left_at,
       t.name AS team, patients
ORDER BY active DESC, team, name;
"""
    ),
    'D1': (
        """\
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
"""
    ),
    'D2': (
        """\
MATCH (d:Decision {id: $decision_id})
MERGE (e:Event {id: $event_id})
ON CREATE SET e.kind = 'REOPENED', e.at = $now, e.reason = $reason, e.release = $release, e.change_id = $change_id
MERGE (e)-[:ON]->(d)
RETURN e.id AS event_id;
"""
    ),
    'D3': (
        """\
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
"""
    ),
    'D4': (
        """\
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
"""
    ),
    'D5': (
        """\
MATCH (e:Event {kind: 'REOPENED'})-[on:ON]->(d:Decision)
OPTIONAL MATCH (newer:Decision)-[sp:SUPERSEDES]->(d)
WITH e, d, newer, sp
WHERE newer IS NULL
RETURN d.id AS decision_id, d.pid AS pid, d.kind AS kind, d.summary AS summary, e.at AS reopened_at,
       e.reason AS reason, e.change_id AS change_id
ORDER BY reopened_at DESC;
"""
    ),
    'L1': (
        """\
MATCH (p:Person)-[wn:WAS_NOTIFIED]->(n:Notice {vcv: $vcv})
RETURN p.pid AS pid, p.contact_pref AS contact_pref, coalesce(p.deceased, false) AS deceased, n.id AS notice_id,
       n.cls AS cls, n.notice_type AS notice_type, n.channel AS channel, n.release AS release, n.approved_at AS approved_at
ORDER BY approved_at DESC;
"""
    ),
    'L2': (
        """\
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
"""
    ),
    'L3': (
        """\
UNWIND $tasks AS t
MATCH (d:Duty {id: t.duty_id})
CREATE (k:Task {id: t.id, kind: t.kind, state: 'OPEN', created_at: $now, created_by_agent: t.agent,
                draft_title: t.draft_title, draft_body: t.draft_body, draft_source: t.draft_source})
CREATE (k)-[:ABOUT]->(d)
WITH k, t
OPTIONAL MATCH (pb:Playbook {kind: t.kind})
FOREACH (x IN CASE WHEN pb IS NULL THEN [] ELSE [pb] END | CREATE (k)-[:FOLLOWS]->(x))
RETURN count(k) AS tasks;
"""
    ),
    'L4': (
        """\
MATCH (t:Task {id: $task_id})
WHERE t.state = 'OPEN' OR (t.state = 'CLAIMED' AND t.lease_until < $now)
SET t.state = 'CLAIMED', t.lease_until = $now + 120000, t.claimed_by = $claimer
RETURN t.id AS claimed;
"""
    ),
    'L5': (
        """\
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
"""
    ),
    'L6': (
        """\
MATCH (k:Task {id: $task_id})
WHERE k.state IN ['OPEN', 'CLAIMED', 'AWAITING_APPROVAL']
SET k.state = 'DONE', k.done_at = $now, k.outcome = $outcome
CREATE (e:Event {id: $event_id, kind: $event_kind, at: $now, by: $by, by_name: $by_name, reason: $reason})
CREATE (e)-[:ON]->(k)
RETURN k.id AS task_id;
"""
    ),
    'L7': (
        """\
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
"""
    ),
    'L8': (
        """\
MERGE (h:Handoff {id: $handoff_id})
ON CREATE SET h.kind = $kind, h.from_graph = $from_graph, h.pid = $pid, h.vcv = $vcv, h.payload_json = $payload_json,
              h.state = 'OPEN', h.attempts = 0, h.created_at = $now
RETURN h.id AS handoff_id, h.state AS state;
"""
    ),
    'L9': (
        """\
MATCH (h:Handoff)
WHERE h.state = 'OPEN' OR (h.state = 'CLAIMED' AND h.lease_until < $now)
RETURN h.id AS handoff_id, h.kind AS kind, h.pid AS pid, h.vcv AS vcv, h.payload_json AS payload_json, h.attempts AS attempts
ORDER BY h.created_at ASC
LIMIT $limit;
"""
    ),
    'L10': (
        """\
MATCH (h:Handoff {id: $handoff_id})
WHERE (h.state = 'OPEN' OR (h.state = 'CLAIMED' AND h.lease_until < $now)) AND h.attempts < 5
SET h.state = 'CLAIMED', h.lease_until = $now + 60000, h.claimed_by = $agent, h.attempts = h.attempts + 1
RETURN h.id AS claimed, h.attempts AS attempts;
"""
    ),
    'L11': (
        """\
MATCH (h:Handoff {id: $handoff_id})
WHERE h.state = 'CLAIMED' AND h.claimed_by = $agent
SET h.state = 'DONE', h.done_at = $now, h.result_json = $result_json
RETURN h.id AS done;
"""
    ),
    'L17': (
        """\
MATCH (h:Handoff {id: $handoff_id})
RETURN h.id AS handoff_id, h.kind AS kind, h.state AS state, h.payload_json AS payload_json, h.result_json AS result_json,
       h.attempts AS attempts;
"""
    ),
    'L18': (
        """\
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
"""
    ),
    'L19': (
        """\
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
"""
    ),
    'L20': (
        """\
MATCH (r:Recon {id: $about_id})
MERGE (k:Task {id: $task_id})
ON CREATE SET k.kind = 'RECONSIDER_SUBMISSION', k.state = 'OPEN', k.created_at = $now, k.created_by_agent = 'curator',
              k.draft_title = $draft_title, k.draft_body = $draft_body
MERGE (k)-[:ABOUT]->(r)
WITH k
OPTIONAL MATCH (pb:Playbook {kind: 'RECONSIDER_SUBMISSION'})
FOREACH (x IN CASE WHEN pb IS NULL THEN [] ELSE [pb] END | MERGE (k)-[:FOLLOWS]->(x))
RETURN k.id AS task_id;
"""
    ),
    'L21': (
        """\
MATCH (h:Handoff {id: $handoff_id})
WHERE h.state <> 'DONE' AND h.state <> 'FAILED' AND h.attempts >= 5
SET h.state = 'FAILED', h.done_at = $now, h.result_json = $result_json
RETURN h.id AS failed;
"""
    ),
    'L12': (
        """\
MERGE (r:Recon {id: $recon_id})
ON CREATE SET r.scv = $scv, r.vcv = $vcv, r.gene = $gene, r.opened_cls = $opened_cls, r.opened_version = $opened_version,
              r.panel_cls = $panel_cls, r.panel = $panel, r.opened_release = $release, r.opened_at = $now
RETURN r.id AS recon_id;
"""
    ),
    'L13': (
        """\
MATCH (r:Recon {id: $recon_id})
MERGE (e:Event {id: $event_id})
ON CREATE SET e.kind = 'RECON_CLOSED', e.at = $now, e.release = $release, e.outcome = $outcome,
              e.new_cls = $new_cls, e.new_version = $new_version
MERGE (e)-[:ON]->(r)
RETURN e.id AS event_id;
"""
    ),
    'L14': (
        """\
MATCH (r:Recon)
OPTIONAL MATCH (e:Event {kind: 'RECON_CLOSED'})-[on:ON]->(r)
WITH r, e, on
WHERE e IS NULL
RETURN r.id AS recon_id, r.scv AS scv, r.vcv AS vcv, r.gene AS gene, r.opened_cls AS opened_cls,
       r.opened_version AS opened_version, r.panel_cls AS panel_cls, r.panel AS panel, r.opened_release AS opened_release
ORDER BY opened_release, gene;
"""
    ),
    'L15': (
        """\
MATCH (prev:Task {id: $prev_task_id})
CREATE (k:Task {id: $task_id, kind: $kind, state: 'OPEN', created_at: $now, created_by_agent: $agent,
                draft_title: $draft_title, draft_body: $draft_body})
CREATE (k)-[:HANDED_OFF_FROM]->(prev)
SET prev.state = 'AWAITING_APPROVAL'
WITH k
OPTIONAL MATCH (pb:Playbook {kind: $kind})
FOREACH (x IN CASE WHEN pb IS NULL THEN [] ELSE [pb] END | CREATE (k)-[:FOLLOWS]->(x))
RETURN k.id AS task_id;
"""
    ),
    'L16': (
        """\
MERGE (c:Conversation {id: $conversation_id})
ON CREATE SET c.channel = $channel, c.started_at = $now
CREATE (t:Turn {id: $turn_id, tool: $tool, args_json: $args_json, summary: $summary, at: $now})
CREATE (c)-[:HAS_TURN]->(t)
WITH t
OPTIONAL MATCH (r:Run {id: $run_id})
FOREACH (x IN CASE WHEN r IS NULL THEN [] ELSE [r] END | CREATE (t)-[:PRODUCED]->(x))
RETURN t.id AS turn_id;
"""
    ),
    'T1': (
        """\
MATCH (r:Run)-[pr:PRODUCED]->(d:Duty {id: $duty_id})-[f:FOR]->(p:Person)
OPTIONAL MATCH (k:Task)-[ab:ABOUT]->(d)
OPTIONAL MATCH (e:Event)-[on:ON]->(k)
OPTIONAL MATCH (d)-[bc:BECAME]->(n:Notice)
RETURN r.id AS run_id, r.change_id AS change_id, r.release AS release, r.from_cls AS from_cls, r.to_cls AS to_cls,
       p.pid AS pid, p.label AS label, d.verdict AS verdict, d.notice_type AS notice_type, d.channel AS channel,
       d.failed AS failed, d.proof_json AS proof_json, d.owner_id AS owner_id, d.owner_status AS owner_status,
       k.id AS task_id, k.state AS task_state,
       collect(DISTINCT {kind: e.kind, at: e.at, by: e.by_name}) AS events, n.id AS notice_id;
"""
    ),
    'T2': (
        """\
MATCH (r:Run)
OPTIONAL MATCH (r)-[pr:PRODUCED]->(d:Duty)
RETURN r.id AS run_id, r.change_id AS change_id, r.vcv AS vcv, r.release AS release, r.kind AS kind, r.at AS at,
       count(d) AS duties, sum(CASE WHEN d.verdict IN ['DIRECT_NOTICE', 'VIA_FAMILY_LETTER'] THEN 1 ELSE 0 END) AS notices
ORDER BY at DESC
LIMIT $limit;
"""
    ),
    'T3': (
        """\
MATCH (p:Person)
OPTIONAL MATCH (p)-[hr:HAS_REPORT]->(rep:Report)
RETURN count(DISTINCT p) AS people, count(DISTINCT p.family) AS families, count(DISTINCT rep) AS reports,
       count(DISTINCT CASE WHEN p.synthetic = true THEN p END) AS synthetic_people;
"""
    ),
    'T4': (
        """\
MATCH (vr:VariantRef)<-[ci:CITES]-(rep:Report)
RETURN vr.vcv AS vcv, count(rep) AS reports, collect(DISTINCT rep.scv) AS scvs
ORDER BY reports DESC;
"""
    ),
    'T5': (
        """\
MATCH (r:Run {id: $run_id})-[pr:PRODUCED]->(d:Duty)-[f:FOR]->(p:Person)
RETURN d.id AS duty_id, p.pid AS pid, p.label AS label, d.role AS role, d.verdict AS verdict, d.notice_type AS notice_type,
       d.channel AS channel, d.degree AS degree, d.source_pid AS source_pid, d.owner_id AS owner_id,
       d.owner_status AS owner_status, d.failed AS failed, d.proof_json AS proof_json
ORDER BY CASE d.role WHEN 'CARRIER' THEN 0 ELSE 1 END, degree, pid;
"""
    ),
    'A1': (
        """\
CALL algo.WCC({nodeLabels: ['Person'], relationshipTypes: ['PARENT_OF']})
YIELD node, componentId
WITH componentId, collect(node.pid) AS members
RETURN componentId, size(members) AS size, members[0..25] AS sample
ORDER BY size DESC
LIMIT $limit;
"""
    ),
    'A2': (
        """\
CALL algo.WCC({nodeLabels: ['Person'], relationshipTypes: ['PARENT_OF']})
YIELD node, componentId
WITH componentId, node
WHERE $vcv IN node.pos
WITH componentId, collect(node.pid) AS carriers
WHERE size(carriers) >= 2
RETURN componentId, carriers;
"""
    ),
    'A3': (
        """\
MATCH (f:Person {pid: $pid})
CALL algo.BFS(f, 4, 'PARENT_OF')
YIELD nodes
RETURN [n IN nodes | n.pid] AS descendants;
"""
    ),
    'P1': (
        """\
UNWIND $rows AS r
CREATE (:Person {pid: r.pid, label: r.label, family: r.family, sex: r.sex, birth_year: r.birth_year,
                 deceased: r.deceased, contact_pref: r.contact_pref, family_share: r.family_share,
                 recontact_ok: r.recontact_ok, pos: [], neg: [], synthetic: true})
RETURN count(*) AS people;
"""
    ),
    'P2': (
        """\
UNWIND $rows AS r
MATCH (a:Person {pid: r.parent}), (b:Person {pid: r.child})
CREATE (a)-[:PARENT_OF]->(b)
RETURN count(*) AS edges;
"""
    ),
    'P3': (
        """\
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
"""
    ),
    'P4': (
        """\
UNWIND $rows AS r
MATCH (p:Person {pid: r.pid})
CREATE (t:Test {id: r.id, vcv: r.vcv, result: r.result, date: r.date})
CREATE (p)-[:HAD_TEST]->(t)
SET p.neg = CASE WHEN r.result = 'NEG' AND NOT r.vcv IN p.neg THEN p.neg + [r.vcv] ELSE p.neg END,
    p.pos = CASE WHEN r.result = 'POS' AND NOT r.vcv IN p.pos THEN p.pos + [r.vcv] ELSE p.pos END
RETURN count(t) AS tests;
"""
    ),
    'P5': (
        """\
UNWIND $jurisdictions AS j
MERGE (x:Jurisdiction {code: j.code})
SET x.name = j.name, x.direct_allowed = j.direct_allowed, x.note = j.note, x.illustrative = true
WITH count(x) AS n
UNWIND $residence AS r
MATCH (p:Person {pid: r.pid}), (j:Jurisdiction {code: r.code})
CREATE (p)-[:RESIDES_IN]->(j)
RETURN count(*) AS residents;
"""
    ),
    'P6': (
        """\
MERGE (o:Org {id: $org_id})
SET o.name = $org_name, o.kind = $org_kind, o.mirrors_submitter = $mirrors_submitter, o.synthetic = true
WITH o
UNWIND $playbooks AS pb
MERGE (x:Playbook {kind: pb.kind})
SET x.steps = pb.steps
RETURN count(x) AS playbooks;
"""
    ),
    'P7': (
        """\
UNWIND $clinicians AS c
CREATE (:Clinician {id: c.id, name: c.name, role: c.role, active: c.active, left_at: c.left_at, synthetic: true})
WITH count(*) AS n
UNWIND $clinics AS k
CREATE (:Clinic {id: k.id, name: k.name, open: k.open, closed_at: k.closed_at, synthetic: true})
RETURN count(*) AS clinics;
"""
    ),
    'P8': (
        """\
UNWIND $rows AS r
MATCH (a:Clinician {id: r.from}), (b:Clinic {id: r.to})
CREATE (a)-[:PRACTICED_AT {at: r.at, until: r.until}]->(b)
RETURN count(*) AS edges;
"""
    ),
    'P9': (
        """\
UNWIND $rows AS r
MATCH (a:Clinician {id: r.from}), (b:Clinician {id: r.to})
CREATE (a)-[:HANDED_PANEL_TO {at: r.at}]->(b)
RETURN count(*) AS edges;
"""
    ),
    'P10': (
        """\
UNWIND $rows AS r
MATCH (a:Clinic {id: r.from}), (b:Clinic {id: r.to})
CREATE (a)-[:SUCCEEDED_BY {at: r.at}]->(b)
RETURN count(*) AS edges;
"""
    ),
    'P11': (
        """\
UNWIND $rows AS r
MATCH (a:Clinic {id: r.from}), (b:Clinician {id: r.to})
CREATE (a)-[:LED_BY {at: r.at, until: r.until}]->(b)
RETURN count(*) AS edges;
"""
    ),
    'P12': (
        """\
UNWIND $patients AS r
MERGE (pt:Patient {pid: r.pid})
WITH pt, r
MATCH (c:Clinician {id: r.clinician})
CREATE (pt)-[:UNDER_CARE {from: r.from, until: r.until}]->(c)
RETURN count(*) AS links;
"""
    ),
    'P13': (
        """\
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
"""
    ),
    'P14': (
        """\
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
"""
    ),
    'P15': (
        """\
UNWIND $rows AS r
MATCH (p:Person {pid: r.pid})
CREATE (n:Notice {id: r.id, pid: r.pid, vcv: r.vcv, cls: r.cls, notice_type: r.notice_type, channel: r.channel,
                  release: r.release, approved_by: r.approved_by, approved_at: r.approved_at, body: r.body, seeded: true})
CREATE (p)-[:WAS_NOTIFIED]->(n)
RETURN count(n) AS notices;
"""
    ),
}

SCHEMA_KB = QUERIES['SCHEMA_KB']
SCHEMA_LAB = QUERIES['SCHEMA_LAB']
SCHEMA_HS = QUERIES['SCHEMA_HS']
K1 = QUERIES['K1']
K2 = QUERIES['K2']
K3 = QUERIES['K3']
K4 = QUERIES['K4']
K5 = QUERIES['K5']
K6 = QUERIES['K6']
K7 = QUERIES['K7']
K8 = QUERIES['K8']
K9 = QUERIES['K9']
K10 = QUERIES['K10']
K11 = QUERIES['K11']
K12 = QUERIES['K12']
K13 = QUERIES['K13']
K14 = QUERIES['K14']
K15 = QUERIES['K15']
K16 = QUERIES['K16']
K17 = QUERIES['K17']
X1 = QUERIES['X1']
X2 = QUERIES['X2']
X3 = QUERIES['X3']
X4 = QUERIES['X4']
C1 = QUERIES['C1']
C2 = QUERIES['C2']
C3 = QUERIES['C3']
W1 = QUERIES['W1']
W2 = QUERIES['W2']
W3 = QUERIES['W3']
W4 = QUERIES['W4']
W5 = QUERIES['W5']
D1 = QUERIES['D1']
D2 = QUERIES['D2']
D3 = QUERIES['D3']
D4 = QUERIES['D4']
D5 = QUERIES['D5']
L1 = QUERIES['L1']
L2 = QUERIES['L2']
L3 = QUERIES['L3']
L4 = QUERIES['L4']
L5 = QUERIES['L5']
L6 = QUERIES['L6']
L7 = QUERIES['L7']
L8 = QUERIES['L8']
L9 = QUERIES['L9']
L10 = QUERIES['L10']
L11 = QUERIES['L11']
L17 = QUERIES['L17']
L18 = QUERIES['L18']
L19 = QUERIES['L19']
L20 = QUERIES['L20']
L21 = QUERIES['L21']
L12 = QUERIES['L12']
L13 = QUERIES['L13']
L14 = QUERIES['L14']
L15 = QUERIES['L15']
L16 = QUERIES['L16']
T1 = QUERIES['T1']
T2 = QUERIES['T2']
T3 = QUERIES['T3']
T4 = QUERIES['T4']
T5 = QUERIES['T5']
A1 = QUERIES['A1']
A2 = QUERIES['A2']
A3 = QUERIES['A3']
P1 = QUERIES['P1']
P2 = QUERIES['P2']
P3 = QUERIES['P3']
P4 = QUERIES['P4']
P5 = QUERIES['P5']
P6 = QUERIES['P6']
P7 = QUERIES['P7']
P8 = QUERIES['P8']
P9 = QUERIES['P9']
P10 = QUERIES['P10']
P11 = QUERIES['P11']
P12 = QUERIES['P12']
P13 = QUERIES['P13']
P14 = QUERIES['P14']
P15 = QUERIES['P15']

# Fixed health aggregates. Not query blocks; no user input.
HEALTH_RELEASES = """MATCH (r:Release)
RETURN r.id AS id, r.kind AS kind, r.rows AS rows, r.file_sha256 AS file_sha256
ORDER BY id ASC"""
COUNT_VARIANTS = "MATCH (v:Variant) RETURN count(v) AS variants"
COUNT_SCVS = "MATCH (s:SCV) RETURN count(s) AS scvs"

# fmt: on
