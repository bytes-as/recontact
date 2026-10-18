"""Apply SCHEMA_KB, SCHEMA_LAB and SCHEMA_HS. Index creation is idempotent."""

from __future__ import annotations

import logging

from app.graph.db import list_graphs, query
from app.graph.queries import SCHEMA_HS, SCHEMA_KB, SCHEMA_LAB

log = logging.getLogger("recontact.schema")


def statements(block: str) -> list[str]:
    return [part.strip() for part in block.split(";") if part.strip()]


def _block_for(name: str) -> str | None:
    if name == "kb" or name.startswith("kb_"):
        return SCHEMA_KB
    if name.startswith("lab_") or name.endswith("_lab"):
        return SCHEMA_LAB
    if name.startswith("hs_") or name.endswith("_hs"):
        return SCHEMA_HS
    return None


def apply_schema() -> None:
    names = set(list_graphs())
    names.add("kb")
    for name in sorted(names):
        block = _block_for(name)
        if block is None:
            continue
        for statement in statements(block):
            try:
                query(name, statement)
            except Exception as exc:
                if "already indexed" in str(exc).lower():
                    continue
                raise
        log.info("schema applied on %s", name)
