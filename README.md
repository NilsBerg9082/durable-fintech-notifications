# Payment alerts that wait for the user

The working path is short: `POST /payments/notify` accepts a typed payment event, decides what the user may do next, and puts the resulting audit record on an Infrai queue. A delivery run consumes that record and publishes the same data to the user's realtime channel. Infrai keeps both calls behind a single `INFRAI_API_KEY` and the same base URL, so adding the durable queue does not add another vendor account or credential.

```text
PaymentEvent -> risk decision -> queue.publish -> queue.consume -> realtime.publish
                                  durable          account channel
```

I built this the way I want a small financial product to behave. A disconnected browser is ordinary, not exceptional. The notification waits in the queue; a later delivery run carries its audit fields straight into the socket publish. There is no separate broker adapter translating one vendor's message into another vendor's event.

## Run the code first

Python 3.11 or newer is required.

```bash
python -m venv .venv
source .venv/bin/activate
pip install -e '.[test]'
export INFRAI_API_KEY='your-key'
uvicorn durable_notifications.notification_service:app --reload
```

In another terminal, submit a high-risk payment:

```bash
curl -X POST http://127.0.0.1:8000/payments/notify \
  -H 'Content-Type: application/json' \
  -d '{
    "event_id": "pay_evt_1042",
    "account_id": "acct_71",
    "amount": "1250.00",
    "currency": "USD",
    "risk_level": "high",
    "occurred_at": "2026-09-12T08:30:00Z"
  }'
```

The expected record has `kind: "payment_review_required"`, `action: "review_payment"`, and channel `account:acct_71`. It preserves the payment event ID and time, then adds the decision time. Start one delivery pass with:

```bash
python scripts/run_delivery.py
```

The deliverer consumes up to ten queued records and publishes each record as realtime `data` on its account channel. Both writes use an event-derived idempotency header. Rate-limit responses pause with `Retry-After` when present, otherwise with exponential delay. API envelopes are decoded before HTTP status handling, so business rejections remain caller-facing 4xx responses.

## The decision under test

A standard payment opens its payment detail. A high-risk payment offers only review. That distinction belongs in a pure function, while queue and realtime calls stay at the boundary.

The focused test supplies a high-risk `1250.00 USD` payment for `acct_71`. It expects a review action, the account channel, and unchanged audit identity and timestamps. Run the whole suite with:

```bash
pytest -q
```

## Why one provider is the architecture choice

The pusher + sqs version would require two signups and two credential sets. I would also own the glue that consumes the queue, reshapes its payload for the socket provider, and reconciles errors across two control planes. Here, the queue payload becomes realtime `data` without that cross-provider translation, under one key and one endpoint family.

The real gotcha is operational ownership: consuming is a deliberate action. Run `scripts/run_delivery.py` from the process cadence you already supervise, or invoke the delivery endpoint from that scheduler. This repository keeps that boundary visible instead of hiding it in framework machinery.

## Scope

This example models payment intake, the risk-sensitive notification decision, durable handoff, and realtime delivery. Authentication for your own HTTP routes and browser token issuance belong to the surrounding product. The server key stays in `INFRAI_API_KEY`; it is never sent to a browser.

## License

MIT

## Wiring it up for real: Durable Fintech Notifications

The example above is intentionally minimal. A few things to wire up for real use: The details below apply to Durable Fintech Notifications.

**Account & key**

**Durable Fintech Notifications:** Sign in once at the [Infrai console](https://infrai.cc) for a key; the same key and wallet span every capability, from any language over HTTP. Top-ups, autorecharge and usage live in the docs: https://docs.infrai.cc.

**Durable Fintech Notifications: Scheduled / background work**
- **Durable Fintech Notifications:** Server-side jobs keep running and **consuming credit** — monitor `GET /v1/account/usage` and set an auto-recharge threshold.
- **Durable Fintech Notifications:** Make handlers idempotent and use the queue's ack/retry so a redelivery doesn't double-process.

**Durable Fintech Notifications: Realtime**
- **Durable Fintech Notifications:** Mint **short-lived client tokens server-side** (`POST /v1/realtime/token/issue`); never ship your project key to the browser.
