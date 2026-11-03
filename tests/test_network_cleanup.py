import asyncio
import pytest
from pmca_wifi import network


def test_a_sharing_failure_does_not_skip_hotspot_shutdown_or_settings_restore(monkeypatch):
    calls = []
    monkeypatch.setattr(network, "netsh", lambda *args: calls.append(args))
    def fail(*args):
        calls.append(("sharing",))
        raise RuntimeError("simulated ICS failure")
    monkeypatch.setattr(network, "sharing", fail)
    session = network.NetworkSession()
    session.started, session.shared = True, True
    session.public, session.private = "public", "private"
    session.legacy = {"ssid": "previous", "key": "old-password", "persistent": True, "enabled": False}
    with pytest.raises(RuntimeError, match="simulated ICS failure"):
        asyncio.run(session.close())
    assert ("stop", "hostednetwork") in calls
    assert ("set", "hostednetwork", "ssid=previous", "key=old-password", "keyUsage=persistent") in calls
    assert ("set", "hostednetwork", "mode=disallow") in calls


def test_an_existing_active_hotspot_is_left_unchanged(monkeypatch):
    monkeypatch.setattr(network, "legacy_settings", lambda: {"state": 2})
    def forbidden(*args):
        raise AssertionError("Must not mutate an existing hotspot")
    monkeypatch.setattr(network, "netsh", forbidden)
    with pytest.raises(RuntimeError, match="正在使用"):
        asyncio.run(network.NetworkSession().start("Test", "12345678"))
