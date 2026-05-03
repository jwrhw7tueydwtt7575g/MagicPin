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
        slots = payload.get('available_slots', [])
        slot_labels = [s.get('label') for s in slots if s.get('label')]
        slot_str = ' or '.join(slot_labels) if slot_labels else 'upcoming slots'
        guidance = (
            f"Patient recall/reminder. Clinical tone only. "
            f"Offer these specific slots: {slot_str}. "
            f"NEVER use 'STOP to opt out' or 'STOP to ignore'. Binary: 'Reply YES to book, or NO if not this month'."
        )
    elif 'perf_' in kind:
        guidance = f"Performance update: {payload.get('metric','metrics')} changed {payload.get('delta_pct','?')}%. Suggest concrete growth action."
    elif 'ipl_match' in kind:
        match = payload.get('match', "tonight's match")
        venue = payload.get('venue', 'nearby')
        time = payload.get('match_time_iso', 'tonight')
        guidance = f"IPL Match: {match} at {venue}, {time}. Suggest timely match-day promo or combo."

    # --- Enriched merchant context ---
    identity = merchant.get('identity', {})
    perf = merchant.get('performance', {})
    offers = [o.get('title') for o in merchant.get('offers', []) if o.get('status') == 'active']
    signals = merchant.get('signals', [])
    review_themes = merchant.get('review_themes', [])
    cust_agg = merchant.get('customer_aggregate', {})
    top_pos_theme = next((t for t in review_themes if t.get('sentiment') == 'pos'), None)
    top_neg_theme = next((t for t in review_themes if t.get('sentiment') == 'neg'), None)

    summary = {
        'category': {
            'slug_hidden': True,
            'voice': category.get('voice', {}).get('tone'),
            'taboos': category.get('voice', {}).get('vocab_taboo', []),
            'peer_avg_ctr': category.get('peer_stats', {}).get('avg_ctr'),
        },
        'merchant': {
            'name': identity.get('name'),
            'owner_first_name': identity.get('owner_first_name'),
            'city': identity.get('city'),
            'locality': identity.get('locality'),
            'ctr': perf.get('ctr'),
            'views': perf.get('views'),
            'calls': perf.get('calls'),
            'active_offers': offers[:3],
            'signals': signals[:5],
            'lapsed_customers': cust_agg.get('lapsed_180d_plus'),
            'top_positive_review': top_pos_theme.get('common_quote') if top_pos_theme else None,
            'top_negative_review': top_neg_theme.get('common_quote') if top_neg_theme else None,
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
        'instruction': (
            'Use the merchant name, active_offers, signals, and review quotes in the body where relevant. '
            'Be specific: mention clinic name, real offer prices, or lapsed patient numbers. '
            'Keep body under 160 characters for WhatsApp readability.'
        ),
    }

    return (
        'Compose one WhatsApp message and rationale using this context summary. '
        'Follow guidance strictly. Output ONLY JSON with "body" and "rationale" keys.\n' + json.dumps(summary, ensure_ascii=True)
    )


def build_customer_reply_prompt(
    merchant: dict,
    customer: dict,
    incoming: str,
    trigger_payload: dict,
    trigger_kind: str,
) -> str:
    """Build a prompt to compose a customer-facing slot-confirmation reply."""
    merchant_name = merchant.get('identity', {}).get('name', 'the clinic')
    customer_name = customer.get('identity', {}).get('name') if customer else None
    slots = trigger_payload.get('available_slots', [])
    slot_labels = [s.get('label') for s in slots if s.get('label')]
    service = trigger_payload.get('service_due', trigger_kind)

    summary = {
        'role': 'You are a warm, professional assistant for the clinic/merchant, responding to a customer.',
        'merchant_name': merchant_name,
        'customer_name': customer_name,
        'customer_message': incoming,
        'service': service,
        'available_slots': slot_labels,
        'instruction': (
            f'The customer said: "{incoming}". '
            f'They are booking or confirming a {service} appointment. '
            f'Identify which slot they want from their message and confirm it specifically by name. '
            f'Address the customer by their first name ({customer_name}). '
            f'Be warm and professional. Keep body under 160 characters. '
            f'Output ONLY JSON with "body" and "rationale" keys.'
        ),
    }
    return 'Compose a customer-facing booking confirmation.\n' + json.dumps(summary, ensure_ascii=True)


def build_prompt_metadata(merchant: dict, trigger: dict) -> dict[str, str]:
    variant = _pick_prompt_variant(merchant, trigger)
    return {'prompt_version': PROMPT_VERSION, 'prompt_variant': variant}
