# sbm-cli — Claude Code Integration Guide

`sbm-cli` is a CLI tool for the SBM 12.0 JSON API. Use it via Bash tool calls.
All commands output JSON by default. Use `--pretty` for human-readable output.

## Setup check

```bash
sbm schema
```

Run this first. It returns the configured host, default table/report IDs, available
named transitions, and configured teams. If it fails with a config_error, run
`sbm configure` to create the config file.

## Workflow for transitions

Always call `sbm schema` first to discover configured transitions and their required fields.
Before any transition that uses a relational field (e.g. RETURN_REASON, ROOT_CAUSE),
call `sbm field-values` to get valid IDs:

```bash
# Discover valid RETURN_REASON values (find table ID from sbm get output)
sbm field-values RETURN_REASON --table 1080
# Returns: {"ok": true, "data": {"values": [{"id": 3, "name": "Missing info"}, ...]}}
```

**Never guess relational field IDs.**

## Commands reference

```bash
sbm schema                               # capabilities, transitions, teams
sbm list                                 # tickets from default report
sbm list --report 2208                   # specific report
sbm list --filter 36                     # by filter ID
sbm get 02440942                         # ticket detail by display ID
sbm field-values FIELD --table TABLE_ID  # valid values for a relational field
sbm teams                                # configured team slugs and IDs

sbm transition assign 02440942 --field OWNER=316 --field 3RD_LEVEL_SPECIALIST=316
sbm transition close 02440942 --field RESOLUTION="Fixed" --field ROOT_CAUSE=1701
sbm transition return-l2 02440942 --field RETURN_REASON=3 --field RETURN_NOTE="Missing logs"
sbm transition transfer 02440942 --field L3_SPECIALIST_GROUP=155

sbm transition run 02440942 --id 155 --field OWNER=316  # raw transition by ID
```

## Output format

All commands (except `--pretty`) return:
```json
{"ok": true/false, "command": "...", "data": {...}}
```
or on error:
```json
{"ok": false, "command": "...", "error": {"type": "...", "message": "..."}}
```

Exit codes: 0=success, 1=API error, 2=config/auth error, 3=validation error.

## Known quirks (handled automatically by the CLI)

- `verify_ssl = false` is required for internal self-signed certificates
- Username must be bare (e.g. `otakar`, not `DOMAIN\otakar`)
- `pagesize` for filter queries must be a URL param — the CLI handles this
- `assign` and `transfer` transitions require a `startTransition` lock — the CLI handles this
- `close` is a two-step transition (Start Solving → Resolved) — handled automatically
- `L3_SPECIALIST_GROUP` must be sent as a JSON array — declared as `"list"` in config

## ROOT_CAUSE common values

Use `sbm field-values ROOT_CAUSE --table <TABLE_ID>` to get the full list.
Common values: 1673=Software bug, 2387=Configuration issue, 1700=User side issue, 1701=Other cause.
