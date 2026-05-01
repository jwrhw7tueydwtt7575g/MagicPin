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
        body = result["body"]
        return body, result["cta"]
    
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
