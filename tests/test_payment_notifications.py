from datetime import datetime, timezone
from decimal import Decimal

from durable_notifications.payment_notifications import (
    PaymentEvent,
    RiskLevel,
    decide_notification,
)


def test_high_risk_payment_requires_review_and_keeps_audit_identity() -> None:
    occurred_at = datetime(2026, 9, 12, 8, 30, tzinfo=timezone.utc)
    decided_at = datetime(2026, 9, 12, 8, 31, tzinfo=timezone.utc)
    payment = PaymentEvent(
        event_id="pay_evt_1042",
        account_id="acct_71",
        amount=Decimal("1250.00"),
        currency="usd",
        risk_level=RiskLevel.HIGH,
        occurred_at=occurred_at,
    )

    notification = decide_notification(payment, decided_at=decided_at)

    assert notification.kind == "payment_review_required"
    assert notification.action == "review_payment"
    assert notification.channel == "account:acct_71"
    assert notification.event_id == "pay_evt_1042"
    assert notification.occurred_at == occurred_at
    assert notification.decided_at == decided_at
