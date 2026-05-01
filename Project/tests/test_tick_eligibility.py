from Project.runtime.triggers import explain_tick_pick_skip, pick_eligible_trigger_ids
from Project.store.state import StateStore


def test_pick_eligible_ignores_expired_when_explicitly_available():
    store = StateStore()
    tid = 'trg_expired_but_listed'
    store.upsert_context(
        'trigger',
        tid,
        1,
        {
            'id': tid,
            'scope': 'merchant',
            'kind': 'research_digest',
            'merchant_id': 'm_x',
            'customer_id': None,
            'urgency': 5,
            'suppression_key': 'sk_test',
            'expires_at': '2020-01-01T00:00:00Z',
        },
    )
    selected = pick_eligible_trigger_ids(store, [tid], '2026-05-01T01:00:00Z', 20)
    assert selected == [tid]


def test_explain_tick_pick_skip_missing_and_suppressed():
    store = StateStore()
    assert explain_tick_pick_skip(store, 'missing') == 'missing_trigger_context'

    tid = 't1'
    store.upsert_context(
        'trigger',
        tid,
        1,
        {'id': tid, 'merchant_id': 'm1', 'suppression_key': 'dup', 'urgency': 1},
    )
    assert explain_tick_pick_skip(store, tid) is None
    store.mark_suppression('dup')
    assert explain_tick_pick_skip(store, tid) == 'suppression_key_active'
