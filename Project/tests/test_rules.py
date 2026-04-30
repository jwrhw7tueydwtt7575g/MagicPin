from Project.core.rules import derive_cta, derive_send_as


def test_send_as_customer_scope():
    assert derive_send_as({'scope': 'customer'}) == 'merchant_on_behalf'


def test_send_as_merchant_scope():
    assert derive_send_as({'scope': 'merchant'}) == 'vera'


def test_cta_action_trigger():
    assert derive_cta({'kind': 'recall_due'}) == 'yes_stop'


def test_cta_info_trigger():
    assert derive_cta({'kind': 'research_digest'}) == 'none'
