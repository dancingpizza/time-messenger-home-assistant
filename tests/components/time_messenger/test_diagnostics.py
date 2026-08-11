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
        options={"include_message_text": False},
        runtime_data=SimpleNamespace(task=task),
    )
    diagnostics = await async_get_config_entry_diagnostics(None, entry)  # type: ignore[arg-type]
    rendered = repr(diagnostics)
    assert "bearer-secret" not in rendered
    assert "password-secret" not in rendered
    assert "123456" not in rendered
    assert "private message" not in rendered
    assert diagnostics["listener_running"] is True
