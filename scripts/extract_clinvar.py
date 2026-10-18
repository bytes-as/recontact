#!/usr/bin/env python3.12
"""Build-time ClinVar extract (FLOWS F1). Streams the monthly archives once; outputs are committed.

Usage:
  python3.12 scripts/extract_clinvar.py variants [--scope sf|core|dev]
  python3.12 scripts/extract_clinvar.py scv      [--scope sf|core|dev]
  python3.12 scripts/extract_clinvar.py --eval   [--scope sf|core|dev]
"""
from __future__ import annotations

import argparse
import gzip
import hashlib
import json
import sys
import time
import urllib.request
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "services" / "api"))
from app.clinvar import parse  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "data" / "clinvar"
RELEASES = json.loads((ROOT / "data" / "releases.json").read_text())
GENES = json.loads((ROOT / "data" / "genes.json").read_text())["genes"]

DEV_GENES = ["BRCA1", "BRCA2", "TP53", "PCSK9", "HFE"]
MAX_TOTAL_BYTES = 60 * 1024 * 1024

# Column names (header-by-name parsing; 2024-10 has 15 columns, 2026 files have 43/16)
VAR_COLS = {
    "vcv": "VariationID",
    "gene": "GeneSymbol",
    "name": "Name",
    "agg_cls_raw": "ClinicalSignificance",
    "agg_review": "ReviewStatus",
    "assembly": "Assembly",
}
SCV_COLS = {
    "vcv": "VariationID",
    "acc_version": "SCV",
    "cls_raw": "ClinicalSignificance",
    "dle": "DateLastEvaluated",
    "review": "ReviewStatus",
    "submitter": "Submitter",
}


def scope_genes(scope: str) -> set[str]:
    if scope == "dev":
        return set(DEV_GENES)
    if scope == "core":
        return {g["symbol"] for g in GENES if g["core"]}
    return {g["symbol"] for g in GENES if g["kb_scope"]}


def stream(url: str, tries: int = 3):
    """Yield decompressed text lines from a .gz over HTTPS, with retry."""
    delay = 5
    for attempt in range(1, tries + 1):
        try:
            req = urllib.request.Request(url, headers={"User-Agent": "recontact"})
            with urllib.request.urlopen(req, timeout=120) as resp:
                with gzip.GzipFile(fileobj=resp) as gz:
                    for raw in gz:
                        yield raw.decode("utf-8", "replace")
            return
        except Exception as exc:  # noqa: BLE001
            if attempt == tries:
                raise
            print(f"  retry {attempt}/{tries} {url.split('/')[-1]}: {exc}", file=sys.stderr)
            time.sleep(delay)
            delay *= 3


def sha256_of(url: str) -> tuple[str, int]:
    h = hashlib.sha256()
    n = 0
    req = urllib.request.Request(url, headers={"User-Agent": "recontact"})
    with urllib.request.urlopen(req, timeout=120) as resp:
        while True:
            chunk = resp.read(1 << 20)
            if not chunk:
                break
            h.update(chunk)
            n += len(chunk)
    return h.hexdigest(), n


def find_header(lines, marker: str):
    for line in lines:
        if line.startswith(marker):
            return line.lstrip("#").rstrip("\n").split("\t"), lines
    raise RuntimeError(f"no header starting {marker!r}")


