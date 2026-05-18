from __future__ import annotations

from src.services.identity_service import _SYNTH_EMAIL_DOMAIN, _synth_email


def test_synth_email_format() -> None:
    addr = _synth_email("telegram", "12345678")
    assert addr == f"telegram-12345678@{_SYNTH_EMAIL_DOMAIN}"


def test_synth_email_uniqueness_by_subject() -> None:
    a = _synth_email("telegram", "1")
    b = _synth_email("telegram", "2")
    assert a != b


def test_synth_email_distinguishes_providers() -> None:
    a = _synth_email("telegram", "1")
    b = _synth_email("google", "1")
    assert a != b


def test_synth_email_uses_invalid_tld_not_local() -> None:
    # .local — RFC 6762 multicast DNS, отвергается email-validator
    # .invalid — RFC 6761 reserved для несуществующих адресов
    addr = _synth_email("telegram", "999")
    assert ".local" not in addr
    assert addr.endswith(".invalid")
