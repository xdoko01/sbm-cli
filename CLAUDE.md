# sbm-cli — Claude Code Integration Guide

`sbm-cli` is a CLI tool for the SBM 12.0 JSON API. Use it via Bash tool calls.
All commands output JSON by default. Use `--pretty` (global flag) for human-readable output.
`--pretty` must come **before** the subcommand: `sbm --pretty list`, NOT `sbm list --pretty`.

## Setup check

```bash
sbm schema
```

Run this first. It returns the configured host, default table/report IDs, available
named transitions, and configured teams. If it fails with a config_error, run
`sbm configure` to create the config file.

`sbm schema` reads only the local config — it makes no API call. To confirm the
credentials actually work, run `sbm auth check`.

## Headless / non-interactive use

On a machine with no keyring and no terminal (CI runner, container, cloud VM),
two environment variables replace the interactive paths:

| Variable | Meaning |
|---|---|
| `SBM_CLI_PASSWORD` | Password, checked before the keyring. Used verbatim (whitespace included). Never written to disk. |
| `SBM_CLI_CONFIG` | Path to the config file. `--config` overrides it; default is `~/.sbm-cli/config.toml`. |

Bootstrap a fresh machine by exporting the config from one that already works —
`configure setup` is interactive and cannot produce transitions non-interactively:

```bash
# on the working machine
sbm configure export > sbm-config.toml

# on the headless machine
export SBM_CLI_PASSWORD='...'
sbm configure import sbm-config.toml   # add --force to overwrite an existing config
sbm auth check                         # smoke test; exit 0 = authenticated
```

Check the counts `configure import` reports: `"transitions": 0` means `sbm list`
and `sbm get` will work but every `sbm transition` will fail.

When stdin is not a terminal, `sbm` does **not** prompt for a password — it exits
2 with `auth_error` naming `SBM_CLI_PASSWORD`. Do not try to pipe a password into
stdin; set the variable instead.

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

## Optional fields on transitions

`SOLUTION_STEPS` is a free-text journal field available on all transitions. In the SBM web UI it appears as "Add your comment:" on the transition form and "Solution steps:" on the ticket view.

- **Type:** journal (each transition appends a new entry — previous entries are preserved)
- **Required on:** `return-l2` (already in `fields` list)
- **Optional on:** all other named transitions (`assign`, `close`, `transfer`, `start-solving`, `email-initiator`)
- **AI instruction:** Before executing any transition, ask the user if they want to add a comment. If yes, include `--field SOLUTION_STEPS="<comment>"`.

Run `sbm schema` to see which transitions have `optional_fields` configured.

## Commands reference

```bash
sbm schema                               # capabilities, transitions, teams
sbm list                                 # tickets from all configured reports (merged, de-duplicated)
sbm --pretty list                        # human-readable table output
sbm list --report 2208                   # specific report (overrides config)
sbm list --report 2208 --report 2209     # several reports (repeatable; overrides config)
sbm list --filter 36                     # by filter ID
sbm get 02440942                         # ticket detail by display ID
sbm --pretty get 02440942               # human-readable ticket detail
sbm field-values FIELD --table TABLE_ID  # valid values for a relational field
sbm teams                                # configured team slugs and IDs
sbm configure setup                      # full interactive setup wizard
sbm configure transition assign          # add/update a named transition interactively
sbm auth check                           # verify credentials (reports password source)
sbm configure export > sbm-config.toml   # dump config as TOML (never includes a password)
sbm configure import sbm-config.toml     # install a config (--force to overwrite)
sbm fields 02440942                      # list all field dbnames, types, labels
sbm fields 02440942 --fields FUNCTIONALITY,APPLICATION1,COUNTRY_IM,ROOT_CAUSE  # probe specific fields

sbm transition assign 02440942 --field OWNER=316 --field 3RD_LEVEL_SPECIALIST=316
sbm transition assign 02440942 --field OWNER=316 --field 3RD_LEVEL_SPECIALIST=316 --field SOLUTION_STEPS="Taking ownership, will investigate."
sbm transition close 02440942 --field RESOLUTION="Fixed" --field ROOT_CAUSE=1701
sbm transition close 02440942 --field RESOLUTION="Fixed" --field ROOT_CAUSE=1701 --field SOLUTION_STEPS="Root cause identified and resolved."
sbm transition return-l2 02440942 --field RETURN_REASON=3 --field RETURN_NOTE="Missing logs" --field SOLUTION_STEPS="Returning to L2 — missing diagnostic logs."
sbm transition transfer 02440942 --field L3_SPECIALIST_GROUP=155

sbm transition run 02440942 --id 155 --field OWNER=316  # raw transition by ID
```