def cmd_variants(scope: str) -> None:
    genes = scope_genes(scope)
    url = RELEASES["base_url"] + RELEASES["variants_from"]["file"]
    print(f"variants: streaming {url} scope={scope} genes={len(genes)}", file=sys.stderr)
    OUT.mkdir(parents=True, exist_ok=True)
    seen: set[int] = set()
    out_path = OUT / "variants.tsv.gz"
    rows_in = rows_out = 0
    header = None
    idx: dict[str, int] = {}
    with gzip.open(out_path, "wt") as out:
        out.write("vcv\tgene\tname\tagg_cls\tagg_cls_raw\tagg_review\tagg_stars\n")
        for line in stream(url):
            if line.startswith("##"):
                continue
            if line.startswith("#AlleleID"):
                header = line.lstrip("#").rstrip("\n").split("\t")
                idx = {name: i for i, name in enumerate(header)}
                continue
            if header is None or not line.strip():
                continue
            rows_in += 1
            cols = line.rstrip("\n").split("\t")
            def c(key: str) -> str:
                name = VAR_COLS[key]
                return cols[idx[name]] if name in idx and idx[name] < len(cols) else ""
            if c("assembly") != RELEASES["variants_from"]["assembly"]:
                continue
            gene = parse.in_scope_gene(c("gene"), genes)
            if gene is None:
                continue
            try:
                vcv = int(c("vcv"))
            except ValueError:
                continue
            if vcv in seen:
                continue
            seen.add(vcv)
            agg_raw = c("agg_cls_raw")
            row = [
                str(vcv),
                gene,
                c("name"),
                parse.norm_class(agg_raw),
                agg_raw,
                c("agg_review"),
                str(parse.norm_stars(c("agg_review"))),
            ]
            out.write("\t".join(row) + "\n")
            rows_out += 1
    print(f"variants: rows_in={rows_in} rows_out={rows_out} -> {out_path}", file=sys.stderr)


def _iter_scv_rows(url: str, variant_set: set[int]):
    """Yield normalised rows from one submission_summary archive."""
    header = None
    idx: dict[str, int] = {}
    for line in stream(url):
        if line.startswith("#Name") or (line.startswith("##") and not line.startswith("#VariationID")):
            continue
        if line.startswith("#VariationID"):
            header = line.lstrip("#").rstrip("\n").split("\t")
            idx = {name: i for i, name in enumerate(header)}
            continue
        if header is None or not line.strip():
            continue
        cols = line.rstrip("\n").split("\t")
        def c(key: str) -> str:
            name = SCV_COLS[key]
            return cols[idx[name]] if name in idx and idx[name] < len(cols) else ""
        try:
            vcv = int(c("vcv"))
        except ValueError:
            continue
        if vcv not in variant_set:
            continue
        review = c("review")
        if review.strip().lower() in parse.SKIP_REVIEW_STATUS:
            continue
        acc_full = c("acc_version")
        if "." in acc_full:
            acc, ver = acc_full.rsplit(".", 1)
        else:
            acc, ver = acc_full, "1"
        try:
            version = int(ver)
        except ValueError:
            version = 1
        cls_raw = c("cls_raw")
        submitter = c("submitter")
        yield {
            "acc": acc,
            "vcv": vcv,
            "version": version,
            "cls": parse.norm_class(cls_raw),
            "cls_raw": cls_raw,
            "dle": parse.norm_date(c("dle")) or "",
            "review": review,
            "stars": parse.norm_stars(review),
            "submitter": submitter,
            "submitter_id": parse.submitter_slug(submitter),
        }


def _load_variant_set(scope: str) -> set[int]:
    genes = scope_genes(scope)
    vs = set()
    with gzip.open(OUT / "variants.tsv.gz", "rt") as f:
        next(f)
        for line in f:
            v, g = line.split("\t")[:2]
            if g in genes:
                vs.add(int(v))
    return vs


def cmd_scv(scope: str) -> None:
    variant_set = _load_variant_set(scope)
    print(f"scv: scope={scope} variants={len(variant_set)}", file=sys.stderr)
    manifest = []
    prev: dict[str, dict] = {}
    for rel in RELEASES["releases"]:
        rid, kind, fname = rel["id"], rel["kind"], rel["file"]
        url = RELEASES["base_url"] + fname
        cur: dict[str, dict] = {}
        rows_in = 0
        for row in _iter_scv_rows(url, variant_set):
            rows_in += 1
            cur[row["acc"]] = row
        # delta rows: new acc, or (version, cls) differs from prev
        delta = []
        for acc, row in cur.items():
            p = prev.get(acc)
            if p is None or (p["version"], p["cls"]) != (row["version"], row["cls"]):
                delta.append(row)
        withdrawn = [acc for acc in prev if acc not in cur]
        out_file = OUT / f"scv_{rid}_{'base' if kind=='BASE' else 'delta'}.tsv.gz"
        cols = ["acc", "vcv", "version", "cls", "cls_raw", "dle", "review", "stars", "submitter", "submitter_id"]
        with gzip.open(out_file, "wt") as out:
            out.write("\t".join(cols) + "\n")
            for row in delta:
                out.write("\t".join(str(row[c]) for c in cols) + "\n")
        if kind != "BASE":
            with open(OUT / f"withdrawn_{rid}.txt", "w") as out:
                out.write("\n".join(sorted(withdrawn)) + ("\n" if withdrawn else ""))
        sha, nbytes = sha256_of(url)
        manifest.append({
            "file": fname, "release": rid, "kind": kind, "bytes": nbytes,
            "sha256": sha, "rows_in": rows_in, "rows_out": len(delta), "scope": scope,
        })
        print(f"scv {rid}: rows_in={rows_in} rows_out={len(delta)} withdrawn={len(withdrawn)}", file=sys.stderr)
        prev = cur
    (OUT / "MANIFEST.json").write_text(json.dumps({"files": manifest}, indent=2))
    _check_size()


