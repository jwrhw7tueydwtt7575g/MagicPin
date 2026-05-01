import httpx
import asyncio
import json
import os

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

async def test_reply_positive_context():
    print("\n--- Simulating Positive Context Reply ---")
    # First, let's establish a bot turn by ticking first or manual injection
    # We'll just use a mock conversation state if we had access to store, 
    # but since we are external, we rely on the server state.
    
    # 1. Trigger something that says "audit"
    await test_regulation_change_tick()
    
    # 2. Reply positively
    data = {
        "conversation_id": "conv_context_test",
        "merchant_id": "m_001_drmeera_dentist_delhi",
        "customer_id": None,
        "from_role": "merchant",
        "message": "Ok let's do the audit.",
        "received_at": "2026-05-01T14:30:00Z",
        "turn_number": 2
    }
    # Note: conversation_id must match the one from tick for context to work ideally, 
    # but in our script we just want to see if it works.
    async with httpx.AsyncClient() as client:
        resp = await client.post(f"{BASE_URL}/reply", json=data)
        print(f"Status: {resp.status_code}")
        print(json.dumps(resp.json(), indent=2))

async def main():
    async with httpx.AsyncClient(timeout=30) as client:
        await client.post(f"{BASE_URL}/teardown")
        print("Server Teardown Complete.")
        os.system(".venv/bin/python load_dataset.py > /dev/null")
        print("Data Re-loaded.")

        print("\n--- Simulating Regulation Change & Positive Context Reply ---")
        tick_resp = await client.post(f"{BASE_URL}/tick", json={
            "now": "2026-05-01T14:00:00Z",
            "available_triggers": ["trg_002_compliance_dci_radiograph"]
        })
        actions = tick_resp.json()["actions"]
        if actions:
            action = actions[0]
            print(f"Initial Tick Body: {action['body']}")
            real_conv_id = action["conversation_id"]
            
            reply_resp = await client.post(f"{BASE_URL}/reply", json={
                "conversation_id": real_conv_id,
                "merchant_id": "m_001_drmeera_dentist_delhi",
                "customer_id": None,
                "from_role": "merchant",
                "message": "Yes, I am ready to start the audit.",
                "received_at": "2026-05-01T14:05:00Z",
                "turn_number": 2
            })
            print(f"Contextual Reply Status: {reply_resp.status_code}")
            print(json.dumps(reply_resp.json(), indent=2))
        else:
            print("Failed to trigger regulation change action.")

        print("\n--- Simulating Clinical Recall Tick ---")
        resp = await client.post(f"{BASE_URL}/tick", json={
            "now": "2026-05-01T14:10:00Z",
            "available_triggers": ["trg_003_recall_due_priya"]
        })
        print(f"Status: {resp.status_code}")
        print(json.dumps(resp.json(), indent=2))

        print("\n--- Simulating Complex Compliance Followup ---")
        resp = await client.post(f"{BASE_URL}/reply", json={
            "conversation_id": "conv_complex_audit",
            "merchant_id": "m_001_drmeera_dentist_delhi",
            "customer_id": None,
            "from_role": "merchant",
            "message": "I need help with the audit setup for my film units.",
            "received_at": "2026-05-01T14:20:00Z",
            "turn_number": 2
        })
        print(f"Status: {resp.status_code}")
        print(json.dumps(resp.json(), indent=2))

if __name__ == "__main__":
    asyncio.run(main())
