# Secure Password Storage via Windows Credential Manager — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace plaintext `password` in `~/.sbm-cli/config.toml` with Windows Credential Manager storage via the `keyring` library.

**Architecture:** A new `credentials.py` module wraps `keyring`. `Config` and `save_config` are updated to never handle passwords. `load_config` detects and auto-migrates any existing plaintext password to the keychain. `cli.py` stores to the keychain in `configure_setup` and retrieves from it in `AppContext.client`.

**Tech Stack:** Python 3.11+, `keyring>=25.0`, `pytest-mock`, Click, `tomllib`

---

## File Map

| File | Action | Responsibility |
|------|--------|----------------|
| `pyproject.toml` | Modify | Add `keyring>=25.0` dependency |
| `sbm_cli/credentials.py` | **Create** | Thin keyring wrapper: `service_name`, `get_password`, `set_password`, `delete_password` |
| `sbm_cli/config.py` | Modify | Remove `password` from `Config`, `load_config`, `save_config`; add migration |
| `sbm_cli/cli.py` | Modify | `configure_setup` stores to keychain; `AppContext.client` retrieves from keychain |
| `tests/test_credentials.py` | **Create** | Unit tests for credentials module (all keyring calls mocked) |
| `tests/test_config.py` | Modify | Remove password from all fixtures; add migration tests |
| `tests/test_cli.py` | Modify | Remove password from `_make_app_config`; add missing-credentials and configure tests |
| `tests/conftest.py` | Modify | Remove password from `sample_config`; add `mock_credentials` autouse fixture |

---

### Task 1: Add `keyring` dependency

**Files:**
- Modify: `pyproject.toml`

- [ ] **Step 1: Edit `pyproject.toml` — add keyring**

In `pyproject.toml`, change the `dependencies` list from:

```toml
dependencies = [
    "click>=8.1",
    "requests>=2.32",
    "rich>=13.0",
]
```

To:

```toml
dependencies = [
    "click>=8.1",
    "keyring>=25.0",
    "requests>=2.32",
    "rich>=13.0",
]
```

- [ ] **Step 2: Install updated dependencies**

```bash
pip install -e ".[dev]"
```

Expected: `keyring` installs successfully. No errors.

- [ ] **Step 3: Run tests to verify nothing broke**

```bash
pytest tests/ -v --ignore=tests/integration
```

Expected: all existing tests PASS.

- [ ] **Step 4: Commit**

```bash
git add pyproject.toml
git commit -m "chore: add keyring dependency for Windows Credential Manager"
```

---

### Task 2: Create `sbm_cli/credentials.py` (TDD)

**Files:**
- Create: `tests/test_credentials.py`
- Create: `sbm_cli/credentials.py`

- [ ] **Step 1: Write failing tests**

Create `tests/test_credentials.py`:

```python
from sbm_cli.credentials import service_name, get_password, set_password, delete_password


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
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
pytest tests/test_credentials.py -v
```

Expected: `ImportError` — `sbm_cli.credentials` does not exist yet.

- [ ] **Step 3: Create `sbm_cli/credentials.py`**

```python
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
    """Remove password from Windows Credential Manager."""
    keyring.delete_password(service_name(host), username)
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
pytest tests/test_credentials.py -v
```

Expected: all 5 tests PASS.

- [ ] **Step 5: Commit**

```bash
git add sbm_cli/credentials.py tests/test_credentials.py
git commit -m "feat: add credentials module wrapping keyring for Windows Credential Manager"
```

---

### Task 3: Remove `password` from `Config`, `save_config`, and `load_config` — update all consumers atomically

This task touches many files. All changes must be made together so the suite stays green.

**Files:**
- Modify: `sbm_cli/config.py`
- Modify: `tests/test_config.py`
- Modify: `tests/conftest.py`
- Modify: `tests/test_cli.py`

- [ ] **Step 1: Write two new failing tests in `test_config.py`**

Add at the end of `tests/test_config.py`:

