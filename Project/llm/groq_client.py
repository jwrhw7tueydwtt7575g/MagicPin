from __future__ import annotations

import json
from typing import Any

import httpx


class GroqClient:
    def __init__(self, api_key: str, model: str, timeout_seconds: float = 20.0) -> None:
        self.api_key = api_key
        self.model = model
        self.timeout_seconds = timeout_seconds
        self.url = 'https://api.groq.com/openai/v1/chat/completions'

    async def compose_json(self, system_prompt: str, user_prompt: str) -> dict[str, Any]:
        if not self.api_key:
            return {}

        headers = {
            'Authorization': f'Bearer {self.api_key}',
            'Content-Type': 'application/json',
        }
        data = {
            'model': self.model,
            'temperature': 0,
            'max_tokens': 220,
            'response_format': {'type': 'json_object'},
            'messages': [
                {'role': 'system', 'content': system_prompt},
                {'role': 'user', 'content': user_prompt},
            ],
        }
        async with httpx.AsyncClient(timeout=self.timeout_seconds) as client:
            try:
                response = await client.post(self.url, headers=headers, json=data)
                response.raise_for_status()
                content = response.json()['choices'][0]['message']['content']
                return json.loads(content)
            except (httpx.HTTPError, KeyError, json.JSONDecodeError, TypeError):
                # Retry once with a looser payload for provider compatibility.
                fallback_data = {
                    'model': self.model,
                    'temperature': 0,
                    'max_tokens': 220,
                    'messages': [
                        {'role': 'system', 'content': system_prompt},
                        {'role': 'user', 'content': user_prompt},
                    ],
                }
                try:
                    retry = await client.post(self.url, headers=headers, json=fallback_data)
                    retry.raise_for_status()
                    content = retry.json()['choices'][0]['message']['content']
                    return json.loads(content)
                except (httpx.HTTPError, KeyError, json.JSONDecodeError, TypeError):
                    # Composer has deterministic rule-based fallback.
                    return {}