## Default list fields

Set once in `~/.sbm-cli/config.toml` under `[defaults]`:

```toml
[defaults]
list_fields = ["TITLE","STATE","OWNER","FUNCTIONALITY","URGENCY","COUNTRY_IM","ROOT_CAUSE"]
```

Or set during the wizard: `sbm configure setup` prompts for this.
When absent or empty, the built-in default `TITLE,STATE,OWNER,SECONDARYOWNER,URGENCY,SEVERITY` is used.
`--fields` always overrides this for a single invocation.

## Default reports

`defaults.report_ids` is a **list** of report IDs:

```toml
[defaults]
report_ids = [2208, 2209]
```

`sbm list` (with no `--report`) queries every configured report, merges the
results, and drops duplicate tickets. If one report fails it is skipped with a
warning on stderr; `sbm list` errors only when every report fails. `--report`
is repeatable and overrides `report_ids` for that run
(`sbm list --report 2208 --report 2209`). A legacy singular `report_id = 2208`
is still read (as `[2208]`) and migrated to `report_ids` on the next save.

## Output format

All commands (except when `--pretty` is used) return:
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
- Username must be bare (e.g. `alice`, not `DOMAIN\alice`)
- `pagesize` for filter queries must be a URL param — the CLI handles this
- `assign` and `transfer` transitions require a `startTransition` lock — the CLI handles this
- `close` is a two-step transition (Start Solving → Resolved) — handled automatically
- `L3_SPECIALIST_GROUP` must be sent as a JSON array — declared as `"list"` in config

## Field value structure (SBM API quirk)

Relational fields are returned in two forms depending on the endpoint:

| Endpoint | Structure |
|----------|-----------|
| `getitemsbyitemid` / `GetItem` | `{"value": {"id": 3, "name": "High"}, "displayName": "..."}` |
| `getitemsbylistingreport` / `getitemsbyreportfilter` | `{"id": 3, "name": "3 - Medium"}` |

Both forms are handled transparently by `_field_val` (formatters) and `_classify_field` (client).
When debugging blank `--pretty` columns, check which form the endpoint returns.

## ROOT_CAUSE common values

Use `sbm field-values ROOT_CAUSE --table <TABLE_ID>` to get the full list.
Common values: 1673=Software bug, 2387=Configuration issue, 1700=User side issue, 1701=Other cause.

## Maintaining the bundled skill (`skills/sbm-cli/`)

The repo ships an `sbm-cli` skill that teaches users' AI assistants to install and operate the
CLI. It is plain Markdown usable by any assistant (copy the folder); `.claude-plugin/` adds a
Claude Code install path on top. Keep `SKILL.md` assistant-neutral — no Claude-only tools or syntax. It must change in the **same commit** as the code it
describes. `tests/test_skill.py` enforces this — `uv run pytest` fails on drift.

| File | How it is maintained |
|---|---|
| `skills/sbm-cli/references/commands.md` | **Generated** — never edit. Run `uv run python scripts/gen_skill_reference.py` after changing any command, option, argument or docstring in `sbm_cli/cli.py` |
| `skills/sbm-cli/SKILL.md` | Hand-written. Update when install steps, setup/auth flow, env vars, global flags, error types, exit codes, output shape or a user-visible quirk changes. Every command path, global flag, env var and error type must be mentioned |
| `skills/sbm-cli/references/config.md` | Hand-written. Update when a config key is added, renamed or changes meaning (`sbm_cli/config.py`) |
| `.claude-plugin/plugin.json` | `version` must equal `pyproject.toml` — bump both together on release |
| `docs/manual.md` §1.1, README "AI assistant skill" | User-facing install/usage guide for the plugin. Update when install/update commands, the plugin or marketplace name, or what the skill does changes |

Any change to `sbm_cli/` (or to install/upgrade instructions in README or the manual): before
committing, review the three skill files above against the change, regenerate the reference,
and run `uv run pytest tests/test_skill.py`. The test checks coverage, not accuracy — a changed
behavior with an unchanged command name still needs a manual edit to SKILL.md.
