from __future__ import annotations

import time
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone


@dataclass
class ConversationState:
    merchant_id: str
    customer_id: str | None
    turns: list[dict] = field(default_factory=list)
    ended: bool = False


class StateStore:
    def __init__(self) -> None:
        self.started_at = time.time()
        self.contexts: dict[tuple[str, str], dict] = {}
        self.by_scope: dict[str, dict[str, dict]] = defaultdict(dict)
        self.conversations: dict[str, ConversationState] = {}
        self.used_suppression_keys: set[str] = set()
        self.sent_body_hashes: dict[str, set[str]] = defaultdict(set)
        self.used_conversation_ids_on_tick: set[str] = set()
        self.last_outbound_at: dict[tuple[str, str | None], datetime] = {}
        self.composition_audit: list[dict] = []

    def upsert_context(self, scope: str, context_id: str, version: int, payload: dict) -> tuple[bool, int | None]:
        key = (scope, context_id)
        current = self.contexts.get(key)
        if current and current['version'] > version:
            return False, current['version']
        if current and current['version'] == version:
            return True, version
        self.contexts[key] = {'version': version, 'payload': payload}
        self.by_scope[scope][context_id] = payload
        return True, version

    def get_context(self, scope: str, context_id: str) -> dict | None:
        entry = self.contexts.get((scope, context_id))
        return entry['payload'] if entry else None

    def context_counts(self) -> dict[str, int]:
        return {
            'category': len(self.by_scope.get('category', {})),
            'merchant': len(self.by_scope.get('merchant', {})),
            'customer': len(self.by_scope.get('customer', {})),
            'trigger': len(self.by_scope.get('trigger', {})),
        }

    def uptime_seconds(self) -> int:
        return int(time.time() - self.started_at)

    def mark_suppression(self, suppression_key: str) -> None:
        self.used_suppression_keys.add(suppression_key)

    def is_suppressed(self, suppression_key: str) -> bool:
        return suppression_key in self.used_suppression_keys

    def mark_conversation_id_from_tick(self, conversation_id: str) -> None:
        self.used_conversation_ids_on_tick.add(conversation_id)

    def conversation_id_used_on_tick(self, conversation_id: str) -> bool:
        return conversation_id in self.used_conversation_ids_on_tick

    def upsert_conversation(self, conversation_id: str, merchant_id: str, customer_id: str | None) -> ConversationState:
        if conversation_id not in self.conversations:
            self.conversations[conversation_id] = ConversationState(merchant_id=merchant_id, customer_id=customer_id)
        return self.conversations[conversation_id]

    def append_turn(self, conversation_id: str, turn: dict) -> None:
        convo = self.conversations.get(conversation_id)
        if convo is None:
            raise ValueError('conversation_not_found')
        convo.turns.append(turn)

    def end_conversation(self, conversation_id: str) -> None:
        convo = self.conversations.get(conversation_id)
        if convo:
            convo.ended = True

    def clear_all(self) -> None:
        self.contexts.clear()
        self.by_scope.clear()
        self.conversations.clear()
        self.used_suppression_keys.clear()
        self.sent_body_hashes.clear()
        self.used_conversation_ids_on_tick.clear()
        self.last_outbound_at.clear()
        self.composition_audit.clear()

    def repeated_incoming_text_count(self, conversation_id: str, incoming_text: str) -> int:
        convo = self.conversations.get(conversation_id)
        if convo is None:
            return 0
        target = incoming_text.strip().lower()
        if not target:
            return 0
        count = 0
        for turn in reversed(convo.turns):
            if turn.get('from') != 'merchant':
                continue
            body = str(turn.get('body', '')).strip().lower()
            if body == target:
                count += 1
            else:
                break
        return count

    def is_duplicate_bot_body(self, conversation_id: str, body: str) -> bool:
        convo = self.conversations.get(conversation_id)
        if convo is None:
            return False
        normalized = body.strip().lower()
        for turn in convo.turns:
            if turn.get('from') == 'bot' and str(turn.get('body', '')).strip().lower() == normalized:
                return True
        return False

    def can_use_template_now(self, merchant_id: str, customer_id: str | None, now_iso: str) -> bool:
        key = (merchant_id, customer_id)
        now_dt = datetime.fromisoformat(now_iso.replace('Z', '+00:00'))
        last = self.last_outbound_at.get(key)
        if last is None:
            return True
        return (now_dt - last) > timedelta(hours=24)

    def mark_outbound_sent(self, merchant_id: str, customer_id: str | None, now_iso: str) -> None:
        key = (merchant_id, customer_id)
        self.last_outbound_at[key] = datetime.fromisoformat(now_iso.replace('Z', '+00:00')).astimezone(timezone.utc)

    def add_composition_audit(self, entry: dict) -> None:
        self.composition_audit.append(entry)
