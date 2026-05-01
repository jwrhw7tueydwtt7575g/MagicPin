from Project.core.rules import derive_cta, derive_send_as


def test_send_as_customer_scope():
    assert derive_send_as({'scope': 'customer'}) == 'merchant_on_behalf'


def test_send_as_merchant_scope():
    assert derive_send_as({'scope': 'merchant'}) == 'vera'


def test_cta_action_trigger():
    assert derive_cta({'kind': 'recall_due'}) == 'yes_stop'


def test_cta_research_digest_open_ended():
    assert derive_cta({'kind': 'research_digest'}) == 'open_ended'


def test_cta_regulation_change_yes_stop():
    assert derive_cta({'kind': 'regulation_change'}) == 'yes_stop'


def test_cta_supply_alert_high_urgency_yes_stop():
    assert derive_cta({'kind': 'supply_alert', 'urgency': 5}) == 'yes_stop'


def test_cta_active_planning_intent_unchanged_at_urgency_4():
    assert derive_cta({'kind': 'active_planning_intent', 'urgency': 4}) == 'open_ended'


def test_cta_active_planning_intent_high_urgency_stays_open_ended():
    assert derive_cta({'kind': 'active_planning_intent', 'urgency': 5}) == 'open_ended'


def test_cta_unknown_kind_high_urgency_yes_stop():
    assert derive_cta({'kind': 'judge_injected_kind_xyz', 'urgency': 5}) == 'yes_stop'
