from __future__ import annotations

import asyncio

from Project.app import app
from Project.config import Settings
from Project.core.composer import Composer
from Project.llm.groq_client import GroqClient


async def _compose_async(category: dict, merchant: dict, trigger: dict, customer: dict | None) -> dict:
    settings = Settings.from_env()
    composer = Composer(GroqClient(settings.groq_api_key, settings.groq_model, settings.request_timeout_seconds))
    return await composer.compose(category=category, merchant=merchant, trigger=trigger, customer=customer)


def compose(category: dict, merchant: dict, trigger: dict, customer: dict | None = None) -> dict:
    """
    Return keys: body, cta, send_as, suppression_key, rationale.
    Deterministic by design (Groq temperature=0 + rule-based fallback).
    """
    return asyncio.run(_compose_async(category, merchant, trigger, customer))
