from __future__ import annotations

from Project.core.lang import pick_language_style
from Project.core.prompts import build_prompt_metadata, build_system_prompt, build_user_prompt
from Project.core.rules import derive_cta, derive_send_as, pick_template_name, sanitize_body


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
        body = self._align_body_with_cta(body, cta)
        rationale = llm_output.get('rationale', fallback_rationale)
        body = self._enforce_category_specificity(body, category, merchant)

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
            rationale = 'Customer-scoped trigger with explicit consent-safe YES/STOP action.'
            return body, rationale

        if top_item_id:
            body = (
                f"{merchant_name}: new {category_slug} digest item {top_item_id} is relevant to your profile. "
                "Want a 2-line takeaway you can use today?"
            )
            rationale = 'Uses trigger digest anchor and category to drive curiosity with a single CTA.'
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

    def _enforce_category_specificity(self, body: str, category: dict, merchant: dict) -> str:
        category_slug = str(category.get('slug', '')).strip()
        merchant_name = merchant.get('identity', {}).get('name')
        if category_slug and category_slug.lower() not in body.lower():
            body = f"{body} ({category_slug})"
        if merchant_name and merchant_name.lower() not in body.lower():
            body = f"{merchant_name}: {body}"
        return body

    def _align_body_with_cta(self, body: str, cta: str) -> str:
        txt = body.strip()
        if cta == 'yes_stop':
            lower = txt.lower()
            if 'reply yes' not in lower and 'stop' not in lower:
                txt = f'{txt} Reply YES to continue or STOP to opt out.'
            return txt
        if cta == 'none':
            for fragment in ('Reply YES to continue or STOP to opt out.', 'Reply YES to act or STOP to pause.'):
                txt = txt.replace(fragment, '').strip()
            return txt
        return txt
