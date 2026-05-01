from __future__ import annotations

import json
from hashlib import sha1


PROMPT_VERSION = 'v1.2.0'


def _pick_prompt_variant(merchant: dict, trigger: dict) -> str:
    seed = f"{merchant.get('merchant_id','')}::{trigger.get('id','')}"
    shard = int(sha1(seed.encode('utf-8')).hexdigest(), 16) % 2
    return 'A' if shard == 0 else 'B'


def build_system_prompt(variant: str) -> str:
    variant_suffix = 'Prioritize concise actionability.' if variant == 'A' else 'Prioritize merchant empathy with concise actionability.'
    return (
        'You are a deterministic WhatsApp message composer for merchant engagement. '
        'Never hallucinate facts. Use only provided context. '
        'Return strict JSON with keys: body, rationale. Keep body concise. '
        'Never end the body with a trailing parenthetical like (dentists) or (category_slug); '
        'weave category naturally in prose if needed. '
        'When cta is yes_stop, the body must invite the same binary action the channel will use '
        '(YES/STOP for merchant or promo flows; for patient clinical recall in dentists, prefer '
        'booking-focused YES/NO language, never marketing unsubscribe phrasing). '
        f'{variant_suffix}'
    )


def build_user_prompt(category: dict, merchant: dict, trigger: dict, customer: dict | None, language_style: str, cta: str) -> str:
    variant = _pick_prompt_variant(merchant, trigger)
    kind = (trigger.get('kind') or '').lower()
    guidance = ""
    if 'regulation' in kind or 'compliance' in kind:
        guidance = "This is a compliance alert. Focus on the deadline and necessary audit actions."
    elif 'competitor' in kind:
        guidance = "A new competitor is mentioned. Focus on the merchant's unique value proposition and service quality."
    elif 'recall' in kind or 'appointment' in kind:
        guidance = "This is a patient recall/reminder. Use a professional, clinical tone. Avoid marketing hype."
    elif 'perf_' in kind:
        guidance = "This is a performance update. Use specific metrics and suggest a concrete growth action."
    elif 'ipl_match' in kind:
        guidance = "This is a match-day event. Create a timely, event-specific promotion framing."
    
    payload = {
        'category': category,
        'merchant': merchant,
        'trigger': trigger,
        'customer': customer,
        'language_style': language_style,
        'cta': cta,
        'guidance': guidance,
        'prompt_version': PROMPT_VERSION,
        'prompt_variant': variant,
    }
    return (
        'Compose one WhatsApp message and rationale using the context JSON. '
        'Follow the "guidance" field if provided. Do not add missing facts. Output JSON only.\n' + json.dumps(payload, ensure_ascii=True)
    )


def build_prompt_metadata(merchant: dict, trigger: dict) -> dict[str, str]:
    variant = _pick_prompt_variant(merchant, trigger)
    return {'prompt_version': PROMPT_VERSION, 'prompt_variant': variant}
