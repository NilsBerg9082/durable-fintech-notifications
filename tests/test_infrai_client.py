import json

import httpx

from durable_notifications.infrai_client import InfraiClient


def test_queue_and_realtime_share_origin_key_and_payload() -> None:
    requests: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        return httpx.Response(200, json={"ok": True, "data": {"accepted": True}})

    client = InfraiClient(
        api_key="test-key",
        base_url="https://example.invalid",
        transport=httpx.MockTransport(handler),
    )
    notification = {"event_id": "pay_evt_1042", "account_id": "acct_71"}
    try:
        client.queue_notification(notification, "pay_evt_1042")
        client.publish_realtime(
            channel="account:acct_71",
            event="payment_posted",
            data=notification,
            account_id="acct_71",
            event_id="pay_evt_1042",
        )
    finally:
        client.close()

    assert [request.url.path for request in requests] == [
        "/v1/queue/publish",
        "/v1/realtime/publish",
    ]
    assert {request.url.host for request in requests} == {"example.invalid"}
    assert {request.headers["authorization"] for request in requests} == {
        "Bearer test-key"
    }
    assert json.loads(requests[0].content)["payload"] == notification
    assert json.loads(requests[1].content)["data"] == notification
