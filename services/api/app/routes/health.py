"""GET /api/health."""

from __future__ import annotations

from fastapi import APIRouter

from app.config import get_settings
from app.graph.db import health_snapshot, ro_query
from app.graph.queries import COUNT_SCVS, COUNT_VARIANTS, HEALTH_RELEASES
from app.main_version import VERSION

router = APIRouter()

# The loader (G025) writes this while a release is ingesting.
kb_loading: dict[str, object] | None = None


def _cell(row: list[object], index: int) -> object:
    if index >= len(row):
        return None
    return row[index]


def _kb_counts() -> dict[str, object]:
    releases_result = ro_query("kb", HEALTH_RELEASES)
    releases = []
    for row in releases_result.result_set or []:
        releases.append(
            {
                "id": _cell(row, 0),
                "kind": _cell(row, 1),
                "rows": _cell(row, 2),
                "file_sha256": _cell(row, 3),
            }
        )
    variants_row = (ro_query("kb", COUNT_VARIANTS).result_set or [[0]])[0]
    scvs_row = (ro_query("kb", COUNT_SCVS).result_set or [[0]])[0]
    return {
        "releases": releases,
        "variants": int(variants_row[0] or 0),
        "scvs": int(scvs_row[0] or 0),
    }


@router.get("/api/health")
def health() -> dict[str, object]:
    settings = get_settings()
    snap = health_snapshot()
    kb: dict[str, object] = {
        "releases": [],
        "variants": 0,
        "scvs": 0,
        "loading": kb_loading,
        "scope": settings.kb_scope,
    }
    if snap["falkordb"] == "up" and "kb" in snap["graphs"]:
        try:
            kb.update(_kb_counts())
        except Exception:
            kb["releases"] = []
    ncbi = "disabled" if not settings.live_lookups else "ok"
    return {
        "ok": snap["falkordb"] == "up",
        "falkordb": snap["falkordb"],
        "graphs": snap["graphs"],
        "kb": kb,
        "ncbi": ncbi,
        "version": VERSION,
    }
