"""Token checks. Only a sha256 is retained; comparison is constant time."""

from __future__ import annotations

import hashlib
import hmac


def token_hash(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()


def tokens_equal(presented: str, expected: str) -> bool:
    return hmac.compare_digest(presented, expected)
