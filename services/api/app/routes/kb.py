"""ClinVar kb endpoints (graph `kb`, read-only). Every answer is a FalkorDB query."""

from __future__ import annotations

from fastapi import APIRouter, Query
from fastapi import Path as PathParam

from app.errors import ApiError
from app.graph.db import ro_query
from app.graph.queries import K7, K8, K9, K10, K14, K15, K17
from app.models import Change, SubmitterRank, VariantStatus

router = APIRouter()

KB = "kb"

_RELEASE_RE = r"^\d{4}-\d{2}$"
_SUBMITTER_RE = r"^[a-z0-9-]{1,80}$"


def _require_kb() -> None:
    from app.graph.db import health_snapshot

    if health_snapshot()["falkordb"] != "up":
        raise ApiError("GRAPH_UNAVAILABLE", "FalkorDB is not reachable.", retry_after_s=5)


def _rows(result) -> list[dict]:
    header = [str(h) for h in (result.header or [])]
    out = []
    for row in result.result_set or []:
        out.append({header[i]: row[i] for i in range(len(header))})
    return out


def _source_line(release: str) -> str:
    return f"Source: ClinVar monthly archive {release} (NCBI, public)"


@router.get("/api/releases")
def releases() -> list[dict]:
    _require_kb()
    result = ro_query(KB, K14)
    return _rows(result)


@router.get("/api/releases/{release}/summary")
def release_summary(release: str = PathParam(pattern=_RELEASE_RE)) -> list[dict]:
    _require_kb()
    result = ro_query(KB, K15, {"release": release})
    return _rows(result)


@router.get("/api/releases/{release}/submitters")
def submitters(
    release: str = PathParam(pattern=_RELEASE_RE),
    limit: int = Query(50, ge=1, le=500),
) -> list[SubmitterRank]:
    _require_kb()
    result = ro_query(KB, K8, {"release": release, "limit": limit})
    return [SubmitterRank(**r) for r in _rows(result)]


@router.get("/api/releases/{release}/submitters/{submitter_id}/changes")
def submitter_changes(
    release: str = PathParam(pattern=_RELEASE_RE),
    submitter_id: str = PathParam(pattern=_SUBMITTER_RE),
    limit: int = Query(200, ge=1, le=500),
) -> dict:
    _require_kb()
    result = ro_query(KB, K7, {"release": release, "submitter_id": submitter_id, "limit": limit})
    rows = _rows(result)
    changes = [
        Change(
            release=release,
            submitter_id=submitter_id,
            review_always=None,
            review_reason=None,
            **{k: v for k, v in r.items() if k != "submitter"},
            submitter=r.get("submitter", ""),
        )
        for r in rows
    ]
    submitter = rows[0]["submitter"] if rows else ""
    return {
        "submitter": submitter,
        "release": release,
        "changes": [c.model_dump() for c in changes],
        "reported_by_demo": [],
    }


@router.get("/api/variants/{vcv}")
def variant_status(
    vcv: int = PathParam(ge=1, le=999999999),
    as_of: str | None = Query(None, pattern=_RELEASE_RE),
) -> VariantStatus:
    _require_kb()
    as_of_release = as_of or _latest_release()
    result = ro_query(KB, K9, {"vcv": vcv, "as_of": as_of_release})
    rows = _rows(result)
    if not rows or rows[0].get("vcv") is None:
        raise ApiError(
            "VARIANT_NOT_FOUND",
            f"No variant {vcv} in the loaded ClinVar releases.",
            hint="We load ACMG secondary-findings genes only. Check the Variation ID on ClinVar.",
        )
    r = rows[0]
    submissions = [s for s in (r.get("submissions") or []) if s and s.get("scv")]
    panel = _expert_panel(submissions)
    submissions = _mark_differs(submissions, panel)
    history = _rows(ro_query(KB, K10, {"vcv": vcv}))
    return VariantStatus(
        vcv=vcv,
        variant=r.get("variant") or "",
        gene=r.get("gene"),
        inheritance=r.get("inheritance"),
        review_always=r.get("review_always"),
        aggregate={
            "cls": r.get("aggregate_cls"),
            "cls_raw": r.get("aggregate_cls_raw"),
            "review": r.get("aggregate_review"),
            "stars": r.get("aggregate_stars"),
            "release": r.get("aggregate_release"),
        },
        as_of=as_of_release,
        submissions=submissions,
        history=history,
        panel=panel,
        source="kb",
        source_line=_source_line(as_of_release),
        note=None,
    )


@router.get("/api/changes/{change_id}")
def change_detail(change_id: str = PathParam(pattern=r"^SCV\d{9}@\d{4}-\d{2}$")) -> dict:
    _require_kb()
    result = ro_query(KB, K17, {"change_id": change_id})
    rows = _rows(result)
    if not rows:
        raise ApiError(
            "CHANGE_NOT_FOUND",
            f"No class change {change_id} in the loaded ClinVar releases.",
            hint="Pick a change from the list on the home page.",
        )
    return rows[0]


def _latest_release() -> str:
    result = ro_query(KB, K14)
    rows = _rows(result)
    if not rows:
        return "2026-10"
    return str(rows[-1]["release"])


def _expert_panel(submissions: list[dict]) -> dict | None:
    for s in submissions:
        if int(s.get("stars") or 0) >= 3:
            return {
                "scv": s.get("scv"),
                "submitter": s.get("submitter"),
                "cls": s.get("cls"),
                "evaluated": s.get("evaluated"),
            }
    return None


def _mark_differs(submissions: list[dict], panel: dict | None) -> list[dict]:
    if not panel:
        for s in submissions:
            s["differs_from_panel"] = False
        return submissions
    panel_actionable = panel.get("cls") in ("P", "LP")
    for s in submissions:
        s["differs_from_panel"] = (s.get("cls") in ("P", "LP")) != panel_actionable
    return submissions
