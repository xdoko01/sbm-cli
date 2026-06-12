"""System keyring access via the keyring library.

Supports Windows (Credential Manager), macOS (Keychain), and Linux
(GNOME Keyring / KWallet via SecretService). On headless Linux systems
without a running keyring daemon, all operations raise NoKeyringAvailable.
"""
from __future__ import annotations

import sys

import keyring
import keyring.errors


class NoKeyringAvailable(Exception):
    """Raised when no system keyring backend is accessible."""


def platform_keyring_name() -> str:
    """Return the human-readable name of the system keyring for the current platform."""
    if sys.platform == "win32":
        return "Windows Credential Manager"
    elif sys.platform == "darwin":
        return "macOS Keychain"
    else:
        return "system keyring"


def service_name(host: str) -> str:
    """Build the credential service key: 'sbm-cli:<host>'."""
    return f"sbm-cli:{host}"


def get_password(host: str, username: str) -> str | None:
    """Retrieve password from the system keyring. Returns None if not found.

    Raises NoKeyringAvailable if no keyring backend is accessible.
    """
    try:
        return keyring.get_password(service_name(host), username)
    except keyring.errors.NoKeyringError as exc:
        raise NoKeyringAvailable(str(exc)) from exc


def set_password(host: str, username: str, password: str) -> None:
    """Store password in the system keyring.

    Raises NoKeyringAvailable if no keyring backend is accessible.
    """
    try:
        keyring.set_password(service_name(host), username, password)
    except keyring.errors.NoKeyringError as exc:
        raise NoKeyringAvailable(str(exc)) from exc


def delete_password(host: str, username: str) -> None:
    """Remove password from the system keyring.

    Raises keyring.errors.PasswordDeleteError if no credential exists.
    Raises NoKeyringAvailable if no keyring backend is accessible.
    """
    try:
        keyring.delete_password(service_name(host), username)
    except keyring.errors.NoKeyringError as exc:
        raise NoKeyringAvailable(str(exc)) from exc
