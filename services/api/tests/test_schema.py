"""G012: schema bootstrap is idempotent."""

from app.graph.schema import apply_schema


def test_schema_applies_twice() -> None:
    apply_schema()
    apply_schema()
