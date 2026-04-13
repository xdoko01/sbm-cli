# Secure Password Storage via Windows Credential Manager

**Date:** 2026-04-13  
**Status:** Approved  
**Scope:** sbm-cli — replace plaintext `password` in `config.toml` with Windows Credential Manager via the `keyring` library

---

## Context

`sbm-cli` currently stores the SBM password in plaintext in `~/.sbm-cli/config.toml` under `[connection].password`. This design replaces that with secure storage in Windows Credential Manager.

**Platform:** Windows only. This decision is intentional and must be preserved. The `keyring` library is used as the interface, but the Windows Credential Manager backend is the sole supported target. If cross-platform support is ever needed, this design should be revisited.

---

## Credential Key Design

Each Windows Credential Manager entry is identified by a **service name** and an **account (username)**:

- **Service name:** `sbm-cli:<host>` — e.g. `sbm-cli:https://sbm.example.com`
- **Account:** the `username` value from `[connection]`

Using the host in the service name avoids collisions if multiple SBM instances are ever configured with the same username.

---

## Module Structure

A new `sbm_cli/credentials.py` module is the sole interface to `keyring`. No other file imports `keyring` directly.

```python
# sbm_cli/credentials.py
import keyring

def service_name(host: str) -> str:
    return f"sbm-cli:{host}"

def get_password(host: str, username: str) -> str | None:
    return keyring.get_password(service_name(host), username)

def set_password(host: str, username: str, password: str) -> None:
    keyring.set_password(service_name(host), username, password)

def delete_password(host: str, username: str) -> None:
    keyring.delete_password(service_name(host), username)
```

---

## Config Changes

### `config.toml`

The `password` field under `[connection]` is **removed** after migration. A valid config.toml no longer contains a password:

```toml
[connection]
host       = "https://sbm.example.com"
username   = "myuser"
verify_ssl = false
```

### `Config` dataclass (`config.py`)

- `password` is removed as a required field in `[connection]` validation
- `load_config()` no longer raises `ConfigError` for a missing `password` key
- `save_config()` never writes a `password` field to disk

---

## Migration on First Run

Triggered automatically inside `load_config()` when a `password` key is found in the parsed `[connection]` section:

1. Call `credentials.set_password(host, username, password)` to store in Windows Credential Manager
2. Remove `password` from the parsed config data
3. Rewrite `config.toml` to disk (without the password field)
4. Print a one-time notice to stdout: `"Password migrated to Windows Credential Manager."`

Migration is idempotent: if the `password` key is absent from config.toml (already migrated), nothing happens.

---

## `sbm configure` Flow

The interactive setup command (`cli.py`) already prompts for password via `click.prompt("Password", hide_input=True)`. The only change: instead of including the password in the saved config.toml, call `credentials.set_password(host, username, password)` after the prompt.

Re-running `sbm configure` overwrites the existing keychain entry for that host/username pair.

---

## Runtime Password Retrieval

In `cli.py`, after loading the config and before constructing the `SBMClient`, retrieve the password:

```python
password = credentials.get_password(config.connection.host, config.connection.username)
if password is None:
    click.echo(
        "Error: No password found in Windows Credential Manager.\n"
        "Run 'sbm configure' to set up your credentials.",
        err=True,
    )
    raise SystemExit(2)
```

The `SBMClient` receives the retrieved plaintext password as before — no changes to `client.py`.

---

## Dependency

Add to `pyproject.toml` under `[project.dependencies]`:

```toml
"keyring>=25.0"
```

`keyring` 25+ uses Windows Credential Manager automatically on Windows with no additional backend configuration required.

---

## Testing

- **Unit tests** mock `credentials.get_password` / `credentials.set_password` directly via `pytest-mock`. No real Windows Credential Manager calls in tests.
- **Migration test** (`test_config.py`): load a config fixture containing a plaintext `password` field — assert the field is absent from the rewritten file and `credentials.set_password` was called with the correct arguments.
- **Missing credential test**: `credentials.get_password` returns `None` → CLI exits with code 2 and the expected error message.
- Existing `client.py` and `cli.py` tests remain structurally unchanged; fixtures that supply a password are updated to mock `credentials.get_password` instead.

---

## Out of Scope

- Cross-platform support (macOS Keychain, Linux Secret Service) — intentionally excluded
- Environment variable fallback for CI/automation — not needed for this use case
- `sbm delete-password` command — re-running `sbm configure` is sufficient to overwrite