```python
def test_load_config_no_password_required(tmp_path, mocker):
    mocker.patch("sbm_cli.credentials.set_password")
    toml_content = """\
[connection]
host     = "https://sbm.test"
username = "user"
verify_ssl = false

[defaults]
table_id  = 1000
report_id = 0
"""
    path = tmp_path / "config.toml"
    path.write_text(toml_content, encoding="utf-8")
    config = load_config(path)
    assert config.host == "https://sbm.test"
    assert config.username == "user"


def test_save_config_does_not_write_password(tmp_path):
    config = Config(
        host="https://sbm.test", username="user",
        verify_ssl=False, table_id=1000, report_id=0,
    )
    path = tmp_path / "config.toml"
    save_config(config, path)
    content = path.read_text()
    assert "password" not in content
```

- [ ] **Step 2: Run the two new tests to verify they fail**

```bash
pytest tests/test_config.py::test_load_config_no_password_required tests/test_config.py::test_save_config_does_not_write_password -v
```

Expected: FAIL — `Config.__init__()` still requires `password` and `save_config` still writes it.

- [ ] **Step 3: Update `sbm_cli/config.py` — remove `password` from `Config` dataclass**

Change the `Config` dataclass (lines 41–52) from:

```python
@dataclass
class Config:
    host: str
    username: str
    password: str
    verify_ssl: bool
    table_id: int
    report_id: int
    transitions: dict[str, TransitionConfig] = field(default_factory=dict)
    teams: dict[str, TeamConfig] = field(default_factory=dict)
    users: dict[str, UserConfig] = field(default_factory=dict)
    fields: dict[str, FieldDef] = field(default_factory=dict)
    list_fields: list[str] = field(default_factory=list)
```

To:

```python
@dataclass
class Config:
    host: str
    username: str
    verify_ssl: bool
    table_id: int
    report_id: int
    transitions: dict[str, TransitionConfig] = field(default_factory=dict)
    teams: dict[str, TeamConfig] = field(default_factory=dict)
    users: dict[str, UserConfig] = field(default_factory=dict)
    fields: dict[str, FieldDef] = field(default_factory=dict)
    list_fields: list[str] = field(default_factory=list)
```

- [ ] **Step 4: Update `load_config` — remove `password` from required-key check and `Config()` constructor**

Change line 75 from:

```python
    missing = [k for k in ("host", "username", "password") if not conn.get(k)]
```

To:

```python
    missing = [k for k in ("host", "username") if not conn.get(k)]
```

Change the `return Config(...)` block (lines 127–139) from:

```python
    return Config(
        host=conn["host"],
        username=conn["username"],
        password=conn["password"],
        verify_ssl=conn.get("verify_ssl", True),
        table_id=defaults.get("table_id", 1000),
        report_id=defaults.get("report_id", 0),
        transitions=transitions,
        teams=teams,
        users=users,
        fields=field_defs,
        list_fields=list_fields,
    )
```

To:

```python
    return Config(
        host=conn["host"],
        username=conn["username"],
        verify_ssl=conn.get("verify_ssl", True),
        table_id=defaults.get("table_id", 1000),
        report_id=defaults.get("report_id", 0),
        transitions=transitions,
        teams=teams,
        users=users,
        fields=field_defs,
        list_fields=list_fields,
    )
```

- [ ] **Step 5: Update `save_config` — remove the `password` line**

Change the `lines` list start (lines 158–163) from:

```python
    lines: list[str] = [
        "[connection]",
        f'host       = "{_toml_str(config.host)}"',
        f'username   = "{_toml_str(config.username)}"',
        f'password   = "{_toml_str(config.password)}"',
        f"verify_ssl = {'true' if config.verify_ssl else 'false'}",
        "",
```

To:

```python
    lines: list[str] = [
        "[connection]",
        f'host       = "{_toml_str(config.host)}"',
        f'username   = "{_toml_str(config.username)}"',
        f"verify_ssl = {'true' if config.verify_ssl else 'false'}",
        "",
```

- [ ] **Step 6: Update `tests/test_config.py` — remove `password` from VALID_TOML**

Replace the `VALID_TOML` constant (lines 9–34) with:

