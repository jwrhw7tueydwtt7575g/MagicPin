import asyncio
from unittest.mock import AsyncMock, MagicMock

from Project.core.composer import Composer, strip_trailing_category_parenthetical


def test_strip_trailing_category_parenthetical():
    assert strip_trailing_category_parenthetical('Hello (dentists)', 'dentists') == 'Hello'
    assert strip_trailing_category_parenthetical('Hello (Dentists)', 'dentists') == 'Hello'
    assert strip_trailing_category_parenthetical('No suffix', 'dentists') == 'No suffix'


def test_align_clinical_customer_recall_no_stop_opt_out():
    c = Composer(None)
    category = {'slug': 'dentists'}
    trigger = {'kind': 'recall_due'}
    customer = {'identity': {'name': 'Pat'}}
    out = c._align_body_with_cta('Time for your check-up.', 'yes_stop', trigger, customer, category)
    assert 'stop to opt out' not in out.lower()
    assert 'reply yes' in out.lower()
    assert 'no if not' in out.lower()


def test_align_clinical_customer_recall_non_dentist_category():
    c = Composer(None)
    category = {'slug': 'gyms'}
    trigger = {'kind': 'recall_due'}
    customer = {'identity': {'name': 'Alex'}}
    out = c._align_body_with_cta('Membership health check due.', 'yes_stop', trigger, customer, category)
    assert 'stop to opt out' not in out.lower()
    assert 'reply yes' in out.lower()
    assert 'no if not' in out.lower()
    assert 'stop' not in out.lower()


def test_align_clinical_customer_recall_rewrites_existing_yes_stop_line():
    c = Composer(None)
    category = {'slug': 'gyms'}
    trigger = {'kind': 'recall_due'}
    customer = {'identity': {'name': 'Alex'}}
    out = c._align_body_with_cta(
        'Hi Alex, it is time for your next session. Reply YES to book or STOP to cancel.',
        'yes_stop',
        trigger,
        customer,
        category,
    )
    assert 'reply yes' in out.lower()
    assert 'no if not' in out.lower()
    assert 'stop' not in out.lower()


def test_compose_strips_trailing_slug_from_llm_body():
    groq = MagicMock()
    groq.compose_json = AsyncMock(
        return_value={
            'body': 'Your update is ready (dentists)',
            'rationale': 'test',
        }
    )
    composer = Composer(groq)
    category = {'slug': 'dentists'}
    merchant = {'merchant_id': 'm1', 'identity': {'name': 'Bright Smile'}}
    trigger = {
        'id': 't1',
        'kind': 'research_digest',
        'scope': 'merchant',
        'merchant_id': 'm1',
        'suppression_key': 'k1',
    }

    async def run():
        return await composer.compose(category, merchant, trigger, None)

    result = asyncio.run(run())
    assert not result['body'].rstrip().lower().endswith('(dentists)')
    assert '(dentists)' not in result['body']


def test_compose_clinical_customer_body_no_marketing_stop():
    groq = MagicMock()
    groq.compose_json = AsyncMock(
        return_value={
            'body': 'Hi Pat, your cleaning recall is due.',
            'rationale': 'test',
        }
    )
    composer = Composer(groq)
    category = {'slug': 'dentists'}
    merchant = {'merchant_id': 'm1', 'identity': {'name': 'Bright Smile'}}
    trigger = {
        'id': 't1',
        'kind': 'recall_due',
        'scope': 'customer',
        'merchant_id': 'm1',
        'customer_id': 'c1',
        'suppression_key': 'k1',
    }
    customer = {'identity': {'name': 'Pat'}}

    async def run():
        return await composer.compose(category, merchant, trigger, customer)

    result = asyncio.run(run())
    assert 'stop to opt out' not in result['body'].lower()


def test_compose_gym_customer_recall_no_marketing_stop():
    groq = MagicMock()
    groq.compose_json = AsyncMock(
        return_value={
            'body': 'Hi Alex, quick reminder about your membership check-in.',
            'rationale': 'test',
        }
    )
    composer = Composer(groq)
    category = {'slug': 'gyms'}
    merchant = {'merchant_id': 'm_gym', 'identity': {'name': 'Zen Yoga Studio'}}
    trigger = {
        'id': 't_gym_recall',
        'kind': 'recall_due',
        'scope': 'customer',
        'merchant_id': 'm_gym',
        'customer_id': 'c_gym',
        'suppression_key': 'k_gym',
    }
    customer = {'identity': {'name': 'Alex'}}

    async def run():
        return await composer.compose(category, merchant, trigger, customer)

    result = asyncio.run(run())
    assert 'stop to opt out' not in result['body'].lower()
    assert 'no if not' in result['body'].lower()


def test_compose_gym_customer_recall_rewrites_llm_yes_stop():
    groq = MagicMock()
    groq.compose_json = AsyncMock(
        return_value={
            'body': 'Hi Alex, time for your next session at Zen Yoga Studio. Reply YES to book or STOP to cancel.',
            'rationale': 'test',
        }
    )
    composer = Composer(groq)
    category = {'slug': 'gyms'}
    merchant = {'merchant_id': 'm_gym', 'identity': {'name': 'Zen Yoga Studio'}}
    trigger = {
        'id': 't_gym_recall',
        'kind': 'recall_due',
        'scope': 'customer',
        'merchant_id': 'm_gym',
        'customer_id': 'c_gym',
        'suppression_key': 'k_gym',
    }
    customer = {'identity': {'name': 'Alex'}}

    async def run():
        return await composer.compose(category, merchant, trigger, customer)

    result = asyncio.run(run())
    assert 'reply yes' in result['body'].lower()
    assert 'no if not' in result['body'].lower()
    assert 'stop' not in result['body'].lower()
