import httpx
import asyncio
import json

BASE_URL = "http://localhost:8080/v1"

async def test_regulation_change_tick():
    print("\n--- Simulating Regulation Change Tick ---")
    data = {
        "now": "2026-05-01T14:00:00Z",
        "available_triggers": ["trg_002_compliance_dci_radiograph"]
    }
    async with httpx.AsyncClient() as client:
        resp = await client.post(f"{BASE_URL}/tick", json=data)
        print(f"Status: {resp.status_code}")
        print(json.dumps(resp.json(), indent=2))

async def test_clinical_recall_tick():
    print("\n--- Simulating Clinical Recall Tick ---")
    data = {
        "now": "2026-05-01T14:10:00Z",
        "available_triggers": ["trg_003_recall_due_priya"]
    }
    async with httpx.AsyncClient() as client:
        resp = await client.post(f"{BASE_URL}/tick", json=data)
        print(f"Status: {resp.status_code}")
        print(json.dumps(resp.json(), indent=2))

async def test_reply_audit_followup():
    print("\n--- Simulating Reply Audit Followup ---")
    # First we need a conversation ID. trg_002 tick should have created one.
    # But for a direct test, we can just use a dummy one.
    data = {
        "conversation_id": "conv_test_audit",
        "merchant_id": "m_001_drmeera_dentist_delhi",
        "customer_id": None,
        "from_role": "merchant",
        "message": "I need help auditing my x-ray setup, we have old films.",
        "received_at": "2026-05-01T14:20:00Z",
        "turn_number": 2
    }
    async with httpx.AsyncClient() as client:
        resp = await client.post(f"{BASE_URL}/reply", json=data)
        print(f"Status: {resp.status_code}")
        print(json.dumps(resp.json(), indent=2))

async def main():
    await test_regulation_change_tick()
    await test_clinical_recall_tick()
    await test_reply_audit_followup()

if __name__ == "__main__":
    asyncio.run(main())
