from __future__ import annotations

from datetime import datetime, timezone
from decimal import Decimal
from enum import StrEnum
from typing import Any, Literal

from pydantic import BaseModel, Field


class RiskLevel(StrEnum):
    STANDARD = "standard"
    HIGH = "high"


class PaymentEvent(BaseModel):
    event_id: str = Field(min_length=1)
    account_id: str = Field(min_length=1)
    amount: Decimal = Field(gt=0)
    currency: str = Field(min_length=3, max_length=3)
    risk_level: RiskLevel
    occurred_at: datetime


class AuditNotification(BaseModel):
    event_id: str
    account_id: str
    channel: str
    kind: Literal["payment_posted", "payment_review_required"]
    title: str
    body: str
    action: Literal["open_payment", "review_payment"]
    occurred_at: datetime
    decided_at: datetime

    def realtime_data(self) -> dict[str, Any]:
        return self.model_dump(mode="json")


def decide_notification(
    payment: PaymentEvent, *, decided_at: datetime | None = None
) -> AuditNotification:
    decision_time = decided_at or datetime.now(timezone.utc)
    amount = f"{payment.amount:.2f} {payment.currency.upper()}"
    if payment.risk_level is RiskLevel.HIGH:
        kind = "payment_review_required"
        title = "Payment needs review"
        body = f"Review the {amount} payment before taking further action."
        action = "review_payment"
    else:
        kind = "payment_posted"
        title = "Payment posted"
        body = f"Your {amount} payment is now posted."
        action = "open_payment"

    return AuditNotification(
        event_id=payment.event_id,
        account_id=payment.account_id,
        channel=f"account:{payment.account_id}",
        kind=kind,
        title=title,
        body=body,
        action=action,
        occurred_at=payment.occurred_at,
        decided_at=decision_time,
    )
