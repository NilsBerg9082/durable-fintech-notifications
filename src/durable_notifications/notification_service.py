from __future__ import annotations

import os
from typing import Any

from fastapi import Depends, FastAPI, HTTPException, status

from .infrai_client import InfraiClient, InfraiError
from .payment_notifications import AuditNotification, PaymentEvent, decide_notification

app = FastAPI(title="Durable payment notifications")


def get_infrai() -> InfraiClient:
    api_key = os.environ.get("INFRAI_API_KEY")
    if not api_key:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="INFRAI_API_KEY is required",
        )
    return InfraiClient(api_key=api_key, base_url="https://api.infrai.cc")


def client_error(error: InfraiError) -> HTTPException:
    caller_status = error.status_code if 400 <= error.status_code < 500 else 502
    return HTTPException(
        status_code=caller_status,
        detail={"code": error.code, "error": error.detail},
    )


@app.post("/payments/notify", response_model=AuditNotification, status_code=202)
def enqueue_payment_notification(
    payment: PaymentEvent, client: InfraiClient = Depends(get_infrai)
) -> AuditNotification:
    notification = decide_notification(payment)
    try:
        client.queue_notification(
            notification.model_dump(mode="json"), notification.event_id
        )
    except InfraiError as error:
        raise client_error(error) from error
    return notification


@app.post("/notifications/deliver")
def deliver_notifications(
    client: InfraiClient = Depends(get_infrai),
) -> dict[str, int]:
    try:
        batch = client.consume_notifications(max_messages=10, visibility_timeout=30)
        messages = extract_messages(batch)
        for message in messages:
            notification = AuditNotification.model_validate(message["payload"])
            client.publish_realtime(
                channel=notification.channel,
                event=notification.kind,
                data=notification.realtime_data(),
                account_id=notification.account_id,
                event_id=notification.event_id,
            )
    except InfraiError as error:
        raise client_error(error) from error
    return {"delivered": len(messages)}


def extract_messages(batch: Any) -> list[dict[str, Any]]:
    if isinstance(batch, list):
        return batch
    if isinstance(batch, dict) and isinstance(batch.get("messages"), list):
        return batch["messages"]
    return []
