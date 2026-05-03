import os
import json
import httpx
import asyncio
from pathlib import Path

DATA_ROOT = Path("Information/dataset/expanded")
BASE_URL = "https://magicpin-bot-latest.onrender.com/v1"

async def push_context(scope, context_id, payload):
    url = f"{BASE_URL}/context"
    data = {
        "scope": scope,
        "context_id": context_id,
        "version": 1,
        "payload": payload,
        "delivered_at": "2026-05-01T12:00:00Z"
    }
    async with httpx.AsyncClient() as client:
        try:
            resp = await client.post(url, json=data, timeout=10)
            if resp.status_code == 200:
                print(f"Loaded {scope}: {context_id}")
            else:
                print(f"Failed {scope}: {context_id} - {resp.text}")
        except Exception as e:
            print(f"Error loading {scope}: {context_id} - {e}")

async def main():
    # Load categories
    cat_dir = DATA_ROOT / "categories"
    for cat_file in cat_dir.glob("*.json"):
        payload = json.loads(cat_file.read_text())
        await push_context("category", payload["slug"], payload)

    # Load merchants
    merch_dir = DATA_ROOT / "merchants"
    for merch_file in merch_dir.glob("*.json"):
        payload = json.loads(merch_file.read_text())
        await push_context("merchant", payload["merchant_id"], payload)

    # Load customers
    cust_dir = DATA_ROOT / "customers"
    for cust_file in cust_dir.glob("*.json"):
        payload = json.loads(cust_file.read_text())
        await push_context("customer", payload["customer_id"], payload)

    # Load triggers
    trig_dir = DATA_ROOT / "triggers"
    for trig_file in trig_dir.glob("*.json"):
        payload = json.loads(trig_file.read_text())
        await push_context("trigger", payload["id"], payload)

if __name__ == "__main__":
    asyncio.run(main())
