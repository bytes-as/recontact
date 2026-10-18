"""kb loader (FLOWS F2). K1 genes, K2 variants, then per release K3/K4/K5/K6.

Resumable: a release whose Release node already exists is skipped unless force.
Idempotent: K4 and K5 MERGE on ids, so a re-run changes nothing.
"""

from __future__ import annotations

import gzip
import json
import logging
import time
from pathlib import Path
from typing import Any

from app.config import get_settings
from app.graph import db
from app.graph.queries import K1, K2, K3, K4, K5, K6, K14

log = logging.getLogger("recontact.load")

KB = "kb"

_repo = Path(__file__).resolve()
for _p in _repo.parents:
    if (_p / "data" / "genes.json").is_file():
        _repo = _p
        break
DATA = _repo / "data"
CLINVAR = DATA / "clinvar"

BATCH = 2000

# Progress surfaced at /api/health.kb.loading
progress: dict[str, Any] | None = None


def _set_progress(release: str | None, rows_done: int, rows_total: int) -> None:
    global progress
    if release is None:
        progress = None
    else:
        progress = {"release": release, "rows_done": rows_done, "rows_total": rows_total}


def _batches(rows: list[dict[str, Any]], size: int):
    for i in range(0, len(rows), size):
        yield rows[i : i + size]


def _read_tsv(path: Path) -> list[dict[str, str]]:
    out: list[dict[str, str]] = []
    with gzip.open(path, "rt") as f:
        header = next(f).rstrip("\n").split("\t")
        for line in f:
            cols = line.rstrip("\n").split("\t")
            out.append(dict(zip(header, cols, strict=False)))
    return out


def _read_withdrawn(path: Path) -> list[str]:
    if not path.exists():
        return []
    return [line.strip() for line in path.read_text().splitlines() if line.strip()]


def _manifest_sha(file_name: str) -> str:
    manifest = CLINVAR / "MANIFEST.json"
    if not manifest.exists():
        return ""
    for entry in json.loads(manifest.read_text()).get("files", []):
        if entry.get("file") == file_name:
            return entry.get("sha256", "")
    return ""


def _load_genes() -> int:
    genes = json.loads((DATA / "genes.json").read_text())["genes"]
    rows = [
        {
            "symbol": g["symbol"],
            "inheritance": g["inheritance"],
            "review_always": g["review_always"],
            "review_reason": g.get("review_reason"),
            "category": g.get("category"),
            "condition": g.get("condition"),
            "sf_version": g.get("sf_version"),
        }
        for g in genes
    ]
    result = db.query(KB, K1, {"rows": rows})
    count = int((result.result_set or [[0]])[0][0])
    log.info("K1 genes=%s", count)
    return count


def _load_variants(release: str) -> int:
    rows_raw = _read_tsv(CLINVAR / "variants.tsv.gz")
    rows = [
        {
            "vcv": int(r["vcv"]),
            "gene": r["gene"],
            "name": r["name"],
            "agg_cls": r["agg_cls"],
            "agg_cls_raw": r["agg_cls_raw"],
            "agg_review": r["agg_review"],
            "agg_stars": int(r["agg_stars"]),
        }
        for r in rows_raw
    ]
    total = 0
    for batch in _batches(rows, BATCH):
        db.query(KB, K2, {"rows": batch, "release": release})
        total += len(batch)
    log.info("K2 variants=%s", total)
    return total


def _scv_rows(path: Path) -> list[dict[str, Any]]:
    rows = []
    for r in _read_tsv(path):
        rows.append(
            {
                "acc": r["acc"],
                "vcv": int(r["vcv"]),
                "version": int(r["version"]),
                "cls": r["cls"],
                "cls_raw": r["cls_raw"],
                "dle": r["dle"] or None,
                "review": r["review"],
                "stars": int(r["stars"]),
                "submitter": r["submitter"],
                "submitter_id": r["submitter_id"],
            }
        )
    return rows


def _loaded_release_ids() -> set[str]:
    try:
        result = db.ro_query(KB, K14)
    except Exception:
        return set()
    return {str(row[0]) for row in (result.result_set or [])}


def _load_release(release: dict[str, str]) -> None:
    rid, kind, fname = release["id"], release["kind"], release["file"]
    suffix = "base" if kind == "BASE" else "delta"
    scv_path = CLINVAR / f"scv_{rid}_{suffix}.tsv.gz"
    if not scv_path.exists():
        log.warning("no extract for %s (%s); skipping", rid, scv_path)
        return
    rows = _scv_rows(scv_path)
    withdrawn = _read_withdrawn(CLINVAR / f"withdrawn_{rid}.txt")
    _set_progress(rid, 0, len(rows))
    done = 0
    for batch in _batches(rows, BATCH):
        db.query(KB, K4, {"rows": batch})
        db.query(KB, K5, {"rows": batch, "release": rid})
        done += len(batch)
        _set_progress(rid, done, len(rows))
    if withdrawn:
        db.query(KB, K6, {"accs": withdrawn, "release": rid})
    db.query(
        KB,
        K3,
        {
            "release": rid,
            "kind": kind,
            "file": fname,
            "file_sha256": _manifest_sha(fname),
            "rows": len(rows),
            "now": int(time.time() * 1000),
        },
    )
    log.info("loaded %s rows=%s withdrawn=%s", rid, len(rows), len(withdrawn))


def load_kb(force: bool = False) -> dict[str, Any]:
    """Load genes, variants, then every release. Returns a summary."""
    started = time.time()
    settings = get_settings()
    batch = settings.kb_batch_size or BATCH
    global BATCH
    BATCH = batch
    releases = json.loads((DATA / "releases.json").read_text())["releases"]
    latest = releases[-1]["id"]
    _load_genes()
    variants = _load_variants(latest)
    loaded = _loaded_release_ids()
    for release in releases:
        if release["id"] in loaded and not force:
            log.info("release %s already loaded; skipping", release["id"])
            continue
        _load_release(release)
        loaded.add(release["id"])
    _set_progress(None, 0, 0)
    elapsed = time.time() - started
    summary = {"variants": variants, "releases": sorted(loaded), "elapsed_s": round(elapsed, 1)}
    log.info("kb load complete: %s", summary)
    return summary


if __name__ == "__main__":
    import argparse

    ap = argparse.ArgumentParser()
    ap.add_argument("--force", action="store_true")
    args = ap.parse_args()
    print(json.dumps(load_kb(force=args.force)))
