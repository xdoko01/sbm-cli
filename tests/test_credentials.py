import sys
import pytest
import keyring.errors
from sbm_cli.credentials import (
    service_name, get_password, set_password, delete_password,
    platform_keyring_name, NoKeyringAvailable,
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