```python
VALID_TOML = """\
[connection]
host       = "https://sbm.test"
username   = "user"
verify_ssl = false

[defaults]
table_id  = 1000
report_id = 2208

[transitions]
assign    = { id = 155, fields = ["OWNER", "3RD_LEVEL_SPECIALIST"] }
close     = { id = 19,  fields = ["RESOLUTION", "ROOT_CAUSE"], pre_transition_id = 148, pre_transition_optional = true }
return-l2 = { id = 88,  fields = ["RETURN_REASON", "RETURN_NOTE"] }

[transitions.transfer]
id     = 140
fields = ["L3_SPECIALIST_GROUP"]

[transitions.transfer.field_types]
L3_SPECIALIST_GROUP = "list"

[teams]
market-finance = { id = 155, name = "L3 SD Market Finance" }
"""
```

- [ ] **Step 7: Update `tests/test_config.py` — fix `test_load_config_missing_required_field_raises`**

Replace the test body (lines 74–78) with:

```python
def test_load_config_missing_required_field_raises(tmp_path):
    cfg_file = tmp_path / "config.toml"
    cfg_file.write_text("[connection]\nusername = \"user\"\n", encoding="utf-8")
    with pytest.raises(ConfigError, match="host"):
        load_config(cfg_file)
```

- [ ] **Step 8: Update `tests/test_config.py` — fix `test_save_and_reload_roundtrip`**

Replace the full function (lines 81–111) with:

```python
def test_save_and_reload_roundtrip(tmp_path):
    cfg_file = tmp_path / "config.toml"
    original = Config(
        host="https://sbm.example.com",
        username="myuser",
        verify_ssl=True,
        table_id=1000,
        report_id=2208,
        transitions={
            "assign": TransitionConfig(id=155, fields=["OWNER"]),
            "close": TransitionConfig(
                id=19, fields=["RESOLUTION", "ROOT_CAUSE"],
                pre_transition_id=148, pre_transition_optional=True,
            ),
            "transfer": TransitionConfig(
                id=140, fields=["L3_SPECIALIST_GROUP"],
                field_types={"L3_SPECIALIST_GROUP": "list"},
            ),
        },
        teams={"test-team": TeamConfig(id=99, name="Test Team")},
    )
    save_config(original, cfg_file)
    reloaded = load_config(cfg_file)
    assert reloaded.host == original.host
    assert reloaded.verify_ssl == original.verify_ssl
    assert reloaded.transitions["assign"].id == 155
    assert reloaded.transitions["close"].pre_transition_id == 148
    assert reloaded.transitions["close"].pre_transition_optional is True
    assert reloaded.transitions["transfer"].field_types == {"L3_SPECIALIST_GROUP": "list"}
    assert reloaded.teams["test-team"].name == "Test Team"
```

- [ ] **Step 9: Update `tests/test_config.py` — fix `test_save_and_reload_special_chars`**

Replace with (test username special chars only — password no longer in config):

```python
def test_save_and_reload_special_chars(tmp_path):
    cfg_file = tmp_path / "config.toml"
    cfg = Config(
        host="https://sbm.example.com",
        username="domain\\user",
        verify_ssl=True,
        table_id=1000,
        report_id=0,
    )
    save_config(cfg, cfg_file)
    reloaded = load_config(cfg_file)
    assert reloaded.username == "domain\\user"
```

- [ ] **Step 10: Update remaining `Config()` calls in `tests/test_config.py` — remove `password` keyword arg**

The following tests have `Config(..., password="pass", ...)` or `Config(..., password="p", ...)`. Remove the `password=` argument from each:

- `test_save_config_invalid_transition_name_raises` — remove `password="pass",`
- `test_save_config_invalid_field_type_key_raises` — remove `password="pass",`
- `test_pre_transition_optional_without_id_roundtrip` — remove `password="pass",`
- `test_save_config_round_trips_users` — remove `password="p",`
- `test_save_config_round_trips_fields` — remove `password="p",`
- `test_save_config_round_trips_list_fields` — remove `password="p",`
- `test_save_config_empty_list_fields_omits_key` — remove `password="p",`

- [ ] **Step 11: Update inline TOML strings in `tests/test_config.py` — remove `password` lines**

