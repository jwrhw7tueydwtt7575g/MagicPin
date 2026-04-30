from Project.store.state import StateStore


def test_upsert_rejects_stale_version():
    store = StateStore()
    ok, _ = store.upsert_context('merchant', 'm1', 2, {'x': 1})
    assert ok
    ok, current = store.upsert_context('merchant', 'm1', 1, {'x': 2})
    assert not ok
    assert current == 2
