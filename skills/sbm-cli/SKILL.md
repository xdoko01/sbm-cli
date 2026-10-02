---
name: sbm-cli
description: Use when installing, configuring, upgrading, troubleshooting or operating the sbm-cli command-line client for the SBM (Serena Business Manager) 12.0 JSON API — setting up `sbm` on a new machine, connecting it to an SBM host, storing the password, moving a config to a headless/CI machine, defining transitions, or running `sbm list`, `sbm get`, `sbm transition` and the other `sbm` commands to read and update SBM tickets.
---

# sbm-cli — install and operate

`sbm` is a CLI for the SBM 12.0 JSON API. Every command prints a JSON envelope on
stdout, so drive it through the shell and parse the output:

```json
{"ok": true,  "command": "get", "data": {...}}
{"ok": false, "command": "transition", "error": {"type": "api_error", "message": "...", "field": "..."}}
```

Exit codes: `0` success · `1` API error · `2` config/auth error · `3` validation error.

Full `--help` text of every command: [references/commands.md](references/commands.md)
(generated from the code). Config file format: [references/config.md](references/config.md).

## Step 0 — find out where the user stands

Run these in order and stop at the first that fails; it tells you which section to go to.

| Check | Fails with | Go to |
|---|---|---|
| `sbm --version` | command not found | [Install](#install) |
| `sbm schema` | `config_error` (exit 2) | [Configure](#configure) |
| `sbm auth check` | `auth_error` (exit 2) / `api_error` (exit 1) | [Troubleshooting](#troubleshooting) |

`sbm schema` reads only the local config — it makes no network call. `sbm auth check` is the
real smoke test: one call to the host, and it reports `password_source`
(`env:SBM_CLI_PASSWORD`, `keyring` or `prompt`) — never the password.

If `sbm --version` is older than the version named at the top of
[references/commands.md](references/commands.md), recommend an [upgrade](#upgrade-and-uninstall)
before relying on a newer feature.

## Install

Requires Python 3.11+. Prefer uv (isolated environment, `sbm` on PATH):

```bash
uv tool install sbm-cli        # recommended
pip install sbm-cli            # alternative
pip install sbm_cli-<version>-py3-none-any.whl   # offline, from a wheel file
sbm --version                  # verify
```

No uv? Install it first: `pip install uv`, or see https://docs.astral.sh/uv/getting-started/installation/.

**`sbm: command not found` after installing** — the tool directory is not on PATH:

1. Run `uv tool update-shell`, then have the user open a **new** terminal.
2. Still missing: add `~/.local/bin` (macOS/Linux, in `~/.zshrc` or `~/.bashrc`) or
   `%USERPROFILE%\.local\bin` (Windows, User `Path` variable) to PATH.
3. Installed with pip on Windows: the scripts dir is printed by `python -m site --user-scripts`.

## Configure

The config lives at `~/.sbm-cli/config.toml`. Location precedence:
`--config PATH` > `SBM_CLI_CONFIG` env var > `~/.sbm-cli/config.toml`.
The password is **never** in the config — it comes from `SBM_CLI_PASSWORD`, then the
system keyring, then an interactive prompt (only when stdin is a terminal).

### Interactive machine (a person at a desktop)

`sbm configure setup` is an interactive wizard with a hidden password prompt. **You cannot
answer its prompts through a tool call** — ask the user to run it in their own terminal window.
Never ask the user to paste their password into the chat.

Tell them what the wizard asks so they can gather it first:

| Prompt | Notes |
|---|---|
| SBM host | Full URL with `https://`, no trailing slash |
| Username | Bare login (`alice`, not `DOMAIN\alice`) |
| Password | Hidden; stored in the OS keyring (Windows Credential Manager, macOS Keychain, Secret Service) |
| Default table ID | The SBM table the tickets live in — ask the SBM admin |
| Default report IDs | Comma-separated saved-report IDs that `sbm list` queries |
| Verify SSL | Answer `n` for an internal host with a self-signed certificate |
| Default list fields | Comma-separated dbnames; blank = `TITLE,STATE,OWNER,SECONDARYOWNER,URGENCY,SEVERITY` |
| Sample ticket ID | Optional; used to discover and cache field definitions |

The wizard tests the connection at the end. Afterwards run `sbm auth check` and `sbm schema`
yourself to confirm.

### Headless machine (CI runner, container, cloud VM, AI agent sandbox)

No keyring and no terminal. Do not try to pipe a password into stdin — on non-TTY stdin
`sbm` exits 2 with `auth_error` naming `SBM_CLI_PASSWORD` instead of prompting. Use env vars
and copy the config from a machine where it already works:

```bash
# on the working machine
sbm configure export > sbm-config.toml       # raw TOML, never contains a password

# on the headless machine
export SBM_CLI_PASSWORD='...'                 # used verbatim, whitespace included; never written to disk
export SBM_CLI_CONFIG=/path/to/config.toml    # optional; default ~/.sbm-cli/config.toml
sbm configure import sbm-config.toml          # or '-' for stdin; --force to overwrite
sbm auth check                                # exit 0 = authenticated
```

`configure import` validates before installing (a bad file never touches the existing config),
strips any plaintext `password =` line, tolerates a UTF-8 BOM, and reports counts. Check them:
`"transitions": 0` means `sbm list` / `sbm get` work but every `sbm transition` fails.

### Transitions, teams and users

Transition IDs are specific to each SBM instance — find them in the browser dev tools while
performing the action in the SBM web UI, or ask the SBM admin. Never invent one.

- `sbm configure transition <name>` — interactive (ID, required fields, list-typed fields,
  pre-transition). Again the user must run it in their own terminal.
- `optional_fields`, `[teams]` and `[users]` have no wizard: edit the TOML directly. The layout
  is in [references/config.md](references/config.md).
- Re-check with `sbm schema` after any change.

## Operate

### Ground rules

- **Global flags go before the subcommand:** `sbm --pretty list`, never `sbm list --pretty`.
  Globals: `--pretty`/`-H` (rich tables), `--indent` (indented JSON), `--quiet` (no stderr
  status lines), `--config PATH`, `--version`. Use JSON (no `--pretty`) when you parse output.
- **`sbm schema` first** before any transition: it lists configured transitions with their
  `required_fields`, `optional_fields`, `field_types` and `pre_transition_id`, plus teams.
- **Never guess relational field IDs** (OWNER, ROOT_CAUSE, RETURN_REASON, ...). Look them up:
  find the field's `relTableId` in `sbm get <ticket>` output, then
  `sbm field-values <FIELD> --table <relTableId>`. User IDs may also be in `[users]` of the config,
  where a login can be passed instead of the number (`--field OWNER=alice`).
- **Confirm before writing.** A transition changes a live ticket. Show the user the exact
  command and field values and wait for an explicit yes. Before running it, ask whether they
  want to add a comment; if so pass it as `--field SOLUTION_STEPS="..."` where the transition
  allows it (see `optional_fields` in `sbm schema`).
- **Link ticket IDs** you report back using the `id.url` value from the API response.

### Reading tickets

```bash
sbm list                                   # all configured reports, merged and de-duplicated
sbm list --report 2208 --report 2209       # specific reports (repeatable; overrides config)
sbm list --filter 36                       # by filter ID or name
sbm list --fields TITLE,STATE,OWNER        # choose columns (overrides defaults.list_fields)
sbm get 02440942                           # one ticket by display ID, all fields
sbm get 02440942 --fields TITLE,STATE      # selected fields only
sbm fields 02440942                        # dbnames, inferred types and labels of a ticket's fields
sbm fields 02440942 --fields ROOT_CAUSE    # probe fields that are null on that ticket
sbm teams                                  # configured team slugs and IDs
```

`sbm list` over several reports is best-effort: a failing report is skipped with
`Warning: report <id> failed: ...` on **stderr** and `ok` stays `true`. It errors only when every
report fails. When the full set matters, check stderr and treat a warning as a partial result.

Field values come in two shapes depending on the endpoint — handle both:
`get` → `{"value": {"id": 3, "name": "High"}, ...}`; `list` → `{"id": 3, "name": "3 - Medium"}`.
Text fields are `{"value": "..."}`; an `id` of `0` means unset.

### Changing tickets

```bash
sbm schema                                                          # what transitions exist
sbm transition <name> <ticket> --field KEY=VALUE [--field ...]      # named, from config
sbm transition run <ticket> --id <transition-id> --field KEY=VALUE  # raw, by ID
```

- Missing a `required_fields` entry → `validation_error`, exit 3, nothing is sent.
- A field the transition does not declare → stderr warning, but it is still sent.
- `--field` values that look like integers are sent as integers.
- Fields declared `"list"` in `field_types` are wrapped in a JSON array automatically.
- A `pre_transition_id` (e.g. Start Solving before Resolved) runs automatically first.
- Record locks are taken and broken by the CLI; you never manage them.

**Multi-line text** (SOLUTION_STEPS, RESOLUTION, RETURN_NOTE, ...): a `\n` typed in a shell string
reaches SBM as a literal backslash-n. Pass the value as one argument from Python instead:

```python
import json, subprocess
text = """Root cause
----------
Line one.
Line two."""
r = subprocess.run(["sbm", "transition", "close", "02440942",
                    "--field", "RESOLUTION=Fixed", "--field", f"SOLUTION_STEPS={text}"],
                   capture_output=True, text=True)
print(json.loads(r.stdout)["ok"])
```

## Troubleshooting

Read `error.type` and the exit code; `error.field` names the offending field when SBM reports one.

| Symptom | Cause | Fix |
|---|---|---|
| `config_error`, exit 2, on any command | No config / invalid TOML / missing keys | `sbm configure setup`, or `sbm configure import` on headless; check `--config` / `SBM_CLI_CONFIG` |
| `config_error` "Unknown transition" | Name not in `[transitions]` | `sbm schema` for valid names; add with `sbm configure transition <name>` |
| `config_error` "No reports configured" | `defaults.report_ids` empty | Pass `--report N` or set `report_ids` in the config |
| `auth_error` "No password available" | Non-interactive shell, no keyring entry, no env var | Set `SBM_CLI_PASSWORD`, or have the user run `sbm configure setup` in a real terminal |
| `auth_error` on a valid-looking login | Wrong or changed password, or `DOMAIN\` prefix in username | Use a bare username. Changed password: see [Password changed](#password-changed) |
| `api_error` "Could not reach ..." | Host URL, VPN or network | Check `connection.host`; is the user on the corporate network/VPN? |
| SSL / certificate errors | Self-signed internal certificate | Set `verify_ssl = false` under `[connection]` |
| `validation_error`, exit 3 | Missing required `--field`, malformed `KEY=VALUE`, `run` without `--id`, or invalid imported config | Fix the arguments; `sbm schema` lists required fields |
| `api_error` from a transition | Ticket in the wrong state, bad relational ID, field not on the form | Read `error.message` / `error.field`; verify IDs with `sbm field-values` |
| `--pretty` columns blank | Field not returned by that report | Try `sbm get <ticket>` to see the real field shape |
| `configure import` reports `"transitions": 0` | Source config had none | Export again from a machine where transitions are configured |

### Password changed

The keyring entry goes stale and every command returns `auth_error`. With `SBM_CLI_PASSWORD`
set, just update the variable — the keyring is not consulted. Otherwise the user either re-runs
`sbm configure setup`, or updates only the keyring entry in their own terminal (the service name is
`sbm-cli:` + `connection.host` exactly as in the config; the username is bare):

```bash
python -c "import keyring, getpass; keyring.set_password('sbm-cli:https://sbm.example.com', 'alice', getpass.getpass('SBM password: '))"
```

Run it with a Python that has `keyring` installed (for a uv install:
`uv tool run --from sbm-cli python -c "..."`). Confirm with `sbm auth check` →
`"password_source": "keyring"`.

## Upgrade and uninstall

```bash
uv tool upgrade sbm-cli           # or: pip install --upgrade sbm-cli
uv tool uninstall sbm-cli         # or: pip uninstall sbm-cli
```

Upgrades keep the config and keyring entry. After uninstalling, the config
(`~/.sbm-cli/config.toml`) and the keyring credential remain until removed by hand.