def cmd_eval(scope: str) -> None:
    variant_set = _load_variant_set(scope)
    gene_of = {}
    with gzip.open(OUT / "variants.tsv.gz", "rt") as f:
        next(f)
        for line in f:
            v, g = line.split("\t")[:2]
            gene_of[int(v)] = g
    r2024 = RELEASES["eval_only"][0]
    r2026 = RELEASES["releases"][-1]
    def snap(url):
        out = {}
        for row in _iter_scv_rows(url, variant_set):
            out[row["acc"]] = row
        return out
    a = snap(RELEASES["base_url"] + r2024["file"])
    b = snap(RELEASES["base_url"] + r2026["file"])
    eval_dir = ROOT / "eval"
    eval_dir.mkdir(exist_ok=True)
    n_trans = n_unchanged = 0
    with open(eval_dir / "transitions_2024-10_2026-10.tsv", "w") as tr, \
         open(eval_dir / "unchanged_2024-10_2026-10.tsv", "w") as un:
        tr.write("acc\tvcv\tgene\tsubmitter\tfrom_cls\tto_cls\tfrom_version\tto_version\tkind\n")
        un.write("acc\tvcv\tgene\tsubmitter\tcls\tfrom_version\tto_version\tversion_bumped\n")
        for acc in sorted(set(a) & set(b)):
            ra, rb = a[acc], b[acc]
            if ra["cls"] != rb["cls"]:
                kind = parse.change_kind(ra["cls"], rb["cls"])
                tr.write(f"{acc}\t{ra['vcv']}\t{gene_of.get(ra['vcv'],'')}\t{ra['submitter']}\t{ra['cls']}\t{rb['cls']}\t{ra['version']}\t{rb['version']}\t{kind}\n")
                n_trans += 1
            else:
                bumped = "1" if ra["version"] != rb["version"] else "0"
                un.write(f"{acc}\t{ra['vcv']}\t{gene_of.get(ra['vcv'],'')}\t{ra['submitter']}\t{ra['cls']}\t{ra['version']}\t{rb['version']}\t{bumped}\n")
                n_unchanged += 1
    print(f"eval: transitions={n_trans} unchanged={n_unchanged}", file=sys.stderr)


def _check_size() -> None:
    total = sum(p.stat().st_size for p in OUT.glob("**/*") if p.is_file())
    print(f"data/clinvar size: {total/1024/1024:.1f} MB", file=sys.stderr)
    if total > MAX_TOTAL_BYTES:
        print(f"ERROR: data/clinvar exceeds 60 MB ({total} bytes); use --scope core", file=sys.stderr)
        sys.exit(1)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("command", choices=["variants", "scv"], nargs="?")
    ap.add_argument("--eval", action="store_true", dest="do_eval")
    ap.add_argument("--scope", default="sf", choices=["sf", "core", "dev"])
    args = ap.parse_args()
    if args.do_eval:
        cmd_eval(args.scope)
    elif args.command == "variants":
        cmd_variants(args.scope)
    elif args.command == "scv":
        cmd_scv(args.scope)
    else:
        ap.print_help()


if __name__ == "__main__":
    main()
