import sys
import pytest
import keyring.errors
from sbm_cli.credentials import (
    service_name, get_password, set_password, delete_password,
    platform_keyring_name, NoKeyringAvailable,
    resolve_password, PasswordUnavailable, PASSWORD_ENV_VAR, _stdin_is_tty,
)

# Note: the autouse mock_credentials fixture in conftest.py patches
# sbm_cli.credentials.get_password at the module level. These tests import
# the functions directly at module load time (before fixtures run), so the
# locally-bound references here still point to the original function objects.
# The fixture patches a different level (module namespace vs. local binding),
# so both can coexist without interference.


def test_service_name():
    assert service_name("https://sbm.example.com") == "sbm-cli:https://sbm.example.com"


def test_get_password_calls_keyring(mocker):
    mock_get = mocker.patch("sbm_cli.credentials.keyring.get_password", return_value="secret")
    result = get_password("https://sbm.test", "alice")
    mock_get.assert_called_once_with("sbm-cli:https://sbm.test", "alice")
    assert result == "secret"


def test_get_password_returns_none_when_not_found(mocker):
    mocker.patch("sbm_cli.credentials.keyring.get_password", return_value=None)
    assert get_password("https://sbm.test", "alice") is None


def test_set_password_calls_keyring(mocker):
    mock_set = mocker.patch("sbm_cli.credentials.keyring.set_password")
    set_password("https://sbm.test", "alice", "secret")
    mock_set.assert_called_once_with("sbm-cli:https://sbm.test", "alice", "secret")


def test_delete_password_calls_keyring(mocker):
    mock_del = mocker.patch("sbm_cli.credentials.keyring.delete_password")
    delete_password("https://sbm.test", "alice")
    mock_del.assert_called_once_with("sbm-cli:https://sbm.test", "alice")


def test_platform_keyring_name_windows(mocker):
    mocker.patch.object(sys, "platform", "win32")
    assert platform_keyring_name() == "Windows Credential Manager"


def test_platform_keyring_name_macos(mocker):
    mocker.patch.object(sys, "platform", "darwin")
    assert platform_keyring_name() == "macOS Keychain"


def test_platform_keyring_name_linux(mocker):
    mocker.patch.object(sys, "platform", "linux")
    assert platform_keyring_name() == "system keyring"


def test_get_password_raises_no_keyring_available(mocker):
    mocker.patch(
        "sbm_cli.credentials.keyring.get_password",
        side_effect=keyring.errors.NoKeyringError(),
    )
    with pytest.raises(NoKeyringAvailable):
        get_password("https://sbm.test", "alice")


def test_set_password_raises_no_keyring_available(mocker):
    mocker.patch(
        "sbm_cli.credentials.keyring.set_password",
        side_effect=keyring.errors.NoKeyringError(),
    )
    with pytest.raises(NoKeyringAvailable):
        set_password("https://sbm.test", "alice", "secret")


def test_delete_password_raises_no_keyring_available(mocker):
    mocker.patch(
        "sbm_cli.credentials.keyring.delete_password",
        side_effect=keyring.errors.NoKeyringError(),
    )
    with pytest.raises(NoKeyringAvailable):
        delete_password("https://sbm.test", "alice")


# ---------------------------------------------------------------------------
# resolve_password
# ---------------------------------------------------------------------------

def test_password_env_var_name():
    assert PASSWORD_ENV_VAR == "SBM_CLI_PASSWORD"


def test_resolve_password_prefers_env_var(mocker, monkeypatch):
    monkeypatch.setenv("SBM_CLI_PASSWORD", "fromenv")
    mock_get = mocker.patch("sbm_cli.credentials.get_password", return_value="fromkeyring")
    password, source = resolve_password("https://sbm.test", "alice")
    assert password == "fromenv"
    assert source == "env:SBM_CLI_PASSWORD"
    mock_get.assert_not_called()


def test_resolve_password_env_var_not_stripped(monkeypatch, mocker):
    monkeypatch.setenv("SBM_CLI_PASSWORD", "  pad ded  ")
    mocker.patch("sbm_cli.credentials.get_password", return_value=None)
    password, _ = resolve_password("https://sbm.test", "alice")
    assert password == "  pad ded  "


def test_resolve_password_empty_env_var_falls_through_to_keyring(monkeypatch, mocker):
    monkeypatch.setenv("SBM_CLI_PASSWORD", "")
    mocker.patch("sbm_cli.credentials.get_password", return_value="fromkeyring")
    password, source = resolve_password("https://sbm.test", "alice")
    assert password == "fromkeyring"
    assert source == "keyring"


def test_resolve_password_uses_keyring(mocker):
    mocker.patch("sbm_cli.credentials.get_password", return_value="stored")
    assert resolve_password("https://sbm.test", "alice") == ("stored", "keyring")


def test_resolve_password_raises_when_keyring_empty(mocker):
    """Reachable keyring with no entry must NOT prompt — preserves today's behaviour."""
    mocker.patch("sbm_cli.credentials.get_password", return_value=None)
    mock_prompt = mocker.patch("sbm_cli.credentials.click.prompt")
    with pytest.raises(PasswordUnavailable) as exc:
        resolve_password("https://sbm.test", "alice")
    assert "Run 'sbm configure'" in str(exc.value)
    mock_prompt.assert_not_called()


def test_resolve_password_prompts_on_tty_when_no_keyring(mocker):
    mocker.patch("sbm_cli.credentials.get_password",
                 side_effect=NoKeyringAvailable("no daemon"))
    mocker.patch("sbm_cli.credentials._stdin_is_tty", return_value=True)
    mocker.patch("sbm_cli.credentials.click.prompt", return_value="typed")
    assert resolve_password("https://sbm.test", "alice") == ("typed", "prompt")


def test_resolve_password_no_tty_no_keyring_raises_without_prompting(mocker):
    mocker.patch("sbm_cli.credentials.get_password",
                 side_effect=NoKeyringAvailable("no daemon"))
    mocker.patch("sbm_cli.credentials._stdin_is_tty", return_value=False)
    mock_prompt = mocker.patch("sbm_cli.credentials.click.prompt")
    with pytest.raises(PasswordUnavailable) as exc:
        resolve_password("https://sbm.test", "alice")
    assert "SBM_CLI_PASSWORD" in str(exc.value)
    mock_prompt.assert_not_called()


def test_resolve_password_empty_prompt_raises(mocker):
    mocker.patch("sbm_cli.credentials.get_password",
                 side_effect=NoKeyringAvailable("no daemon"))
    mocker.patch("sbm_cli.credentials._stdin_is_tty", return_value=True)
    mocker.patch("sbm_cli.credentials.click.prompt", return_value="")
    with pytest.raises(PasswordUnavailable):
        resolve_password("https://sbm.test", "alice")


def test_password_unavailable_is_a_permission_error():
    """Existing `except PermissionError` handlers must catch it unchanged."""
    assert issubclass(PasswordUnavailable, PermissionError)


def test_stdin_is_tty_survives_closed_stdin(mocker):
    mocker.patch("sbm_cli.credentials.sys.stdin", None)
    assert _stdin_is_tty() is False
