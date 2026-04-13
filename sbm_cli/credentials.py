"""Windows Credential Manager access via keyring.

Platform: Windows only. This module uses the keyring library which automatically
selects Windows Credential Manager on Windows. Cross-platform support is
intentionally out of scope — if cross-platform support is ever needed, revisit
the backend selection strategy here.
"""
from __future__ import annotations

import keyring


def service_name(host: str) -> str:
    """Build the credential service key: 'sbm-cli:<host>'."""
    return f"sbm-cli:{host}"


def get_password(host: str, username: str) -> str | None:
    """Retrieve password from Windows Credential Manager. Returns None if not found."""
    return keyring.get_password(service_name(host), username)


def set_password(host: str, username: str, password: str) -> None:
    """Store password in Windows Credential Manager."""
    keyring.set_password(service_name(host), username, password)


def delete_password(host: str, username: str) -> None:
    """Remove password from Windows Credential Manager.

    Raises keyring.errors.PasswordDeleteError if no credential exists for the given host/username.
    """
    keyring.delete_password(service_name(host), username)
