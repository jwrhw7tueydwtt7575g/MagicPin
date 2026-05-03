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


def _get_digest_item(payload: dict) -> dict | None:
    """Look up digest item details from trigger payload."""
    items = payload.get('items', [])
    top_id = payload.get('top_item_id')
    if top_id and items:
        return next((i for i in items if i.get('id') == top_id), items[0] if items else None)
    if items:
        return items[0]
    # Also try direct keys in payload
    if payload.get('title') or payload.get('summary'):
        return payload
    return None


def _build_guidance(kind: str, payload: dict, customer: dict | None) -> str:
    """Build rich, kind-specific guidance with real data from the payload."""
    if 'regulation' in kind or 'compliance' in kind:
        deadline = payload.get('deadline') or payload.get('effective_date', 'the upcoming deadline')
        summary = payload.get('regulation_summary') or payload.get('change_summary', '')
        action = payload.get('required_action') or payload.get('audit_action', 'audit equipment and update SOPs')
        return (
            f"B2B_ALERT: This is a compliance message to a MERCHANT (business owner), NOT a consumer. "
            f"The merchant must take action before {deadline}. "
            f"Summary: {summary or 'new regulations announced'}. "
            f"Required action: {action}. "
            f"Use professional B2B language. Focus on deadline, audit steps, and what the merchant must do."
        )
    elif 'competitor' in kind:
        comp_name = payload.get('competitor_name', 'a new competitor')
        distance = payload.get('distance_km', '?')
        offer = payload.get('their_offer', 'discounts')
        return (
            f"B2B_ALERT to merchant: {comp_name} opened {distance}km away offering {offer}. "
            f"Help the merchant differentiate — highlight established trust, quality, and GBP presence."
        )
    elif 'recall' in kind or 'appointment' in kind:
        slots = payload.get('available_slots', [])
        slot_labels = [s.get('label') for s in slots if s.get('label')]
        slot_str = ' or '.join(slot_labels) if slot_labels else 'upcoming slots'
        service = payload.get('service_due', 'check-up')
        return (
            f"PATIENT_RECALL: Clinical tone only. "
            f"Service due: {service}. Specific slots available: {slot_str}. "
            f"Show both slot options so patient can pick by replying 1 or 2. "
            f"NEVER use 'STOP to opt out'. Binary: 'Reply YES to book, or NO if not this month'. "
            f"Address patient by name."
        )
    elif 'research_digest' in kind:
        item = _get_digest_item(payload)
        if item:
            title = item.get('title', '')
            summary = item.get('summary', '')
            source = item.get('source', '')
            stat = item.get('key_stat', '')
            return (
                f"B2B research digest to merchant. Key finding: {title or summary}. "
                f"{f'Key stat: {stat}. ' if stat else ''}"
                f"{f'Source: {source}.' if source else ''} "
                f"Help the merchant apply this insight to their practice."
            )
        return "B2B research digest. Share the top finding and how the merchant can apply it."
    elif 'perf_dip' in kind or 'perf_spike' in kind:
        metric = payload.get('metric', 'performance')
        delta = payload.get('delta_pct')
        delta_str = f'{delta:+.0%}' if delta is not None else 'significantly'
        direction = 'dropped' if 'dip' in kind else 'spiked'
        return (
            f"B2B_ALERT to merchant: Your {metric} {direction} {delta_str}. "
            f"Suggest one concrete, specific action to address this this week."
        )
    elif 'ipl_match' in kind:
        match = payload.get('match', "tonight's match")
        venue = payload.get('venue', 'nearby')
        time = payload.get('match_time_iso', 'tonight')
        return (
            f"B2B opportunity for merchant: IPL match — {match} at {venue}, {time}. "
            f"Suggest a specific match-day promo or combo offer they can run today."
        )
    elif 'competitor_opened' in kind:
        comp_name = payload.get('competitor_name', 'a competitor')
        distance = payload.get('distance_km', '?')
        offer = payload.get('their_offer', 'discounts')
        return (
            f"B2B_ALERT: {comp_name} opened {distance}km away offering {offer}. "
            f"Help merchant differentiate with unique strengths and GBP optimization."
        )
    return "B2B engagement message to merchant. Be specific and actionable."


def build_user_prompt(category: dict, merchant: dict, trigger: dict, customer: dict | None, language_style: str, cta: str) -> str:
    kind = (trigger.get('kind') or '').lower()
    payload = trigger.get('payload', {})

    guidance = _build_guidance(kind, payload, customer)

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
        'context_type': 'B2B' if not customer else 'B2C_PATIENT_RECALL',
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
            'IMPORTANT: context_type=B2B means you are writing TO a merchant (business owner), not a patient/consumer. '
            'Use the merchant name, active_offers, signals, and real data in the body. '
            'Be specific — mention real offer prices, lapsed patient counts, or performance numbers. '
            'Do NOT add a character limit. Write as long as needed to be clear and actionable.'
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
