from __future__ import annotations

import json
from hashlib import sha1


PROMPT_VERSION = 'v1.1.0'


def _pick_prompt_variant(merchant: dict, trigger: dict) -> str:
    seed = f"{merchant.get('merchant_id','')}::{trigger.get('id','')}"
    shard = int(sha1(seed.encode('utf-8')).hexdigest(), 16) % 2
    return 'A' if shard == 0 else 'B'


def build_system_prompt(variant: str) -> str:
    variant_suffix = 'Prioritize concise actionability.' if variant == 'A' else 'Prioritize merchant empathy with concise actionability.'
    return (
        'You are a deterministic WhatsApp message composer for merchant engagement. '
        'Never hallucinate facts. Use only provided context. '
        'Return strict JSON with keys: body, rationale. Keep body concise.'
        f' {variant_suffix}'
    )


def build_user_prompt(category: dict, merchant: dict, trigger: dict, customer: dict | None, language_style: str, cta: str) -> str:
    variant = _pick_prompt_variant(merchant, trigger)
    payload = {
        'category': category,
        'merchant': merchant,
        'trigger': trigger,
        'customer': customer,
        'language_style': language_style,
        'cta': cta,
        'prompt_version': PROMPT_VERSION,
        'prompt_variant': variant,
    }
    return (
        'Compose one WhatsApp message and rationale using only this context JSON. '
        'Do not add missing facts. Output JSON only.\n' + json.dumps(payload, ensure_ascii=True)
    )


def build_prompt_metadata(merchant: dict, trigger: dict) -> dict[str, str]:
    variant = _pick_prompt_variant(merchant, trigger)
    return {'prompt_version': PROMPT_VERSION, 'prompt_variant': variant}
