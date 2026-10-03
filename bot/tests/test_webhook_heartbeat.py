import asyncio
from types import SimpleNamespace
from unittest.mock import Mock

from core import heartbeat, webserver


def test_reload_rejects_missing_or_wrong_secret_without_dispatch(monkeypatch):
    dispatch = Mock()
    schedule = Mock()
    monkeypatch.setattr(webserver, "bot_instance", SimpleNamespace(
        dispatch=dispatch, loop=SimpleNamespace(call_soon_threadsafe=schedule)
    ))
    client = webserver.app.test_client()
    monkeypatch.setattr(webserver, "WEBHOOK_SECRET", "")
    assert client.post("/api/webhook/reload").status_code == 503
    monkeypatch.setattr(webserver, "WEBHOOK_SECRET", "test-secret")
    assert client.post("/api/webhook/reload").status_code == 401
    assert client.post("/api/webhook/reload", headers={"Authorization": "Bearer wrong"}).status_code == 401
    assert client.post("/api/webhook/reload", headers={"Authorization": "Bearer sai-🔐"}).status_code == 401
    schedule.assert_not_called()
    dispatch.assert_not_called()


def test_authenticated_reload_is_accepted(monkeypatch):
    events = []
    monkeypatch.setattr(webserver, "WEBHOOK_SECRET", "test-secret")
    monkeypatch.setattr(webserver, "bot_instance", SimpleNamespace(
        dispatch=events.append,
        loop=SimpleNamespace(call_soon_threadsafe=lambda fn, event: fn(event)),
    ))
    response = webserver.app.test_client().post(
        "/api/webhook/reload", headers={"Authorization": "Bearer test-secret"}
    )
    assert response.status_code == 200
    assert events == ["config_reload"]


def test_heartbeat_reports_disconnect_and_recovery(monkeypatch):
    class Bot:
        def __init__(self):
            self.phase = 0

        async def wait_until_ready(self):
            return None

        def is_closed(self):
            return self.phase == 3

        def is_ready(self):
            return self.phase != 1

        @property
        def latency(self):
            return float("inf") if self.phase == 1 else 0.042

    bot = Bot()
    snapshots = []

    async def save(payload, path):
        snapshots.append(payload.copy())

    async def sleep(seconds):
        bot.phase += 1

    monkeypatch.setattr(heartbeat, "save_json_async", save)
    monkeypatch.setattr(heartbeat.asyncio, "sleep", sleep)
    asyncio.run(heartbeat._heartbeat(bot))
    assert [s["online"] for s in snapshots] == [True, False, True]
    assert [s["latency_ms"] for s in snapshots] == [42, None, 42]
