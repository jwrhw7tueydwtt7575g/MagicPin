from __future__ import annotations

from datetime import datetime, timezone


def _parse_iso(ts: str | None) -> datetime | None:
    if not ts:
        return None
    txt = ts.replace('Z', '+00:00')
    return datetime.fromisoformat(txt)


def pick_eligible_trigger_ids(store, available_triggers: list[str], now: str, cap: int) -> list[str]:
    now_dt = _parse_iso(now) or datetime.now(timezone.utc)
    scored: list[tuple[int, str]] = []

    for trigger_id in available_triggers:
        trigger = store.get_context('trigger', trigger_id)
        if not trigger:
            continue
        suppression_key = trigger.get('suppression_key')
        if suppression_key and store.is_suppressed(suppression_key):
            continue
        exp = _parse_iso(trigger.get('expires_at'))
        if exp and exp < now_dt:
            continue
        urgency = int(trigger.get('urgency', 0))
        scored.append((urgency, trigger_id))

    scored.sort(reverse=True)
    return [trigger_id for _, trigger_id in scored[:cap]]
