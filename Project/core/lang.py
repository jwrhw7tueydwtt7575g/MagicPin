from __future__ import annotations


def pick_language_style(merchant: dict, customer: dict | None) -> str:
    if customer:
        pref = customer.get('identity', {}).get('language_pref') or customer.get('language_pref')
        if pref:
            return str(pref)
    languages = merchant.get('identity', {}).get('languages', [])
    if 'hi' in languages and 'en' in languages:
        return 'hi-en mix'
    if 'hi' in languages:
        return 'hindi'
    return 'english'
