from __future__ import annotations

import argparse
import asyncio
import json
from pathlib import Path

from Project.config import Settings
from Project.core.composer import Composer
from Project.llm.groq_client import GroqClient


def _load_json(path: Path):
    with path.open('r', encoding='utf-8') as f:
        return json.load(f)


async def generate_submission(data_root: Path, output_path: Path) -> None:
    settings = Settings.from_env()
    composer = Composer(GroqClient(settings.groq_api_key, settings.groq_model, settings.request_timeout_seconds))

    category_files = ['dentists.json', 'gyms.json', 'pharmacies.json', 'restaurants.json', 'salons.json']
    categories = {}
    for filename in category_files:
        category_payload = _load_json(data_root / 'categories' / filename)
        categories[category_payload['slug']] = category_payload
    expanded_root = data_root / 'expanded'
    if not expanded_root.exists():
        raise FileNotFoundError(
            f'Expanded dataset not found at {expanded_root}. '
            'Run: python3 Information/dataset/generate_dataset.py --seed-dir Information/dataset --out Information/dataset/expanded'
        )

    test_pairs = _load_json(expanded_root / 'test_pairs.json').get('pairs', [])
    merchants = {}
    for path in (expanded_root / 'merchants').glob('*.json'):
        payload = _load_json(path)
        merchants[payload['merchant_id']] = payload
    customers = {}
    for path in (expanded_root / 'customers').glob('*.json'):
        payload = _load_json(path)
        customers[payload['customer_id']] = payload
    triggers = {}
    for path in (expanded_root / 'triggers').glob('*.json'):
        payload = _load_json(path)
        triggers[payload['id']] = payload

    rows = []
    for pair in test_pairs[:30]:
        trigger = triggers.get(pair.get('trigger_id'))
        if not trigger:
            continue
        merchant = merchants.get(pair.get('merchant_id') or trigger.get('merchant_id'))
        if not merchant:
            continue
        category = categories.get(merchant.get('category_slug'))
        if not category:
            continue
        customer_id = pair.get('customer_id') or trigger.get('customer_id')
        customer = customers.get(customer_id) if customer_id else None
        composed = await composer.compose(category, merchant, trigger, customer)
        rows.append(
            {
                'test_id': pair.get('test_id'),
                'body': composed['body'],
                'cta': composed['cta'],
                'send_as': composed['send_as'],
                'suppression_key': composed['suppression_key'],
                'rationale': composed['rationale'],
            }
        )

    with output_path.open('w', encoding='utf-8') as f:
        for row in rows:
            f.write(json.dumps(row, ensure_ascii=True) + '\n')


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--data-root', default='/home/vivek/Desktop/magicPin/magicpin-ai-challenge/Information/dataset')
    parser.add_argument('--output', default='/home/vivek/Desktop/magicPin/magicpin-ai-challenge/submission.jsonl')
    args = parser.parse_args()
    asyncio.run(generate_submission(Path(args.data_root), Path(args.output)))
