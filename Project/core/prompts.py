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
        'Return strict JSON with ONLY keys: body, rationale. '
        'You must NEVER write the category slug (e.g. "dentists", "salons", "pharmacies") literally in the body. '
        'Refer to the category naturally in prose only if required. '
        'Keep body concise. Never end the body with a trailing parenthetical. '
        'When cta is yes_stop, invite a binary action (YES/STOP; for clinical recall, prefer booking-focused YES/NO). '
        f'{variant_suffix}'
    )


def build_user_prompt(category: dict, merchant: dict, trigger: dict, customer: dict | None, language_style: str, cta: str) -> str:
    variant = _pick_prompt_variant(merchant, trigger)
    kind = (trigger.get('kind') or '').lower()
    payload = trigger.get('payload', {})
    
    guidance = ""
    if 'regulation' in kind or 'compliance' in kind:
        guidance = "This is a compliance alert. Focus on the deadline and necessary audit actions."
    elif 'competitor' in kind:
        comp_name = payload.get('competitor_name', 'a new competitor')
        distance = payload.get('distance_km', '?')
        offer = payload.get('their_offer', 'unspecified offers')
        guidance = (
            f"Competitor Alert: {comp_name} opened {distance}km away offering {offer}. "
            "Focus on the merchant's established trust and quality. Suggest highlighting these in GBP."
        )
    elif 'recall' in kind or 'appointment' in kind:
        guidance = (
            "This is a patient recall/reminder. Use a professional, clinical tone. "
            "NEVER use 'STOP to opt out' or 'STOP to ignore'. Use 'Reply YES to book, or NO if not this month'."
        )
    elif 'perf_' in kind:
        guidance = f"Performance update: {payload.get('metric','metrics')} changed {payload.get('delta_pct','?')}%. Suggest concrete growth action."
    elif 'ipl_match' in kind:
        match = payload.get('match', 'tonight\'s match')
        venue = payload.get('venue', 'nearby')
        time = payload.get('match_time_iso', 'tonight')
        guidance = f"IPL Match: {match} at {venue}, {time}. Suggest timely match-day promo or combo."

    # Context Summarization
    offers = [o.get('title') for o in merchant.get('offers', []) if o.get('status') == 'active']
    signals = merchant.get('signals', [])
    summary = {
        'category': {
            'slug_hidden': True,
            'voice': category.get('voice', {}).get('tone'),
            'taboos': category.get('voice', {}).get('vocab_taboo', []),
            'peer_avg_ctr': category.get('peer_stats', {}).get('avg_ctr'),
        },
        'merchant': {
            'name': merchant.get('identity', {}).get('name'),
            'city': merchant.get('identity', {}).get('city'),
            'ctr': merchant.get('performance', {}).get('ctr'),
            'active_offers': offers[:3],
            'signals': signals[:3],
        },
        'trigger': {
            'kind': kind,
            'urgency': trigger.get('urgency'),
            'payload': payload,
        },
        'customer': {
            'name': customer.get('identity', {}).get('name') if customer else None,
            'state': customer.get('state') if customer else None,
        },
        'style': language_style,
        'cta_type': cta,
        'guidance': guidance,
    }

    return (
        'Compose one WhatsApp message and rationale using this context summary. '
        'Follow guidance strictly. Output ONLY JSON with "body" and "rationale" keys.\n' + json.dumps(summary, ensure_ascii=True)
    )


def build_prompt_metadata(merchant: dict, trigger: dict) -> dict[str, str]:
    variant = _pick_prompt_variant(merchant, trigger)
    return {'prompt_version': PROMPT_VERSION, 'prompt_variant': variant}
