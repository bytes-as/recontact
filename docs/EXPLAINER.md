# Recontact in two minutes (every team member must be able to say this)

**The problem.** Variant classifications change every month in ClinVar: in 1.45 million hereditary-cancer tests, 7.7% of unique VUS were reclassified, 91% of them downgraded (Mersch, JAMA 2018). Labs can list the reports that cite a changed variant, but follow-up breaks exactly where the graph is: the ordering doctor retired or the clinic closed, relatives were never tested (only 41% of at-risk relatives complete cascade testing, Frey, JCO 2022), contact is lawful only along a consented path, and decisions made on the old answer (a sister discharged from screening, a surgery recommendation) stay wrong.

**What we built.** Agents on FalkorDB that answer: "This classification just changed: who must be told, by whom, are we allowed to tell them, and which decisions must reopen?" with a proof for every answer, including every "no".

**The graph model.**
- `kb` (real, public ClinVar): `Gene <-IN_GENE- Variant <-ABOUT- SCV -HAS_VERSION-> SCVVersion -NEXT-> SCVVersion`, `SCV -SUBMITTED_BY-> Submitter`, `ClassChange -OF-> SCV`, `Release`.
- A lab graph per organisation (synthetic, fictional): `Person -PARENT_OF-> Person`, `Person -HAS_REPORT-> Report -CITES-> VariantRef`, tests, consents, jurisdictions, and the memory: `Run -PRODUCED-> Duty -FOR-> Person`, `Notice`, `Task`, `Event`, `Handoff`, `Recon`.
- A health-system graph (synthetic, fictional): `Clinician -HANDED_PANEL_TO-> Clinician`, `Clinician -PRACTICED_AT-> Clinic -SUCCEEDED_BY-> Clinic -LED_BY-> Clinician`, `Patient -UNDER_CARE-> Clinician`, `Decision -RESTED_ON {class, release, SCV}-> VariantRef`, `SUPERSEDES`.

**The queries you must be able to explain.**
- **K5** loads a monthly archive and diffs it inside the graph: a new version of a submission closes the old one, and if the class changed it creates a `ClassChange`. Re-running a month changes nothing.
- **X2 / C1** walk from the variant to every report holder, then up to a common ancestor and down to each untested living relative (never through a partner), at most 4 hops. A relative who tested negative on the way cuts that derivation. C1 checks consent per derivation: AND along a path (source alive, source consented, relative did not refuse, region allows it), OR across paths. That is how a consenting carrier cousin reaches a sister even though the proband refused.
- **W1** finds who owns the duty today: the shortest time-ordered chain of panel handoffs, clinic successions and current clinic leads to an active clinician. No row is the proof of an ORPHAN; **W2** lists the dead ends.
- **D1** finds active decisions that rested on the old class across the actionable line (or on a resolved VUS); they reopen as events and tasks, never edited.
- **K11 / K12**: submissions that differ from a current expert-panel review become reconsideration items; a later archive closes them with a citation. That loop is ClinVar's own update; we provide memory and routing.
- **A2** (`algo.WCC`) finds families with two carriers so nobody is told twice; **A3** (`algo.BFS`) draws the cascade below a person.

**Why FalkorDB, and why it is load-bearing.** Every answer is a FalkorDB query; stop FalkorDB and the product returns 503. One instance holds the real ClinVar graph, each organisation's private graph and every visitor's sandbox (`GRAPH.COPY`). Organisations never read each other's graphs: agents leave `Handoff` nodes with leases in the other graph, carrying the minimum necessary, and nothing about a blocked person ever crosses.

**Decisions and trade-offs.**
- The graph decides; the Python engine applies a fixed table to graph rows; an LLM may only rephrase drafts.
- People are synthetic because privacy forces it; the ClinVar layer is real; the generator and its calibration are published; the eval labels were hashed before the rules existed.
- Automatic relative routing only for autosomal dominant genes without a review flag; everything else goes to a counsellor.
- Nothing is sent without a named counsellor's approval, and Recontact never sends anything itself.
- We never call a real lab's classification wrong; we say it differs from the expert-panel review or was updated.

**What we would do next.** Real lab and health-system pilots under a data agreement, more jurisdictions with counsel, weekly releases, and a FHIR export of approved notices.
