"""Pydantic models for kb responses, matching docs/API.md shared types."""

from __future__ import annotations

from pydantic import BaseModel

DISCLAIMER = (
    "Decision support for genetic counsellors. Not medical advice. "
    "Nothing is sent without a named counsellor's approval. "
    "People and organisations shown are fictional; ClinVar data are real."
)


class Change(BaseModel):
    change_id: str
    release: str
    kind: str
    vcv: int
    variant: str
    gene: str
    scv: str
    submitter_id: str
    submitter: str
    from_cls: str
    to_cls: str
    from_version: int
    to_version: int
    submitter_evaluated: str | None
    inheritance: str | None = None
    review_always: bool | None = None
    review_reason: str | None = None


class SubmitterRank(BaseModel):
    submitter_id: str
    submitter: str
    changes: int
    actionable_changes: int


class ReleaseSummaryRow(BaseModel):
    kind: str
    pruning_valid: bool
    changes: int


class Submission(BaseModel):
    scv: str
    version: int
    cls: str
    cls_raw: str
    stars: int
    review: str
    evaluated: str | None
    since_release: str
    submitter: str
    submitter_id: str
    differs_from_panel: bool = False


class VariantStatus(BaseModel):
    vcv: int
    variant: str
    gene: str | None
    inheritance: str | None
    review_always: bool | None
    aggregate: dict
    as_of: str
    submissions: list[Submission]
    history: list[dict]
    panel: dict | None
    source: str
    source_line: str
    note: str | None
    disclaimer: str = DISCLAIMER
