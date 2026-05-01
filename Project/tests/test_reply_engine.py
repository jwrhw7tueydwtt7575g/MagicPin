from Project.runtime.reply_engine import ReplyEngine


def test_compliance_need_help_without_question_mark():
    eng = ReplyEngine()
    msg = 'Got it doc — need help auditing my X-ray setup. We have an old D-speed film unit.'
    assert eng.classify(msg) == 'compliance_followup'
    out = eng.next_action(msg)
    assert out['action'] == 'send'
    assert 'inventory' in out['body'].lower() or 'audit' in out['body'].lower()


def test_compliance_d_speed_question_sends_action_body():
    eng = ReplyEngine()
    msg = 'Does my D-speed IOPA film stock still pass after the DCI circular change?'
    assert eng.classify(msg) == 'compliance_followup'
    out = eng.next_action(msg)
    assert out['action'] == 'send'
    assert 'inventory' in out['body'].lower() or 'audit' in out['body'].lower()
    assert 'would you' not in out['body'].lower()


def test_ambiguous_smalltalk_waits():
    eng = ReplyEngine()
    msg = 'Hello are you there'
    assert eng.classify(msg) == 'unclear'
    assert eng.next_action(msg)['action'] == 'wait'


def test_positive_commitment_still_send():
    eng = ReplyEngine()
    msg = 'Ok lets do it. Whats next?'
    assert eng.classify(msg) == 'positive'
    out = eng.next_action(msg)
    assert out['action'] == 'send'
    assert 'proceed' in out['body'].lower()
