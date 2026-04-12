# sbm-cli Design Spec
**Date:** 2026-04-08  
**Status:** Approved

---

## Overview

`sbm-cli` is a generic, publicly releasable command-line client for the SBM (Serena Business Manager) 12.0 JSON API. It is designed for day-to-day L3 support work and for use by AI tools (Claude Code) as a drop-in alternative to an MCP server.

**Goals:**
- Cover the five core L3 support operations: list tickets, get ticket details, assign, close, return to L2, transfer between L3 groups
- All IDs and transition mappings are configurable — no hardcoded instance-specific values
- JSON output by default (AI-friendly), human-readable on request (`--pretty`)
- Installable via `uv tool install sbm-cli` or `pip install sbm-cli`
- Suitable for public release on GitHub/PyPI

**Non-goals:**
- Ticket creation (blocked by FUNCTIONALITY field issue; out of scope for v1)
- User management via SOAP (requires "View Users" privilege not available to default user)
- Web UI or interactive TUI

---

## Repository Structure

```
sbm-cli/
├── sbm_cli/
│   ├── __init__.py
│   ├── client.py       # SBMClient — HTTP layer (JSON API + SOAP basics)
│   ├── config.py       # Load/save ~/.sbm-cli/config.toml, sbm configure wizard
│   ├── formatters.py   # Transform API response dicts → human-readable rich output
│   └── cli.py          # Click entry point, all commands
├── tests/
│   ├── __init__.py
│   ├── conftest.py
│   ├── test_cli.py
│   ├── test_config.py
│   ├── test_formatters.py
│   └── integration/
│       ├── __init__.py
│       └── test_live.py    # marked @pytest.mark.integration, skipped by default
├── CLAUDE.md               # AI integration guide (read automatically by Claude Code)
├── README.md
├── pyproject.toml
└── .gitignore
```

**Module responsibilities:**
- `client.py` — all HTTP concerns; no business logic
- `config.py` — all config file I/O and validation; no HTTP
- `formatters.py` — all presentation logic; no HTTP or config reads
- `cli.py` — wires the above together; minimal logic of its own

---

## Configuration

**File location:** `~/.sbm-cli/config.toml`

```toml
[connection]
host       = "https://sbm.example.com"
username   = "myuser"           # bare username, no domain prefix
password   = "secret"           # plaintext; keyring support is a future improvement
verify_ssl = false              # set true when using a trusted certificate

[defaults]
table_id  = 1000                # default table for get/update operations
report_id = 2208                # default report for `sbm list`

[transitions]
assign    = { id = 155, fields = ["OWNER", "3RD_LEVEL_SPECIALIST"] }
close     = { id = 19,  fields = ["RESOLUTION"] }
return-l2 = { id = 88,  fields = ["RETURN_REASON", "RETURN_NOTE"] }
transfer  = { id = 140, fields = ["L3_SPECIALIST_GROUP"] }

# Field type hints — fields that must be sent as JSON arrays
[transitions.transfer.field_types]
L3_SPECIALIST_GROUP = "list"

[teams]
# Slug → numeric L3_SPECIALIST_GROUP ID mapping for human-friendly --field values
# market-finance = { id = 155, name = "L3 SD Market Finance" }
# market-ops     = { id = 123, name = "L3 SD Market Operations" }
```

**`sbm configure` wizard:**
Interactive prompts for all `[connection]` and `[defaults]` values. Tests the connection after writing. The `[transitions]` and `[teams]` sections require manual editing (transition IDs are instance-specific and must be captured from browser dev tools or SBM admin).

**Config loading rules:**
1. Default path: `~/.sbm-cli/config.toml`
2. Override with `--config PATH` global flag
3. `config.py` raises a clear error with setup instructions if file is missing

---

## Commands

### Global flags
```
--pretty / -H   Human-readable output (rich tables/panels instead of JSON)
--config PATH   Override config file location
--quiet         Suppress stderr status messages (for use in scripts)
```

### Setup
```bash
sbm configure            # interactive wizard, writes ~/.sbm-cli/config.toml
sbm schema               # print machine-readable capabilities JSON (see below)
sbm teams                # list configured teams from [teams] config section
```

### Read operations
```bash
sbm list                               # list tickets from default report
sbm list --report 2208                 # specific report ID
sbm list --filter 36                   # or by filter ID
sbm list --fields TITLE,STATE,OWNER    # limit returned fields
                                       # default fields: TITLE, STATE, OWNER, SECONDARYOWNER, URGENCY, SEVERITY

sbm get <ticket-id>                    # get ticket by display ID (e.g. 02440942)
sbm get <ticket-id> --fields TITLE,DESCRIPTION,STATE,OWNER
                                       # default fields: all fields returned by API (no filter applied)
```

### Transitions (named)
```bash
sbm transition assign   <ticket-id> --field OWNER=316 --field 3RD_LEVEL_SPECIALIST=316
sbm transition close    <ticket-id> --field RESOLUTION="Fixed by restarting the service"
sbm transition return-l2 <ticket-id> --field RETURN_REASON=3 --field RETURN_NOTE="Missing logs"
sbm transition transfer  <ticket-id> --field L3_SPECIALIST_GROUP=155
sbm transition transfer  <ticket-id> --field L3_SPECIALIST_GROUP=155 --field OWNER=316
```

### Transitions (raw)
```bash
sbm transition run <ticket-id> --id 155 --field OWNER=316   # arbitrary transition by ID
```

