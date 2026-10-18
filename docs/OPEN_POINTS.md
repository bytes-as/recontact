# Open points

## Resolved before handoff (18 Oct 2026)
| Point | Resolution | Evidence |
|---|---|---|
| Which ClinVar files carry per-lab history | `submission_summary_YYYY-MM.txt.gz` monthly archives: one row per SCV with `Submitter`, `SCV` (accession.version), `ClinicalSignificance`, `DateLastEvaluated`, `ReviewStatus`. 2025-01 through 2026-10 under `archive/`, 2024 under `archive/2024/`. Monthly releases usually on the first Thursday; weekly files are not archived | BLUEPRINT 4.1; directory listings and README read 18 Oct |
| Exact column names | submission_summary: 16 columns (2026 archives), 15 in 2024-10 (no `ContributesToAggregateClassification`): parse by header name. variant_summary: 43 columns, two rows per variant (GRCh37/GRCh38) | BLUEPRINT 4.1; headers streamed from the live files |
| Is there real reclassification volume | Yes. First 20,000 rows of Sep vs Oct 2026: 19,195 shared SCVs, 224 version bumps, 26 class changes (e.g. PCSK9 VCV 2877 SCV001983711 VUS -> B; HFE VCV 11 SCV000206974 P -> LB). Earlier partial diff (research): at least 761 class changes Sep -> Oct 2026 | BLUEPRINT 4.1 |
| E-utilities efetch for a VCV returned an empty set | `rettype=vcv` requires `is_variationid`; without it 110 bytes empty; with it 88,994 bytes, 17 ClinicalAssertion records for VCV 51579 | BLUEPRINT 4.2 |
| E-utilities rate limit | `x-ratelimit-limit: 3` without a key (header verified); 10/s with `NCBI_API_KEY` | BLUEPRINT 4.2 |
| Data terms | NCBI "places no restrictions on the use or distribution of the data" in its molecular databases | NCBI policies page read 18 Oct |
| Gene list | ACMG SF v3.3 = NCBI's v3.2 table (81 genes, cross-checked exactly) + ABCD1, CYP27A1, PLN. Inheritance modes curated; human check pending (G024) | `data/genes.json` |
| kb size | 84 genes: 347,667 alleles, 876,513 submissions (gene_specific_summary 2026-10-11); minus TTN: about 306,700 and 778,900. Scale test: about 6-10 min load, about 1-1.5 GB | BLUEPRINT 3, 4.1 |
| Do the queries run on FalkorDB | All 81 blocks executed on `falkordb/falkordb:latest` (module 42201); 52 behavioural checks pass (pruning, cousin path, not-to-know, letter-only region, deceased source, half-sibling, partner exclusion, succession with ended leads, ORPHAN dead ends, reopen rules, idempotent diff, leases, WCC, BFS outgoing-only, GRAPH.COPY) | `docs/queries.cypher` header |
| Undirected PARENT_OF walks reach partners (a child's other parent) | Replaced by up-then-down kinship paths through a common ancestor with no shared nodes; verified that the father's other partner is never reached | X2, C1 |
| Recon tasks and hs tasks had no query that attaches a task to a Decision, Handoff or Recon | Added L18, L19, L20; failed handoffs L21 | `docs/queries.cypher` |
| Dry runs on the read-only demo tenant would write Handoff nodes | Dry runs use the Steward's read-only resolution in-process; only real runs write handoffs | FLOWS F7.6 |
| Crowding | GitHub, 18 Oct: 0 FalkorDB repos for clinvar, genetic, variant, recontact, cascade testing, consent, genomic, hereditary; 2 for pedigree (one family-risk tracker created 17 Oct 2026; one unrelated agent-memory repo); README search "falkordb clinvar" 0 | BLUEPRINT 1 (positioning) |
| MCP mount and FalkorDB container facts | Reused verified facts from ModelBrain: `mcp>=1.10,<2`, FastMCP stateless_http, mount after routes, lifespan; data path, REDIS_ARGS, FALKORDB_ARGS (TIMEOUT default 1000 re-confirmed) | BLUEPRINT 3 |
| Hosting | Vercel + Railway (FalkorDB in Docker, 2 GB). FalkorDB Cloud free tier rejected | BLUEPRINT 3 |

## Deferred to the build (safe to leave until the step that needs them)
| Point | Why it can wait | When | Owner |
|---|---|---|---|
| Human check of `data/genes.json` inheritance and review flags against the published ACMG SF v3.3 table (G024) | Needed before the engine is merged and before labels are written | Block 1 | B |
| Real counts per release on the full `sf` scope (G027) and the mirrored submitter chosen by the resolver (G040) | Need the extract and load | Block 1-2 | A |
| Load time and memory on Railway (G028); switch to `KB_SCOPE=core` if over budget | Needs the deployment | Block 1 | A |
| K11 latency for the largest submitter (G037); per-gene fallback if slow | Needs the full kb | Block 1 | A |
| Recon counts for the replay (G100); `recon_submitter` fallback | Needs the full kb | Block 5 | A |
| Whether the 2026-11 archive appears during judging (expected about 5 Nov 2026) | The Watcher handles it automatically; the replay endpoint covers the video | after submission | A |
| Repository licence and ownership (rule 15) | Needed only at submission | Block 7 | Team |
| Blog post (side prize) | After submission is fine | after G141 | B |

## Objections we could not fully remove (stated in the README)
- The people who make the duty map are synthetic. Mitigation: the real-data opener, the live variant lookup, a published seeded generator and a frozen eval with human labels and held-out seeds.
- The loop is ClinVar's own update. Mitigation: we claim memory, routing and citation, not causation, and say so on screen.
- FalkorDB algorithm use is modest (WCC, BFS). Mitigation: we use them where they do work and explain why we add nothing for show.

## Verification log (fill in during the build)
- G024 gene table checked by: ____ on ____
- G027 class changes (sf scope): 2026-09: UP ____ DOWN ____ VUS->B ____; 2026-10: UP ____ DOWN ____ VUS->B ____; submitters with changes in 2026-10: ____
- G028 load time ____ min; FalkorDB used memory ____
- G037 K11 latency for the largest submitter ____ s
- G040 mirrored submitter ____; fallback ____
- G100 Recon items opened as of 2026-08 ____; closed in 2026-09 ____, 2026-10 ____

## Not open (decided; do not revisit)
See BLUEPRINT section 18.