In `test_load_config_parses_users`, `test_load_config_parses_fields`, and `test_load_config_parses_list_fields`, the inline `toml_content`/`toml` strings each contain `password = "p"`. Remove that line from each string.

For example, the `[connection]` block in each should become:
```toml
[connection]
host = "https://sbm.test"
username = "u"
verify_ssl = false
```

- [ ] **Step 12: Update `tests/conftest.py` — remove password from `sample_config` and add autouse fixture**

Replace the entire `conftest.py` content with:

```python
import pytest
from click.testing import CliRunner


@pytest.fixture
def runner():
    return CliRunner()


@pytest.fixture
def sample_config():
    from sbm_cli.config import Config, TransitionConfig, TeamConfig
    return Config(
        host="https://sbm.test",
        username="testuser",
        verify_ssl=False,
        table_id=1000,
        report_id=2208,
        transitions={
            "assign": TransitionConfig(id=155, fields=["OWNER", "3RD_LEVEL_SPECIALIST"]),
            "close": TransitionConfig(
                id=19, fields=["RESOLUTION", "ROOT_CAUSE"],
                pre_transition_id=148, pre_transition_optional=True,
            ),
            "return-l2": TransitionConfig(id=88, fields=["RETURN_REASON", "RETURN_NOTE"]),
            "transfer": TransitionConfig(
                id=140, fields=["L3_SPECIALIST_GROUP"],
                field_types={"L3_SPECIALIST_GROUP": "list"},
            ),
        },
        teams={
            "my-team": TeamConfig(id=155, name="L3 Example Team"),
        },
    )


@pytest.fixture
def mock_session(mocker):
    return mocker.patch("sbm_cli.client.requests.Session")


@pytest.fixture(autouse=True)
def mock_credentials(mocker):
    """Patch keyring calls globally so tests never hit real Windows Credential Manager.
    Tests that need to verify missing credentials can override get_password locally:
        mocker.patch("sbm_cli.credentials.get_password", return_value=None)
    """
    mocker.patch("sbm_cli.credentials.get_password", return_value="testpass")
    mocker.patch("sbm_cli.credentials.set_password")
```

- [ ] **Step 13: Update `tests/test_cli.py` — remove `password` from `_make_app_config`**

Change `_make_app_config()` (lines 15–36) from:

```python
def _make_app_config() -> Config:
    return Config(
        host="https://sbm.test",
        username="user",
        password="pass",
        verify_ssl=False,
        ...
    )
```

To:

```python
def _make_app_config() -> Config:
    return Config(
        host="https://sbm.test",
        username="user",
        verify_ssl=False,
        table_id=1000,
        report_id=2208,
        transitions={
            "assign": TransitionConfig(id=155, fields=["OWNER", "3RD_LEVEL_SPECIALIST"]),
            "close": TransitionConfig(
                id=19, fields=["RESOLUTION", "ROOT_CAUSE"],
                pre_transition_id=148, pre_transition_optional=True,
            ),
            "return-l2": TransitionConfig(id=88, fields=["RETURN_REASON", "RETURN_NOTE"]),
            "transfer": TransitionConfig(
                id=140, fields=["L3_SPECIALIST_GROUP"],
                field_types={"L3_SPECIALIST_GROUP": "list"},
            ),
        },
        teams={"my-team": TeamConfig(id=155, name="L3 Example Team")},
    )
```

- [ ] **Step 14: Run the full test suite**

```bash
pytest tests/ -v --ignore=tests/integration
```

Expected: all tests PASS (including the two new ones from Step 1).

- [ ] **Step 15: Commit**

```bash
git add sbm_cli/config.py tests/test_config.py tests/conftest.py tests/test_cli.py
git commit -m "feat: remove password from Config dataclass and config file — keyring is the sole store"
```

---

### Task 4: Add migration logic to `load_config`

**Files:**
- Modify: `sbm_cli/config.py`
- Modify: `tests/test_config.py`

- [ ] **Step 1: Write failing migration tests**

Add at the end of `tests/test_config.py`:

