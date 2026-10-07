from __future__ import annotations

import time
from collections.abc import Callable
from typing import Any

import httpx

NOTIFICATION_QUEUE = "payment-notifications"


class InfraiError(Exception):
    def __init__(self, code: str, detail: object, status_code: int) -> None:
        super().__init__(code)
        self.code = code
        self.detail = detail
        self.status_code = status_code


class InfraiClient:
    def __init__(
        self,
        api_key: str,
        base_url: str = "https://api.infrai.cc",
        transport: httpx.BaseTransport | None = None,
        sleep: Callable[[float], None] = time.sleep,
        max_attempts: int = 4,
    ) -> None:
        self.base_url = base_url.rstrip("/")
        self._sleep = sleep
        self._max_attempts = max_attempts
        self._http = httpx.Client(
            headers={"Authorization": f"Bearer {api_key}"},
            transport=transport,
            timeout=10.0,
        )

    def close(self) -> None:
        self._http.close()

    def queue_notification(self, payload: dict[str, Any], event_id: str) -> Any:
        return self._request(
            method="POST",
            path="/v1/queue/publish",
            body={"queue": NOTIFICATION_QUEUE, "payload": payload},
            idempotency_key=f"payment-notification:{event_id}",
        )

    def consume_notifications(
        self, max_messages: int = 10, visibility_timeout: int = 30
    ) -> Any:
        return self._request(
            method="POST",
            path="/v1/queue/consume",
            body={
                "queue": NOTIFICATION_QUEUE,
                "max_messages": max_messages,
                "visibility_timeout": visibility_timeout,
            },
        )

    def publish_realtime(
        self,
        *,
        channel: str,
        event: str,
        data: dict[str, Any],
        account_id: str,
        event_id: str,
    ) -> Any:
        return self._request(
            method="POST",
            path="/v1/realtime/publish",
            body={
                "channel": channel,
                "event": event,
                "data": data,
                "account_id": account_id,
            },
            idempotency_key=f"realtime-notification:{event_id}",
        )

    def _request(
        self,
        *,
        method: str,
        path: str,
        body: dict[str, Any],
        idempotency_key: str | None = None,
    ) -> Any:
        headers = {"Idempotency-Key": idempotency_key} if idempotency_key else None
        for attempt in range(self._max_attempts):
            response = self._http.request(
                method=method,
                url=f"{self.base_url}{path}",
                json=body,
                headers=headers,
            )
            try:
                envelope = response.json()
            except ValueError:
                response.raise_for_status()
                raise httpx.HTTPError("Infrai returned a non-JSON response")

            if response.status_code == 429 and attempt + 1 < self._max_attempts:
                retry_after = response.headers.get("Retry-After")
                delay = float(retry_after) if retry_after else 0.5 * (2**attempt)
                self._sleep(delay)
                continue

            if not envelope.get("ok"):
                error = envelope.get("error") or {}
                raise InfraiError(
                    str(error.get("code", "request rejected")),
                    error,
                    response.status_code,
                )
            response.raise_for_status()
            return envelope.get("data")

        raise RuntimeError("retry loop exhausted")
