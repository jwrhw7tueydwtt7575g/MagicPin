from __future__ import annotations

import re

from Project.core.lang import pick_language_style
from Project.core.prompts import build_prompt_metadata, build_system_prompt, build_user_prompt
from Project.core.rules import derive_cta, derive_send_as, pick_template_name, sanitize_body

# Patient-facing clinical reminders: binary without marketing-style STOP opt-out wording.
_CLINICAL_CUSTOMER_RECALL_KINDS = frozenset(
    {
        'recall_due',
        'appointment_reminder',
        'appointment_tomorrow',
        'chronic_refill_due',
    }
)

_STOP_CTA_SENTENCE_RE = re.compile(
    r'\s*reply\s+yes\b[^.?!]*(?:\bor\s*)?\bstop\b[^.?!]*[.?!]?',
    re.IGNORECASE,
)


def strip_trailing_category_parenthetical(body: str, category_slug: str | None) -> str:
    """Remove a trailing `` (<slug>)`` if present (LLM or legacy suffix leak)."""
    slug = (category_slug or '').strip()
    if not slug or not body:
        return body
    trimmed = body.rstrip()
    tail = f' ({slug.lower()})'
    if trimmed.lower().endswith(tail):
        return trimmed[: -(len(slug) + 3)].rstrip()
    return trimmed


