from __future__ import annotations

import logging
from datetime import datetime, timezone
from uuid import uuid4

from fastapi import FastAPI
from fastapi.responses import JSONResponse

from Project.config import Settings
from Project.core.composer import Composer
from Project.core.dedup import hash_body
from Project.llm.groq_client import GroqClient
from Project.runtime.reply_engine import ReplyEngine
from Project.runtime.triggers import explain_tick_pick_skip, pick_eligible_trigger_ids
from Project.store.models import (
    ContextPushAccepted,
    ContextPushRejected,
    ContextPushRequest,
    HealthResponse,
    MetadataResponse,
    ReplyEndResponse,
    ReplyRequest,
    ReplySendResponse,
    ReplyWaitResponse,
    TeardownResponse,
    TickAction,
    TickRequest,
    TickResponse,
)
from Project.store.state import StateStore

app = FastAPI(title='MagicPin Engagement Bot')
settings = Settings.from_env()
log = logging.getLogger(__name__)
store = StateStore()
composer = Composer(GroqClient(settings.groq_api_key, settings.groq_model, settings.request_timeout_seconds))
reply_engine = ReplyEngine()
VALID_SCOPES = {'category', 'merchant', 'customer', 'trigger'}


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat().replace('+00:00', 'Z')


@app.get('/v1/healthz', response_model=HealthResponse)
async def healthz() -> HealthResponse:
    return HealthResponse(status='ok', uptime_seconds=store.uptime_seconds(), contexts_loaded=store.context_counts())


@app.get('/v1/metadata', response_model=MetadataResponse)
async def metadata() -> MetadataResponse:
    return MetadataResponse(
        team_name=settings.team_name,
        team_members=settings.team_members or ['Vivek'],
        model=settings.groq_model,
        approach='stateful deterministic composer with Groq and rule-guards',
        contact_email=settings.contact_email,
        version=settings.app_version,
        submitted_at=_utc_now_iso(),
    )


@app.post('/v1/context', response_model=ContextPushAccepted | ContextPushRejected)
async def push_context(body: ContextPushRequest):
    if body.scope not in VALID_SCOPES:
        return JSONResponse(
            status_code=400,
            content=ContextPushRejected(accepted=False, reason='invalid_scope', details=body.scope).model_dump(),
        )

    accepted, current_version = store.upsert_context(body.scope, body.context_id, body.version, body.payload)
    if not accepted:
        return JSONResponse(
            status_code=409,
            content=ContextPushRejected(accepted=False, reason='stale_version', current_version=current_version).model_dump(),
        )
    return ContextPushAccepted(accepted=True, ack_id=f'ack_{body.context_id}_v{body.version}', stored_at=_utc_now_iso())


@app.post('/v1/tick', response_model=TickResponse)
async def tick(body: TickRequest) -> TickResponse:
    selected = pick_eligible_trigger_ids(store, body.available_triggers, body.now, settings.max_actions_per_tick)
    if settings.tick_debug:
        selected_set = set(selected)
        for tid in body.available_triggers:
            if tid in selected_set:
                continue
            reason = explain_tick_pick_skip(store, tid)
            if reason:
                log.info('tick_pick_skip trigger_id=%s reason=%s', tid, reason)

    actions: list[TickAction] = []
    reserved_suppression_keys: set[str] = set()

    for trigger_id in selected:
        trigger = store.get_context('trigger', trigger_id)
        if not trigger:
            if settings.tick_debug:
                log.info('tick_compose_skip trigger_id=%s reason=missing_trigger_payload', trigger_id)
            continue
        merchant_id = trigger.get('merchant_id')
        customer_id = trigger.get('customer_id')
        merchant = store.get_context('merchant', merchant_id) if merchant_id else None
        customer = store.get_context('customer', customer_id) if customer_id else None
        if not merchant:
            if settings.tick_debug:
                log.info('tick_compose_skip trigger_id=%s reason=missing_merchant_context', trigger_id)
            continue
        category = store.get_context('category', merchant.get('category_slug'))
        if not category:
            if settings.tick_debug:
                log.info('tick_compose_skip trigger_id=%s reason=missing_category_context', trigger_id)
            continue
        trigger_suppression_key = trigger.get('suppression_key')
        if trigger_suppression_key and (
            trigger_suppression_key in reserved_suppression_keys or store.is_suppressed(trigger_suppression_key)
        ):
            if settings.tick_debug:
                log.info('tick_compose_skip trigger_id=%s reason=suppression_key_already_used_this_tick', trigger_id)
            continue

        composed = await composer.compose(category, merchant, trigger, customer)
        conversation_id = f'conv_{uuid4().hex[:12]}'
        store.mark_conversation_id_from_tick(conversation_id)
        use_template = store.can_use_template_now(merchant_id=merchant_id, customer_id=customer_id, now_iso=body.now)

        body_hash = hash_body(composed['body'])
        if body_hash in store.sent_body_hashes[merchant_id]:
            if settings.tick_debug:
                log.info('tick_compose_skip trigger_id=%s reason=duplicate_body_hash', trigger_id)
            continue
        store.sent_body_hashes[merchant_id].add(body_hash)

        suppression_key = composed['suppression_key']
        if suppression_key in reserved_suppression_keys or store.is_suppressed(suppression_key):
            if settings.tick_debug:
                log.info('tick_compose_skip trigger_id=%s reason=composed_suppression_key_collision', trigger_id)
            continue
        reserved_suppression_keys.add(suppression_key)
        store.mark_suppression(suppression_key)
        store.mark_outbound_sent(merchant_id=merchant_id, customer_id=customer_id, now_iso=body.now)
        store.upsert_conversation(conversation_id, merchant_id=merchant_id, customer_id=customer_id)
        store.add_composition_audit(
            {
                'conversation_id': conversation_id,
                'merchant_id': merchant_id,
                'customer_id': customer_id,
                'trigger_id': trigger_id,
                'prompt_version': composed.get('prompt_version'),
                'prompt_variant': composed.get('prompt_variant'),
            }
        )
        store.append_turn(
            conversation_id,
            {
                'ts': body.now,
                'from': 'bot',
                'body': composed['body'],
                'cta': composed['cta'],
                'trigger_id': trigger_id,
            },
        )

        actions.append(
            TickAction(
                conversation_id=conversation_id,
                merchant_id=merchant_id,
                customer_id=customer_id,
                send_as=composed['send_as'],
                trigger_id=trigger_id,
                template_name=composed['template_name'] if use_template else None,
                template_params=composed['template_params'] if use_template else None,
                body=composed['body'],
                cta=composed['cta'],
                suppression_key=suppression_key,
                rationale=composed['rationale'],
            )
        )

    return TickResponse(actions=actions[: settings.max_actions_per_tick])


