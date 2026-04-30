from __future__ import annotations

import hashlib


def hash_body(text: str) -> str:
    return hashlib.sha1(text.strip().lower().encode('utf-8')).hexdigest()
