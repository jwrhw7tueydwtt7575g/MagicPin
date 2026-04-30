from __future__ import annotations

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
    'stop',
    'unsubscribe',
    'dont message',
    'do not message',
)

POSITIVE_MARKERS = (
    'yes',
    'ok',
    'okay',
    'interested',
    'do it',
    'lets do it',
)


class ReplyEngine:
    def classify(self, incoming: str) -> str:
        text = incoming.strip().lower()
        if any(token in text for token in AUTO_REPLY_MARKERS):
            return 'auto'
        if any(token in text for token in NEGATIVE_MARKERS):
            return 'negative'
        if any(token in text for token in POSITIVE_MARKERS):
            return 'positive'
        if any(bad in text for bad in ('abuse', 'stupid', 'idiot', 'gst')):
            return 'off_topic'
        return 'unclear'

    def next_action(self, incoming: str, repeated_auto_count: int = 0) -> dict:
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
            return {
                'action': 'send',
                'body': 'Perfect, I will proceed with this now and share the next update shortly.',
                'cta': 'open_ended',
                'rationale': 'User intent is positive, so moving directly to action.',
            }
        if label == 'off_topic':
            return {
                'action': 'send',
                'body': 'I can help only with engagement actions here. If you want, I can continue with the current campaign flow.',
                'cta': 'open_ended',
                'rationale': 'Stays on mission while de-escalating off-topic or hostile content.',
            }
        return {
            'action': 'wait',
            'wait_seconds': 900,
            'rationale': 'Message is ambiguous; waiting for clearer intent.',
        }
