from fastapi.testclient import TestClient

from Project.app import app


client = TestClient(app)


def test_healthz_ok():
    response = client.get('/v1/healthz')
    assert response.status_code == 200
    assert response.json()['status'] == 'ok'


def test_context_and_tick_flow():
    client.post('/v1/context', json={'scope': 'category', 'context_id': 'dentists', 'version': 1, 'payload': {'slug': 'dentists'}, 'delivered_at': '2026-01-01T00:00:00Z'})
    client.post('/v1/context', json={'scope': 'merchant', 'context_id': 'm1', 'version': 1, 'payload': {'merchant_id': 'm1', 'category_slug': 'dentists', 'identity': {'name': 'M1', 'languages': ['en']}}, 'delivered_at': '2026-01-01T00:00:00Z'})
    client.post('/v1/context', json={'scope': 'trigger', 'context_id': 't1', 'version': 1, 'payload': {'id': 't1', 'scope': 'merchant', 'kind': 'research_digest', 'merchant_id': 'm1', 'customer_id': None, 'urgency': 1, 'suppression_key': 's1'}, 'delivered_at': '2026-01-01T00:00:00Z'})

    tick = client.post('/v1/tick', json={'now': '2026-01-01T01:00:00Z', 'available_triggers': ['t1']})
    assert tick.status_code == 200
    assert 'actions' in tick.json()


def test_context_invalid_scope_returns_400():
    response = client.post(
        '/v1/context',
        json={
            'scope': 'invalid_scope',
            'context_id': 'x1',
            'version': 1,
            'payload': {'foo': 'bar'},
            'delivered_at': '2026-01-01T00:00:00Z',
        },
    )
    assert response.status_code == 400
    body = response.json()
    assert body['accepted'] is False
    assert body['reason'] == 'invalid_scope'


def test_context_stale_version_returns_409_without_detail_wrapper():
    client.post(
        '/v1/context',
        json={
            'scope': 'merchant',
            'context_id': 'm_stale',
            'version': 2,
            'payload': {'merchant_id': 'm_stale', 'category_slug': 'dentists'},
            'delivered_at': '2026-01-01T00:00:00Z',
        },
    )
    response = client.post(
        '/v1/context',
        json={
            'scope': 'merchant',
            'context_id': 'm_stale',
            'version': 1,
            'payload': {'merchant_id': 'm_stale', 'category_slug': 'dentists'},
            'delivered_at': '2026-01-01T00:00:00Z',
        },
    )
    assert response.status_code == 409
    body = response.json()
    assert body['accepted'] is False
    assert body['reason'] == 'stale_version'
    assert body['current_version'] == 2


def test_reply_creates_missing_conversation_and_returns_200():
    response = client.post(
        '/v1/reply',
        json={
            'conversation_id': 'conv_missing',
            'merchant_id': 'm_missing',
            'customer_id': None,
            'from_role': 'merchant',
            'message': 'Ok lets do it. Whats next?',
            'received_at': '2026-01-01T00:00:00Z',
            'turn_number': 1,
        },
    )
    assert response.status_code == 200
    assert response.json()['action'] in {'send', 'wait', 'end'}


def test_auto_reply_loop_ends_on_repeat():
    conv_id = 'conv_auto_loop'
    for turn in range(1, 4):
        response = client.post(
            '/v1/reply',
            json={
                'conversation_id': conv_id,
                'merchant_id': 'm_auto',
                'customer_id': None,
                'from_role': 'merchant',
                'message': 'Thank you for contacting us! Our team will respond shortly.',
                'received_at': '2026-01-01T00:00:00Z',
                'turn_number': turn,
            },
        )
        assert response.status_code == 200
    assert response.json()['action'] == 'end'