### Discovery
```bash
sbm field-values <field-dbname> --table <table-id>   # list items from a relational field's table
sbm field-values RETURN_REASON --table 1080           # → [{id, name}, ...]
```
The `--table` ID is found in the `relTableId` property of the field in `sbm get` output. This is a deliberate lookup, not automatic — users discover field table IDs once and then use them consistently.

### `sbm schema` output
```json
{
  "connection": { "host": "https://...", "table_id": 1000 },
  "defaults": { "report_id": 2208 },
  "transitions": {
    "assign":     { "id": 155, "required_fields": ["OWNER", "3RD_LEVEL_SPECIALIST"] },
    "close":      { "id": 19,  "required_fields": ["RESOLUTION"] },
    "return-l2":  { "id": 88,  "required_fields": ["RETURN_REASON", "RETURN_NOTE"] },
    "transfer":   { "id": 140, "required_fields": ["L3_SPECIALIST_GROUP"], "field_types": { "L3_SPECIALIST_GROUP": "list" } }
  },
  "teams": {
    "market-finance": { "id": 155, "name": "L3 SD Market Finance" }
  }
}
```

---

## Error Handling & Output Format

### JSON envelope (all commands, stdout)
**Success:**
```json
{ "ok": true,  "command": "get",        "data": { ... } }
```
**Error:**
```json
{ "ok": false, "command": "transition", "error": { "type": "api_error", "message": "...", "field": "RETURN_REASON" } }
```

### Error types
| type | meaning |
|------|---------|
| `validation_error` | Missing required fields — caught *before* API call |
| `api_error` | SBM API returned `result.type == "ERROR"` |
| `auth_error` | HTTP 401 — bad credentials or session expired |
| `config_error` | Config file missing, unreadable, or incomplete |
| `network_error` | Connection timeout or SSL error |

### Exit codes
| code | meaning |
|------|---------|
| 0 | Success |
| 1 | API error |
| 2 | Config/auth error |
| 3 | Validation error (missing required field) |

### Stdout vs stderr
- All JSON/formatted data → **stdout**
- Progress/status messages (e.g. "Authenticating...") → **stderr**

This keeps stdout clean for piping and script use.

---

## Testing Strategy

**Unit tests** (`tests/test_*.py`):
- Mock `requests.Session` — no network access required
- Cover: CLI argument parsing, config loading/validation, field validation, output formatting, exit codes
- Run anywhere: `uv run pytest` or `pytest`

**Integration tests** (`tests/integration/`):
- Require real credentials in `.env` or environment variables
- Skipped by default: `pytest -m "not integration"`
- Run explicitly: `pytest -m integration`
- Test actual API calls against the live SBM instance

---

## AI Integration

### `CLAUDE.md` (repo root)
Claude Code reads this file automatically. It will contain:

1. **Install & configure** — `uv tool install sbm-cli`, then `sbm configure`
2. **Orientation workflow** — always run `sbm schema` first to discover transitions and defaults
3. **Relational field workflow** — run `sbm field-values <FIELD>` before any transition that requires a relational field value; never guess IDs
4. **Known API quirks:**
   - `verify_ssl = false` required for self-signed certs
   - Username must be bare (no domain prefix)
   - `L3_SPECIALIST_GROUP` must be sent as a JSON array — the CLI handles this automatically when declared as `"list"` type in config
   - `pagesize` on filter endpoint is a URL param, not a body param — the CLI handles this
   - Assign transition (155) requires a proper `startTransition` lock — the CLI handles this automatically
5. **Example sequences** for each named transition

### Usage pattern for Claude Code
```bash
sbm schema                                          # orient: what transitions are configured?
sbm list --fields TITLE,STATE,OWNER                 # survey open tickets
sbm get 02440942                                    # inspect a specific ticket
sbm field-values RETURN_REASON                     # discover valid reason IDs
sbm transition return-l2 02440942 \
  --field RETURN_REASON=3 \
  --field RETURN_NOTE="Missing application logs"   # execute transition
```

---

## API Quirks Reference

Inherited from PoC (`sbm-api`) — these are handled internally by `client.py`:

| Quirk | Handling |
|-------|----------|
| HTTP Basic auth, not SSO | `requests.Session.auth = (username, password)` |
| Self-signed cert | `session.verify = False` (configurable) |
| Bare username required | Documented in `sbm configure` prompt and `CLAUDE.md` |
| `pagesize` on filter endpoint is URL param, not body | `client.py` always passes as `params=` |
| Assign/transfer require `startTransition` lock | `client.py` calls `start_transition()` before `update_item()` for these transitions |
| `L3_SPECIALIST_GROUP` must be a list | CLI wraps value in `[...]` when `field_types` declares `"list"` |
| Relational fields sent as plain integers | `--field KEY=123` parsed as int; string values stay as string |

---

## Packaging

**`pyproject.toml`** defines:
- Package name: `sbm-cli`
- Entry point: `sbm = sbm_cli.cli:main`
- Dependencies: `click`, `requests`, `rich`, `tomli` (Python < 3.11 fallback for `tomllib`)
- Optional dev dependencies: `pytest`, `pytest-mock`

**Install:**
```bash
uv tool install sbm-cli     # recommended — isolated environment
pip install sbm-cli         # also supported
```

**Development:**
```bash
git clone https://github.com/<user>/sbm-cli
cd sbm-cli
uv sync
uv run sbm configure
uv run pytest
```