```python
def test_load_config_migrates_plaintext_password(tmp_path, mocker):
    set_pw = mocker.patch("sbm_cli.credentials.set_password")
    cfg_file = tmp_path / "config.toml"
    cfg_file.write_text("""\
[connection]
host     = "https://sbm.test"
username = "user"
password = "oldpass"
verify_ssl = false

[defaults]
table_id  = 1000
report_id = 0
""", encoding="utf-8")
    config = load_config(cfg_file)
    set_pw.assert_called_once_with("https://sbm.test", "user", "oldpass")
    content = cfg_file.read_text()
    assert "password" not in content
    assert "oldpass" not in content
    assert config.host == "https://sbm.test"


def test_load_config_no_migration_when_no_password(tmp_path, mocker):
    set_pw = mocker.patch("sbm_cli.credentials.set_password")
    path = tmp_path / "config.toml"
    path.write_text(VALID_TOML, encoding="utf-8")
    load_config(path)
    set_pw.assert_not_called()
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
pytest tests/test_config.py::test_load_config_migrates_plaintext_password tests/test_config.py::test_load_config_no_migration_when_no_password -v
```

Expected: `test_load_config_migrates_plaintext_password` FAILS (no migration happens); `test_load_config_no_migration_when_no_password` PASSES.

- [ ] **Step 3: Add `import sys` to `sbm_cli/config.py`**

Change the imports at the top from:

```python
import re
import tomllib
from dataclasses import dataclass, field
from pathlib import Path
```

To:

```python
import re
import sys
import tomllib
from dataclasses import dataclass, field
from pathlib import Path
```

- [ ] **Step 4: Add password detection and migration to `load_config`**

In `load_config`, immediately after the line `conn = data.get("connection", {})`, add:

```python
    raw_password = conn.pop("password", None)  # Detected for migration; not stored in Config
```

Then, after the `Config(...)` constructor call and before `return config`, insert the migration block:

```python
    if raw_password:
        from sbm_cli import credentials
        credentials.set_password(config.host, config.username, raw_password)
        save_config(config, path)
        print("Password migrated to Windows Credential Manager.", file=sys.stderr)

    return config
```

The complete end of `load_config` after this change should look like:

```python
    config = Config(
        host=conn["host"],
        username=conn["username"],
        verify_ssl=conn.get("verify_ssl", True),
        table_id=defaults.get("table_id", 1000),
        report_id=defaults.get("report_id", 0),
        transitions=transitions,
        teams=teams,
        users=users,
        fields=field_defs,
        list_fields=list_fields,
    )

    if raw_password:
        from sbm_cli import credentials
        credentials.set_password(config.host, config.username, raw_password)
        save_config(config, path)
        print("Password migrated to Windows Credential Manager.", file=sys.stderr)

    return config
```

- [ ] **Step 5: Run migration tests**

```bash
pytest tests/test_config.py::test_load_config_migrates_plaintext_password tests/test_config.py::test_load_config_no_migration_when_no_password -v
```

Expected: both PASS.

- [ ] **Step 6: Run full test suite**

```bash
pytest tests/ -v --ignore=tests/integration
```

Expected: all tests PASS.

- [ ] **Step 7: Commit**

```bash
git add sbm_cli/config.py tests/test_config.py
git commit -m "feat: auto-migrate plaintext password from config.toml to Windows Credential Manager"
```

---

### Task 5: Update `cli.py` — keychain retrieval in `AppContext.client` and storage in `configure_setup`

**Files:**
- Modify: `sbm_cli/cli.py`
- Modify: `tests/test_cli.py`

- [ ] **Step 1: Write failing tests**

Add at the end of `tests/test_cli.py`:

