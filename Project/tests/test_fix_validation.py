import pytest
import asyncio
from Project.core.rules import derive_cta
from Project.core.composer import Composer
from Project.runtime.reply_engine import ReplyEngine

class MockGroqClient:
    async def compose_json(self, system, user):
        return {"body": "LLM text", "rationale": "reason"}

def test_regulation_change_cta():
    trigger = {"kind": "regulation_change", "urgency": 3}
    assert derive_cta(trigger) == "yes_stop"

def test_clinical_tone_no_stop():
    async def run_test():
        composer = Composer(MockGroqClient())
        category = {"slug": "dentists"}
        merchant = {"identity": {"name": "Dr. Smith"}}
        trigger = {"kind": "recall_due", "scope": "customer"}
        customer = {"identity": {"name": "Priya"}}
        result = await composer.compose(category, merchant, trigger, customer)
        return result["body"], result["cta"]
    body, cta = asyncio.run(run_test())
    assert "STOP to opt out" not in body
    assert "Reply YES to book, or NO if not this month" in body
    assert cta == "yes_stop"

def test_reply_engine_positive_context():
    engine = ReplyEngine()
    turns = [{"from": "bot", "body": "We should audit your equipment."}]
    msg = "Yes please, let's do it."
    decision = engine.next_action(msg, turns=turns)
    assert decision["action"] == "send"
    assert "audit and compliance check" in decision["body"]

def test_reply_engine_audit_followup():
    engine = ReplyEngine()
    msg = "Got it doc — need help auditing my X-ray setup. We have an old D-speed film unit."
    decision = engine.next_action(msg)
    assert decision["action"] == "send"
    assert "audit" in decision["body"].lower()
    assert "inventory" in decision["body"].lower()

# --- V3.0 Customer Role Tests ---

def test_customer_slot_pick_detected():
    engine = ReplyEngine()
    msg = "Yes please book me for Wed 5 Nov, 6pm."
    label = engine.classify_customer(msg)
    assert label == "slot_pick"

def test_customer_role_returns_slot_pick_action():
    engine = ReplyEngine()
    msg = "Yes please book me for Wed 5 Nov, 6pm."
    decision = engine.next_action(msg, from_role="customer")
    assert decision["action"] == "slot_pick"

def test_customer_negative_ends_conversation():
    engine = ReplyEngine()
    msg = "Stop messaging me."
    decision = engine.next_action(msg, from_role="customer")
    assert decision["action"] == "end"

def test_merchant_role_unchanged():
    engine = ReplyEngine()
    msg = "Yes, let's proceed."
    decision = engine.next_action(msg, from_role="merchant")
    assert decision["action"] == "send"
    assert "Perfect" in decision["body"]

def test_slot_confirmation_fallback_matches_slot():
    from Project.core.composer import Composer
    composer = Composer(None)
    slots = [{"label": "Wed 5 Nov, 6pm"}, {"label": "Thu 6 Nov, 5pm"}]
    body = composer._slot_confirmation_fallback(
        customer_name="Priya",
        merchant_name="Dr. Meera's Dental Clinic",
        incoming="Yes please book me for Wed 5 Nov, 6pm.",
        slots=slots,
    )
    assert "Wed 5 Nov, 6pm" in body
    assert "Priya" in body
    assert "Dr. Meera" in body
