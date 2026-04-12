# sbm-cli

A generic command-line client for the SBM (Serena Business Manager) 12.0 JSON API.

Designed for day-to-day L3 support work and for use as a tool by AI assistants (Claude Code).

## Install

```bash
# Recommended — isolated environment
uv tool install sbm-cli

# Also works
pip install sbm-cli
```

## Quick start

```bash
sbm configure        # interactive setup wizard
sbm schema           # verify config and see available transitions
sbm list             # list open tickets
sbm get 02440942     # get ticket details
```

## Configuration

Config is stored at `~/.sbm-cli/config.toml`. Run `sbm configure` to create it interactively.

Manual editing is needed for transitions and teams (transition IDs are instance-specific):

```toml
[connection]
host       = "https://sbm.example.com"
username   = "myuser"
password   = "mypass"
verify_ssl = false          # set true for trusted certs

[defaults]
table_id  = 1000
report_id = 2208

[transitions]
assign    = { id = 155, fields = ["OWNER", "3RD_LEVEL_SPECIALIST"] }
close     = { id = 19,  fields = ["RESOLUTION", "ROOT_CAUSE"], pre_transition_id = 148, pre_transition_optional = true }
return-l2 = { id = 88,  fields = ["RETURN_REASON", "RETURN_NOTE"] }
transfer  = { id = 140, fields = ["L3_SPECIALIST_GROUP"] }

[transitions.transfer.field_types]
L3_SPECIALIST_GROUP = "list"

[teams]
my-team = { id = 155, name = "L3 My Team" }
```

> **Transition IDs** are instance-specific. Find them by inspecting browser developer tools
> while performing actions in the SBM web UI, or ask your SBM admin.

## Commands

| Command | Description |
|---------|-------------|
| `sbm configure` | Interactive setup wizard |
| `sbm schema` | Machine-readable capabilities JSON |
| `sbm list [--report N] [--filter N]` | List tickets |
| `sbm get <ticket-id>` | Get ticket by display ID |
| `sbm transition <name> <ticket-id> --field K=V` | Run named transition |
| `sbm transition run <ticket-id> --id N --field K=V` | Run raw transition by ID |
| `sbm field-values <field> --table <table-id>` | Discover valid relational field values |
| `sbm teams` | List configured teams |

## Global flags

```
--pretty / -H   Human-readable output (rich tables)
--config PATH   Override config file location
--quiet         Suppress stderr status messages
```

## Output format

All commands output a JSON envelope:
```json
{"ok": true, "command": "get", "data": {...}}
{"ok": false, "command": "transition", "error": {"type": "api_error", "message": "..."}}
```

Exit codes: `0` success · `1` API error · `2` config/auth error · `3` validation error

## Development

```bash
git clone https://github.com/<your-username>/sbm-cli
cd sbm-cli
uv sync
uv run sbm configure
uv run pytest
uv run pytest -m integration  # requires live SBM connection
```

## Planned features

- **`[users]` config section** — map login names / display names to numeric user IDs so
  transitions accept `--field OWNER=jaroslav.burget` instead of `--field OWNER=15399`
- **Dynamic columns in `--pretty list`** — derive table columns from whatever fields
  were requested instead of hardcoded TITLE/STATE/OWNER/TEAM columns
- **`sbm fields` command** — list all available field definitions for a table (dbnames,
  types, labels) by querying the SBM API
- **`--indent` flag** — output formatted JSON with indentation instead of a compact
  single line, for human readability
- **Field discovery in `sbm configure`** — prompt for a sample ticket ID during setup,
  fetch all its fields, store the schema in `~/.sbm-cli/config.toml` under `[fields]`,
  and expose via `sbm schema` so AI assistants can discover available fields without
  querying live tickets

## License

MIT
