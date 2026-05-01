import asyncio
import random
import re
import string
from unittest.mock import AsyncMock, MagicMock

from Project.core.composer import Composer, strip_trailing_category_parenthetical
from Project.core.rules import derive_cta

_STOP_BOUNDARY = re.compile(r'\bstop\b', re.IGNORECASE)
_ALLOWED_CTA = frozenset({'yes_stop', 'open_ended'})


def test_fuzz_derive_cta_outputs_allowed():
    rng = random.Random(20260501)
    for _ in range(500):
        n = rng.randint(0, 24)
        kind = ''.join(rng.choice(string.ascii_lowercase + '_0123456789') for _ in range(n))
        urgency = rng.randint(0, 6)
        scope = rng.choice(['merchant', 'customer', ''])
        trigger = {'kind': kind, 'urgency': urgency}
        if scope:
            trigger['scope'] = scope
        out = derive_cta(trigger)
        assert out in _ALLOWED_CTA


def test_fuzz_strip_trailing_parenthetical_monotone():
    rng = random.Random(20260502)
    slug = 'dentists'
    for _ in range(300):
        body = ''.join(rng.choice(string.printable) for _ in range(rng.randint(0, 120)))
        after = strip_trailing_category_parenthetical(body, slug)
        assert len(after) <= len(body)
        assert not after.rstrip().lower().endswith(f' ({slug})')


def test_fuzz_clinical_recall_never_stop_word():
    composer = Composer(None)
    rng = random.Random(20260503)
    category = {'slug': 'gyms'}
    trigger = {'kind': 'recall_due'}
    customer = {'identity': {'name': 'Alex'}}
    for _ in range(80):
        noise = ''.join(rng.choice(string.ascii_letters + ' .,') for _ in range(rng.randint(5, 80)))
        body = f'{noise} Reply YES to book or STOP to cancel.'
        out = composer._align_body_with_cta(body, 'yes_stop', trigger, customer, category)
        assert not _STOP_BOUNDARY.search(out)


def test_fuzz_clinical_compose_random_llm_stop_line():
    rng = random.Random(20260504)
    groq = MagicMock()
    composer = Composer(groq)
    category = {'slug': 'pharmacies'}
    merchant = {'merchant_id': 'm1', 'identity': {'name': 'Apollo'}}
    trigger = {
        'id': 't1',
        'kind': 'chronic_refill_due',
        'scope': 'customer',
        'merchant_id': 'm1',
        'customer_id': 'c1',
        'suppression_key': 'k1',
    }
    customer = {'identity': {'name': 'Pat'}}

    async def run_once(body: str):
        groq.compose_json = AsyncMock(return_value={'body': body, 'rationale': ''})
        return await composer.compose(category, merchant, trigger, customer)

    for _ in range(40):
        noise = ''.join(rng.choice(string.ascii_letters + ' ') for _ in range(rng.randint(10, 60)))
        body_in = f'{noise} Reply YES or STOP to opt out.'
        result = asyncio.run(run_once(body_in))
        assert not _STOP_BOUNDARY.search(result['body'])
