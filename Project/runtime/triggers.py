from __future__ import annotations


def explain_tick_pick_skip(store, trigger_id: str) -> str | None:
    """Why a trigger id would not enter the scored tick list (before urgency cap).

    ``available_triggers`` is treated as authoritative: expiry is not a skip reason here.
    """
    trigger = store.get_context('trigger', trigger_id)
    if not trigger:
        return 'missing_trigger_context'
    suppression_key = trigger.get('suppression_key')
    if suppression_key and store.is_suppressed(suppression_key):
        return 'suppression_key_active'
    return None


def pick_eligible_trigger_ids(store, available_triggers: list[str], now: str, cap: int) -> list[str]:
    scored: list[tuple[int, str]] = []

    for trigger_id in available_triggers:
        trigger = store.get_context('trigger', trigger_id)
        if not trigger:
            continue
        suppression_key = trigger.get('suppression_key')
        if suppression_key and store.is_suppressed(suppression_key):
            continue
        urgency = int(trigger.get('urgency', 0))
        scored.append((urgency, trigger_id))

    scored.sort(reverse=True)
    return [trigger_id for _, trigger_id in scored[:cap]]
