from __future__ import annotations

import os
from dataclasses import dataclass

from dotenv import load_dotenv

load_dotenv()
load_dotenv('/home/vivek/Desktop/magicPin/magicpin-ai-challenge/.env')
load_dotenv('/home/vivek/Desktop/magicPin/magicpin-ai-challenge/Project/.env')


@dataclass(frozen=True)
class Settings:
    groq_api_key: str
    groq_model: str = 'llama-3.1-70b-versatile'
    request_timeout_seconds: float = 20.0
    max_actions_per_tick: int = 20
    team_name: str = 'MagicPin Team'
    team_members: list[str] = None
    contact_email: str = 'team@example.com'
    app_version: str = '0.1.0'


    @staticmethod
    def from_env() -> 'Settings':
        members = os.getenv('TEAM_MEMBERS', 'Vivek').split(',')
        return Settings(
            groq_api_key=os.getenv('GROQ_API_KEY', ''),
            groq_model=os.getenv('GROQ_MODEL', 'llama-3.1-70b-versatile'),
            request_timeout_seconds=float(os.getenv('REQUEST_TIMEOUT_SECONDS', '20')),
            max_actions_per_tick=int(os.getenv('MAX_ACTIONS_PER_TICK', '20')),
            team_name=os.getenv('TEAM_NAME', 'MagicPin Team'),
            team_members=[m.strip() for m in members if m.strip()],
            contact_email=os.getenv('CONTACT_EMAIL', 'team@example.com'),
            app_version=os.getenv('APP_VERSION', '0.1.0'),
        )
