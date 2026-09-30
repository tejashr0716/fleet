from app.ws.manager import Client, Hub


def test_slow_client_queue_is_bounded_and_latest_survives():
    hub, client = Hub(), Client(expires_at=10**10)
    hub.clients.add(client)
    for i in range(1000):
        hub.broadcast({"type": "position", "data": {"id": i}})
    assert client.queue.qsize() == 64 and client.dropped == 936
    values = [client.queue.get_nowait()["data"]["id"] for _ in range(64)]
    assert values[-1] == 999
