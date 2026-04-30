from __future__ import annotations

from typing import Literal

SendAs = Literal['vera', 'merchant_on_behalf']

ACTION_TRIGGER_KINDS = {
    'recall_due',
    'appointment_reminder',
    'appointment_tomorrow',
    'lead_followup',
    'promo_reactivation',
    'trial_followup',
    'chronic_refill_due',
    'customer_lapsed_soft',
}

INFO_TRIGGER_KINDS = {
    'research_digest',
    'regulation_change',
    'curious_ask_due',
    'festival_upcoming',
    'festival_campaign',
    'trend_alert',
    'milestone_reached',
}


def derive_send_as(trigger: dict) -> SendAs:
    return 'merchant_on_behalf' if trigger.get('scope') == 'customer' else 'vera'


def derive_cta(trigger: dict) -> str:
    kind = (trigger.get('kind') or '').lower()
    if kind in ACTION_TRIGGER_KINDS:
        return 'yes_stop'
    if kind in INFO_TRIGGER_KINDS or 'digest' in kind or 'research' in kind:
        return 'none'
    if kind in {'perf_dip', 'perf_spike', 'renewal_due', 'dormant_with_vera', 'review_theme_emerged', 'competitor_opened'}:
        return 'open_ended'
    return 'open_ended'


def pick_template_name(trigger: dict, send_as: str) -> str:
    kind = (trigger.get('kind') or 'generic').lower()
    prefix = 'vera' if send_as == 'vera' else 'merchant'
    return f'{prefix}_{kind}_v1'


def sanitize_body(body: str, fallback: str) -> str:
    txt = (body or '').strip()
    return txt if txt else fallback
