"""ClinVar row normalisation. Deterministic; the loader and the extract share it."""

from __future__ import annotations

import json
import re
from pathlib import Path

_REPO = Path(__file__).resolve()
for _parent in _REPO.parents:
    if (_parent / "data" / "normalisation.json").is_file():
        _REPO = _parent
        break

_NORM = json.loads((_REPO / "data" / "normalisation.json").read_text())

_CLASS_MAP = {k.lower(): v for k, v in _NORM["classification"].items()}
_STARS = {k.lower(): v for k, v in _NORM["review_status_stars"].items()}
SKIP_REVIEW_STATUS = {s.lower() for s in _NORM["skip_scv_rows_with_review_status"]}
ACTIONABLE = set(_NORM["actionable"])

_MONTHS = {
    "jan": 1,
    "feb": 2,
    "mar": 3,
    "apr": 4,
    "may": 5,
    "jun": 6,
    "jul": 7,
    "aug": 8,
    "sep": 9,
    "oct": 10,
    "nov": 11,
    "dec": 12,
}


def norm_class(raw: str) -> str:
    """Normalise a ClinicalSignificance string to a code."""
    return _CLASS_MAP.get(raw.strip().lower(), "OTHER")


def norm_stars(review_status: str) -> int:
    return int(_STARS.get(review_status.strip().lower(), 0))


def norm_date(raw: str) -> str | None:
    """'Dec 17, 2024' -> '2024-12-17'; '-' or empty -> None."""
    text = raw.strip()
    if not text or text == "-":
        return None
    match = re.match(r"^([A-Za-z]{3})\w*\s+(\d{1,2}),\s+(\d{4})$", text)
    if not match:
        return None
    month = _MONTHS.get(match.group(1)[:3].lower())
    if month is None:
        return None
    return f"{int(match.group(3)):04d}-{month:02d}-{int(match.group(2)):02d}"


def submitter_slug(name: str) -> str:
    """Lowercase, replace runs outside [a-z0-9] with '-', strip, truncate to 80."""
    slug = re.sub(r"[^a-z0-9]+", "-", name.strip().lower()).strip("-")
    return slug[:80].rstrip("-")


def change_kind(from_cls: str, to_cls: str) -> str:
    """Mirror of the K5 CASE, used by the build-time eval extract only."""
    if from_cls in ("CONFLICTING", "OTHER") or to_cls in ("CONFLICTING", "OTHER"):
        return "NEEDS_REVIEW_CLASS"
    if from_cls not in ACTIONABLE and to_cls in ACTIONABLE:
        return "UP_TO_ACTIONABLE"
    if from_cls in ACTIONABLE and to_cls not in ACTIONABLE:
        return "DOWN_FROM_ACTIONABLE"
    if from_cls == "VUS" and to_cls in ("LB", "B"):
        return "VUS_RESOLVED_BENIGN"
    if from_cls in ("LB", "B") and to_cls == "VUS":
        return "BENIGN_TO_VUS"
    return "WITHIN_TIER"


def split_genes(raw: str) -> list[str]:
    return [part.strip() for part in raw.split(";") if part.strip()]


def in_scope_gene(raw: str, scope: set[str]) -> str | None:
    """Exactly one in-scope symbol, else None."""
    hits = [g for g in split_genes(raw) if g in scope]
    return hits[0] if len(hits) == 1 else None