class Composer:
    def __init__(self, groq_client) -> None:
        self.groq_client = groq_client

    async def compose(self, category: dict, merchant: dict, trigger: dict, customer: dict | None = None) -> dict:
        send_as = derive_send_as(trigger)
        cta = derive_cta(trigger)
        language_style = pick_language_style(merchant, customer)

        prompt_meta = build_prompt_metadata(merchant, trigger)
        system_prompt = build_system_prompt(prompt_meta['prompt_variant'])
        user_prompt = build_user_prompt(category, merchant, trigger, customer, language_style, cta)
        llm_output = await self.groq_client.compose_json(system_prompt, user_prompt)

        fallback_body, fallback_rationale = self._rule_based_message(category, merchant, trigger, customer)
        body = sanitize_body(llm_output.get('body', ''), fallback_body)
        body = self._align_body_with_cta(body, cta, trigger, customer, category)
        rationale = llm_output.get('rationale', fallback_rationale)
        body = strip_trailing_category_parenthetical(body, category.get('slug'))

        return {
            'body': body,
            'cta': cta,
            'send_as': send_as,
            'template_name': pick_template_name(trigger, send_as),
            'template_params': self._template_params(merchant, trigger),
            'suppression_key': trigger.get('suppression_key') or f"{trigger.get('kind','generic')}:{merchant.get('merchant_id')}",
            'rationale': rationale,
            'prompt_version': prompt_meta['prompt_version'],
            'prompt_variant': prompt_meta['prompt_variant'],
        }

    async def compose_customer_reply(
        self,
        merchant: dict,
        customer: dict,
        incoming_message: str,
        trigger_payload: dict,
        trigger_kind: str,
    ) -> dict:
        """Compose a customer-voiced slot-confirmation reply from the merchant/bot."""
        from Project.core.prompts import build_customer_reply_prompt, build_system_prompt
        system_prompt = build_system_prompt('A')
        user_prompt = build_customer_reply_prompt(
            merchant=merchant,
            customer=customer,
            incoming=incoming_message,
            trigger_payload=trigger_payload,
            trigger_kind=trigger_kind,
        )
        llm_output = await self.groq_client.compose_json(system_prompt, user_prompt)

        customer_name = customer.get('identity', {}).get('name', '') if customer else ''
        merchant_name = merchant.get('identity', {}).get('name', 'the clinic')
        slots = trigger_payload.get('available_slots', [])

        # Fallback: match the slot they mentioned
        fallback_body = self._slot_confirmation_fallback(
            customer_name=customer_name,
            merchant_name=merchant_name,
            incoming=incoming_message,
            slots=slots,
        )
        body = sanitize_body(llm_output.get('body', ''), fallback_body)
        rationale = llm_output.get('rationale', 'Customer slot-pick confirmed with booking details.')
        return {
            'action': 'send',
            'body': body,
            'cta': 'open_ended',
            'rationale': rationale,
        }

    def _template_params(self, merchant: dict, trigger: dict) -> list[str]:
        name = merchant.get('identity', {}).get('name') or merchant.get('merchant_id', 'merchant')
        kind = trigger.get('kind', 'update')
        return [str(name), str(kind)]

    def _rule_based_message(self, category: dict, merchant: dict, trigger: dict, customer: dict | None) -> tuple[str, str]:
        kind = (trigger.get('kind') or 'update').replace('_', ' ')
        merchant_name = merchant.get('identity', {}).get('name', 'your business')
        category_slug = category.get('slug', merchant.get('category_slug', 'category'))
        payload = trigger.get('payload', {})
        top_item_id = payload.get('top_item_id')
        metric = payload.get('metric')
        delta_pct = payload.get('delta_pct')

        if customer:
            customer_name = customer.get('identity', {}).get('name', 'customer')
            body = f"Hi {customer_name}, this is {merchant_name}. Your {kind} update is due."
            rationale = 'Customer-scoped trigger with explicit consent-safe action.'
            return body, rationale

        if 'ipl match' in kind:
            match = payload.get('match', 'tonight\'s match')
            venue = payload.get('venue', 'nearby')
            time = payload.get('match_time_iso', 'tonight')
            body = f"{merchant_name}: {match} at {venue} {time}. How about a match-night combo to drive covers? Want me to draft a quick banner?"
            return body, 'IPL match-night trigger with payload details'

        if 'competitor opened' in kind:
            comp_name = payload.get('competitor_name', 'a new competitor')
            distance = payload.get('distance_km', '?')
            offer = payload.get('their_offer', 'discounts')
            body = f"{merchant_name}: {comp_name} opened {distance}km away offering {offer}. We can update your profile to highlight your unique quality. Interested?"
            return body, 'Competitor differentiation fallback'

        if 'regulation change' in kind or 'compliance' in kind:
            body = f"{merchant_name}: New industry regulations have been announced. We need to audit your current equipment for compliance."
            rationale = 'Actionable compliance alert fallback.'
            return body, rationale

        if top_item_id:
            body = (
                f"{merchant_name}: new {category_slug} digest item {top_item_id} is relevant to your profile. "
                "Want a 2-line takeaway you can use today?"
            )
            rationale = 'Uses trigger digest anchor.'
            return body, rationale
        if metric and delta_pct is not None:
            body = (
                f"{merchant_name}: your {metric} changed {delta_pct:+.0%} recently. "
                "I can draft one quick fix for this week."
            )
            rationale = 'Uses merchant performance delta from trigger payload with clear next action.'
            return body, rationale

        body = f"Hi {merchant_name}, {kind} is active for your {category_slug} listing."
        rationale = 'Deterministic fallback grounded in merchant, category, and trigger kind.'
        return body, rationale


    def _is_clinical_customer_recall(self, trigger: dict, customer: dict | None) -> bool:
        if customer is None:
            return False
        kind = (trigger.get('kind') or '').lower()
        return kind in _CLINICAL_CUSTOMER_RECALL_KINDS

    def _align_body_with_cta(self, body: str, cta: str, trigger: dict, customer: dict | None, category: dict) -> str:
        txt = body.strip()
        if cta == 'yes_stop':
            if self._is_clinical_customer_recall(trigger, customer):
                txt = self._force_clinical_yes_no(txt)
                return txt
            lower = txt.lower()
            if 'reply yes' not in lower and 'stop' not in lower:
                txt = f'{txt} Reply YES to continue or STOP to opt out.'
            return txt
        if cta == 'none':
            for fragment in (
                'Reply YES to continue or STOP to opt out.',
                'Reply YES to act or STOP to pause.',
                'Reply YES to book or STOP to cancel.',
                'Reply YES to book, or NO if not this month.',
            ):
                txt = txt.replace(fragment, '').strip()
            return txt
        return txt

    def _force_clinical_yes_no(self, body: str) -> str:
        txt = _STOP_CTA_SENTENCE_RE.sub('', body).strip()
        if txt and txt[-1] not in '.!?':
            txt = f'{txt}.'
        return f'{txt} Reply YES to book, or NO if not this month.'.strip()

    def _slot_confirmation_fallback(
        self,
        customer_name: str,
        merchant_name: str,
        incoming: str,
        slots: list[dict],
    ) -> str:
        """Match customer's message to a slot label, confirm it explicitly."""
        incoming_lower = incoming.lower()
        matched_slot = None
        for slot in slots:
            label = slot.get('label', '')
            # Check if any part of the slot label appears in customer's message
            parts = label.lower().split()
            if any(p in incoming_lower for p in parts if len(p) > 2):
                matched_slot = label
                break

        if matched_slot:
            name_part = f'Hi {customer_name}, ' if customer_name else ''
            return (
                f'{name_part}your booking at {merchant_name} is confirmed for {matched_slot}. '
                f'Please arrive 5 minutes early. See you then!'
            )
        # Generic fallback if no slot matched
        name_part = f'Hi {customer_name}, ' if customer_name else ''
        return (
            f'{name_part}thank you for confirming! Your appointment at {merchant_name} has been noted. '
            f'We will send you a reminder closer to the date.'
        )
