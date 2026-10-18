"""G011: queries.py matches docs/queries.cypher after whitespace normalisation."""

from __future__ import annotations

import re
from pathlib import Path

from app.graph.queries import QUERIES

HEADER = re.compile(r"^// ([A-Z][A-Z0-9_]*): ")
EXPECTED_COUNT = 81


def _repo_root() -> Path:
    for parent in Path(__file__).resolve().parents:
        if (parent / "docs" / "queries.cypher").is_file():
            return parent
    raise FileNotFoundError("docs/queries.cypher")


def _norm(text: str) -> str:
    lines = [re.sub(r"[ \t]+", " ", line).strip() for line in text.splitlines()]
    return "\n".join(line for line in lines if line)


def _blocks(text: str) -> dict[str, str]:
    blocks: dict[str, list[str]] = {}
    order: list[str] = []
    current: str | None = None
    buf: list[str] = []

    def flush() -> None:
        nonlocal buf
        if current is None:
            buf = []
            return
        body = "\n".join(line for line in buf if not line.startswith("//")).strip("\n")
        if body.strip():
            blocks[current] = body
            order.append(current)
        buf = []

    for line in text.splitlines():
        match = HEADER.match(line)
        if match:
            flush()
            current = match.group(1)
            continue
        if current is not None:
            buf.append(line)
    flush()
    return {name: blocks[name] for name in order}


def test_every_named_query_matches_the_cypher_file() -> None:
    source = (_repo_root() / "docs" / "queries.cypher").read_text()
    blocks = _blocks(source)
    assert len(blocks) == EXPECTED_COUNT
    assert len(QUERIES) == EXPECTED_COUNT
    assert tuple(QUERIES) == tuple(blocks)
    for name, body in blocks.items():
        assert _norm(QUERIES[name]) == _norm(body), name
