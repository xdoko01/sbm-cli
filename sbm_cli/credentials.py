"""System keyring access via the keyring library.

Supports Windows (Credential Manager), macOS (Keychain), and Linux
(GNOME Keyring / KWallet via SecretService). On headless Linux systems
without a running keyring daemon, all operations raise NoKeyringAvailable.
"""
from __future__ import annotations

import os
import sys

import click
import keyring
import keyring.errors


PASSWORD_ENV_VAR = "SBM_CLI_PASSWORD"


class NoKeyringAvailable(Exception):
    """Raised when no system keyring backend is accessible."""


class PasswordUnavailable(PermissionError):
    """No password could be resolved from any source.

    Subclasses PermissionError so the existing command-level handlers, which
    map PermissionError to an auth_error envelope with exit code 2, catch it
    without modification.
    """


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


def _stdin_is_tty() -> bool:
    """True when stdin is an interactive terminal. False on any doubt.

    A module-level function rather than an inline call so tests can patch it:
    click's CliRunner swaps sys.stdin inside invoke(), so a test cannot patch
    the object the code will actually see.
    """
    try:
        return sys.stdin is not None and sys.stdin.isatty()
    except (ValueError, AttributeError):  # detached or closed stdin
        return False


def resolve_password(host: str, username: str) -> tuple[str, str]:
    """Resolve the password for (host, username).

    Order: SBM_CLI_PASSWORD -> system keyring -> interactive prompt (TTY only).
    Returns (password, source), where source is one of
    'env:SBM_CLI_PASSWORD', 'keyring', 'prompt'.

    Raises PasswordUnavailable when no source yields a password.
    """
    env_password = os.environ.get(PASSWORD_ENV_VAR)
    if env_password:
        # Deliberately not stripped: a password may end in whitespace.
        return env_password, f"env:{PASSWORD_ENV_VAR}"

    try:
        stored = get_password(host, username)
    except NoKeyringAvailable:
        # No backend at all — the prompt is the only remaining source, and it
        # is safe only on a terminal. Piped or redirected stdin would hang.
        if not _stdin_is_tty():
            raise PasswordUnavailable(
                f"No password available. Set {PASSWORD_ENV_VAR}, or run "
                "'sbm configure setup' on an interactive terminal."
            ) from None
        entered = click.prompt("Password", hide_input=True)
        if not entered:
            raise PasswordUnavailable("No password entered.") from None
        return entered, "prompt"

    if not stored:
        raise PasswordUnavailable(
            f"No password found in {platform_keyring_name()}. "
            "Run 'sbm configure' to set up credentials."
        )
    return stored, "keyring"
