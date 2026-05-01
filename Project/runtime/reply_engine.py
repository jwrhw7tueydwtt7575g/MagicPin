from __future__ import annotations

import re

AUTO_REPLY_MARKERS = (
    'out of office',
    'i am away',
    'auto reply',
    'automated message',
    'thank you for contacting us',
    'our team will respond shortly',
    'we will get back to you',
)

NEGATIVE_MARKERS = (
    'not interested',
    'unsubscribe',
    'dont message',
    'do not message',
)

_STOP_WORD_RE = re.compile(r'\bstop\b', re.IGNORECASE)

POSITIVE_MARKERS = (
    'yes',
    'ok',
    'okay',
    'interested',
    'do it',
    'lets do it',
)

_COMPLIANCE_TOPIC_TOKENS = (
    'iopa',
    'd-speed',
    'd speed',
    'msv',
    'radiograph',
    'radiography',
    'film stock',
    'x-ray',
    'xray',
    'sensor',
    'rvg',
    'compliance',
    'circular',
    'dose',
    'exposure',
    'dci',
)

_COMPLIANCE_QUESTION_RE = re.compile(
    r'\b(what|how|does|do|will|can|should|which|when|must|need)\b',
    re.IGNORECASE,
)


class ReplyEngine:
    @staticmethod
    def _looks_like_compliance_followup(text: str) -> bool:
        if not any(tok in text for tok in _COMPLIANCE_TOPIC_TOKENS):
            return False
        if '?' in text or bool(_COMPLIANCE_QUESTION_RE.search(text)):
            return True
        if 'need help' in text or 'help me' in text:
            return True
        return False

    def classify(self, incoming: str) -> str:
        text = incoming.strip().lower()
        if any(token in text for token in AUTO_REPLY_MARKERS):
            return 'auto'
        if any(token in text for token in NEGATIVE_MARKERS) or _STOP_WORD_RE.search(text):
            return 'negative'
        if any(token in text for token in POSITIVE_MARKERS):
            return 'positive'
        if any(bad in text for bad in ('abuse', 'stupid', 'idiot', 'gst')):
            return 'off_topic'
        if self._looks_like_compliance_followup(text) or any(token in text for token in ('audit', 'setup', 'check', 'film')):
            return 'compliance_followup'
        return 'unclear'

    def next_action(self, incoming: str, repeated_auto_count: int = 0, turns: list[dict] = None) -> dict:
        label = self.classify(incoming)
        if label == 'auto' and repeated_auto_count >= 3:
            return {
                'action': 'end',
                'rationale': 'Detected repeated auto-reply loop; ending gracefully.',
            }
        if label == 'auto':
            return {
                'action': 'wait',
                'wait_seconds': 1800,
                'rationale': 'Detected probable auto-reply; waiting avoids spam loops.',
            }
        if label == 'negative':
            return {
                'action': 'end',
                'rationale': 'User opted out or declined; ending conversation respectfully.',
            }
        if label == 'positive':
            # Attempt to pull context from the last bot message
            last_bot_body = next(
                (t['body'] for t in reversed(turns or []) if t.get('from') == 'bot'),
                None
            )
            context = ''
            if last_bot_body:
                # Extract a likely subject (e.g. "audit", "promotion")
                if 'audit' in last_bot_body.lower() or 'compliance' in last_bot_body.lower():
                    context = ' audit and compliance check'
                elif 'promo' in last_bot_body.lower() or 'offer' in last_bot_body.lower():
                    context = ' promotion'
                elif 'recall' in last_bot_body.lower() or 'appointment' in last_bot_body.lower():
                    context = ' appointment booking'

            return {
                'action': 'send',
                'body': f'Perfect, I will proceed with the{context} right away and share the next update shortly.',
                'cta': 'open_ended',
                'rationale': 'User intent is positive; response tailored to last bot turn context.',
            }
        if label == 'off_topic':
            return {
                'action': 'send',
                'body': 'I can help only with engagement actions here. If you want, I can continue with the current campaign flow.',
                'cta': 'open_ended',
                'rationale': 'Stays on mission while de-escalating off-topic or hostile content.',
            }
        if label == 'compliance_followup':
            return {
                'action': 'send',
                'body': (
                    'Got it. To help with the audit, please share your current inventory of active film units and sensor stock. '
                    'I will draft a compliance checklist based on those details immediately.'
                ),
                'cta': 'open_ended',
                'rationale': 'Handles compliance or clinical equipment follow-up with concrete next steps.',
            }
        return {
            'action': 'wait',
            'wait_seconds': 900,
            'rationale': 'Message is ambiguous; waiting for clearer intent.',
        }
