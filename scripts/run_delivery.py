from durable_notifications.infrai_client import InfraiClient
from durable_notifications.notification_service import deliver_notifications, get_infrai


def main() -> None:
    client = get_infrai()
    try:
        result = deliver_notifications(client)
        print(f"Delivered {result['delivered']} notification(s).")
    finally:
        if isinstance(client, InfraiClient):
            client.close()


if __name__ == "__main__":
    main()