```python
def test_missing_credentials_returns_auth_error(runner: CliRunner, mocker):
    mocker.patch("sbm_cli.credentials.get_password", return_value=None)
    with patch("sbm_cli.cli.load_config", return_value=_make_app_config()):
        with patch("sbm_cli.cli.SBMClient"):
            result = runner.invoke(main, ["list"], catch_exceptions=False)
    assert result.exit_code == 2
    data = json.loads(result.stdout)
    assert data["ok"] is False
    assert data["error"]["type"] == "auth_error"
    assert "sbm configure" in data["error"]["message"]


def test_configure_setup_stores_password_in_keyring(runner: CliRunner, mocker):
    set_pw = mocker.patch("sbm_cli.credentials.set_password")
    with patch("sbm_cli.cli.SBMClient") as MockClient:
        MockClient.return_value.check_auth.return_value = None
        result = runner.invoke(
            main,
            ["configure", "setup"],
            input="https://sbm.test\nuser\nsecretpass\n1000\n0\nn\n\n\n",
            catch_exceptions=False,
        )
    assert result.exit_code == 0
    set_pw.assert_called_once_with("https://sbm.test", "user", "secretpass")
```

- [ ] **Step 2: Run failing tests**

```bash
pytest tests/test_cli.py::test_missing_credentials_returns_auth_error tests/test_cli.py::test_configure_setup_stores_password_in_keyring -v
```

Expected: both FAIL — `AppContext.client` still uses `config.password` (removed); `configure_setup` doesn't call `set_password`.

- [ ] **Step 3: Add `credentials` import to `sbm_cli/cli.py`**

At the top of `cli.py`, after the existing local imports, add:

```python
from sbm_cli import credentials
```

The imports section should end with:

```python
from sbm_cli.config import (
    Config, ConfigError, FieldDef, TransitionConfig, UserConfig,
    load_config, save_config, DEFAULT_CONFIG_PATH,
)
from sbm_cli import credentials
from sbm_cli import formatters
```

- [ ] **Step 4: Update `AppContext.client` in `sbm_cli/cli.py`**

Change the `client` property (lines 32–39):

```python
    @property
    def client(self) -> SBMClient:
        if self._client is None:
            self._client = SBMClient(
                host=self.config.host,
                username=self.config.username,
                password=self.config.password,
                verify_ssl=self.config.verify_ssl,
            )
        return self._client
```

To:

```python
    @property
    def client(self) -> SBMClient:
        if self._client is None:
            password = credentials.get_password(self.config.host, self.config.username)
            if password is None:
                raise PermissionError(
                    "No password found in Windows Credential Manager. "
                    "Run 'sbm configure' to set up credentials."
                )
            self._client = SBMClient(
                host=self.config.host,
                username=self.config.username,
                password=password,
                verify_ssl=self.config.verify_ssl,
            )
        return self._client
```

- [ ] **Step 5: Update `configure_setup` — store password to keychain, not config**

Change the `Config(...)` construction and save block in `configure_setup` (lines 148–154):

```python
    config = Config(
        host=host, username=username, password=password,
        verify_ssl=verify_ssl, table_id=table_id, report_id=report_id,
        list_fields=list_fields,
    )
    save_config(config)
    click.echo(f"Config written to {DEFAULT_CONFIG_PATH}", err=True)
```

To:

```python
    config = Config(
        host=host, username=username,
        verify_ssl=verify_ssl, table_id=table_id, report_id=report_id,
        list_fields=list_fields,
    )
    save_config(config)
    credentials.set_password(host, username, password)
    click.echo(f"Config written to {DEFAULT_CONFIG_PATH}", err=True)
```

- [ ] **Step 6: Fix dummy `Config` objects in `cli.py` `main()` group**

There are two occurrences of `Config("", "", "", False, 0, 0)` (lines 84 and 90 — one for `configure` subcommand, one for `--help`). Change both from:

```python
ctx.obj = AppContext(Config("", "", "", False, 0, 0), pretty, quiet, indent)
```

To:

```python
ctx.obj = AppContext(Config("", "", False, 0, 0), pretty, quiet, indent)
```

- [ ] **Step 7: Run new tests**

```bash
pytest tests/test_cli.py::test_missing_credentials_returns_auth_error tests/test_cli.py::test_configure_setup_stores_password_in_keyring -v
```

Expected: both PASS.

- [ ] **Step 8: Run full test suite**

```bash
pytest tests/ -v --ignore=tests/integration
```

Expected: all tests PASS.

- [ ] **Step 9: Commit**

```bash
git add sbm_cli/cli.py tests/test_cli.py
git commit -m "feat: retrieve password from Windows Credential Manager in CLI; store via configure"
```