@app.post('/v1/reply', response_model=ReplySendResponse | ReplyWaitResponse | ReplyEndResponse)
async def reply(body: ReplyRequest):
    if body.conversation_id not in store.conversations:
        store.upsert_conversation(body.conversation_id, merchant_id=body.merchant_id, customer_id=body.customer_id)

    repeated_auto_count = store.repeated_incoming_text_count(body.conversation_id, body.message) + 1
    convo = store.conversations.get(body.conversation_id)
    turns = convo.turns if convo else []

    # Branch on from_role so customer messages get customer-voiced replies
    decision = reply_engine.next_action(
        body.message,
        repeated_auto_count=repeated_auto_count,
        turns=turns,
        from_role=body.from_role or 'merchant',
    )

    store.append_turn(
        body.conversation_id,
        {
            'ts': body.received_at,
            'from': body.from_role,
            'body': body.message,
            'turn_number': body.turn_number,
        },
    )

    if decision['action'] == 'end':
        store.end_conversation(body.conversation_id)
        return ReplyEndResponse(**decision)
    if decision['action'] == 'wait':
        return ReplyWaitResponse(**decision)

    # --- Handle slot_pick: compose customer-voiced slot confirmation via LLM ---
    if decision['action'] == 'slot_pick':
        merchant = store.get_context('merchant', body.merchant_id) or {}
        customer = store.get_context('customer', body.customer_id) if body.customer_id else None

        # Find the last trigger associated with this conversation for payload/slots
        last_trigger_id = next(
            (t.get('trigger_id') for t in reversed(turns) if t.get('trigger_id')),
            None,
        )
        trigger = store.get_context('trigger', last_trigger_id) if last_trigger_id else {}
        trigger_payload = trigger.get('payload', {}) if trigger else {}
        trigger_kind = trigger.get('kind', 'appointment') if trigger else 'appointment'

        slot_decision = await composer.compose_customer_reply(
            merchant=merchant,
            customer=customer or {},
            incoming_message=body.message,
            trigger_payload=trigger_payload,
            trigger_kind=trigger_kind,
        )
        decision = slot_decision

    if store.is_duplicate_bot_body(body.conversation_id, decision['body']):
        return ReplyWaitResponse(
            action='wait',
            wait_seconds=900,
            rationale='Avoiding duplicate outbound body in the same conversation.',
        )

    store.append_turn(
        body.conversation_id,
        {
            'ts': body.received_at,
            'from': 'bot',
            'body': decision['body'],
            'cta': decision.get('cta', 'open_ended'),
        },
    )
    return ReplySendResponse(**{k: v for k, v in decision.items() if k != 'incoming'})


@app.post('/v1/teardown', response_model=TeardownResponse)
async def teardown() -> TeardownResponse:
    store.clear_all()
    return TeardownResponse(accepted=True)
