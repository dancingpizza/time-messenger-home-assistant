"""Tests proving diagnostics never include secrets or message text."""

from types import SimpleNamespace

from custom_components.time_messenger.diagnostics import async_get_config_entry_diagnostics


async def test_diagnostics_are_allowlisted() -> None:
    task = SimpleNamespace(done=lambda: False)
    entry = SimpleNamespace(
        entry_id="entry",
        data={
            "auth_mode": "session",
            "tenant_origin": "https://time.example",
            "user_id": "me",
            "server_version": "10.2",
            "token": "bearer-secret",
            "password": "password-secret",
            "mfa_code": "123456",
            "message_text": "private message",
        },
        options={
            "include_message_text": False,
            "keep_online": True,
            "keep_online_weekdays": ["mon", "tue"],
            "keep_online_start_time": "09:00:00",
            "keep_online_end_time": "18:00:00",
            "keep_online_interval_minutes": 4,
        },
        runtime_data=SimpleNamespace(task=task, keep_online_task=task),
    )
    diagnostics = await async_get_config_entry_diagnostics(None, entry)  # type: ignore[arg-type]
    rendered = repr(diagnostics)
    assert "bearer-secret" not in rendered
    assert "password-secret" not in rendered
    assert "123456" not in rendered
    assert "private message" not in rendered
    assert diagnostics["listener_running"] is True
    assert diagnostics["auth_health_running"] is False
    assert diagnostics["keep_online_enabled"] is True
    assert diagnostics["keep_online_weekdays"] == ["mon", "tue"]
    assert diagnostics["keep_online_start_time"] == "09:00:00"
    assert diagnostics["keep_online_end_time"] == "18:00:00"
    assert diagnostics["keep_online_interval_minutes"] == 4
    assert diagnostics["keep_online_running"] is True
