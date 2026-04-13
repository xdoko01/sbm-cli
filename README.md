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
sbm configure setup  # interactive setup wizard
sbm schema           # verify config and see available transitions
sbm list             # list open tickets
sbm get 02440942     # get ticket details
```

## Configuration

Config is stored at `~/.sbm-cli/config.toml`. Run `sbm configure setup` to create it interactively.

The password is stored in **Windows Credential Manager** (never in the config file). If you have an
existing config with a plaintext `password` field, it is migrated automatically on the next run.

Use `sbm configure transition <name>` to add or update a named transition interactively.
Manual editing is still needed for teams (transition IDs are instance-specific):

```toml
[connection]
host       = "https://sbm.example.com"
username   = "myuser"
verify_ssl = false          # set true for trusted certs

[defaults]
table_id  = 1000
report_id = 2208
list_fields = ["TITLE","STATE","FUNCTIONALITY","URGENCY"]  # optional; blank uses built-in default

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
| `sbm configure setup` | Interactive setup wizard |
| `sbm configure transition <name>` | Add/update a named transition interactively |
| `sbm schema` | Machine-readable capabilities JSON |
| `sbm list [--report N] [--filter N]` | List tickets |
| `sbm get <ticket-id>` | Get ticket by display ID |
| `sbm fields <ticket-id> [--fields F1,F2]` | List field definitions (dbnames, types, labels) |
| `sbm transition <name> <ticket-id> --field K=V` | Run named transition |
| `sbm transition run <ticket-id> --id N --field K=V` | Run raw transition by ID |
| `sbm field-values <field> --table <table-id>` | Discover valid relational field values |
| `sbm teams` | List configured teams |

## Global flags

```
--pretty / -H   Human-readable output (rich tables)
--config PATH   Override config file location
--quiet         Suppress stderr status messages
--indent        Output formatted JSON with indentation
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
git clone https://github.com/xdoko01/sbm-cli
cd sbm-cli
uv sync
uv run sbm configure
uv run pytest
uv run pytest -m integration  # requires live SBM connection
```

## License

MIT
