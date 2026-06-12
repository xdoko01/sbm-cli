# sbm-cli — Installation and Usage Manual

**Version:** 0.4.0  
**Date:** 2026-06-12  
**Platform:** Windows 10/11 · macOS 13+ · Linux (Ubuntu 22.04+)

---

## Table of Contents

1. [Introduction](#1-introduction)
2. [Prerequisites & System Requirements](#2-prerequisites--system-requirements)
3. [Installation](#3-installation)
4. [First-Run Configuration](#4-first-run-configuration)
5. [Secure Password Storage](#5-secure-password-storage)
   - 5.1 [Why this matters](#51-why-this-matters)
   - 5.2 [What happens during configure setup](#52-what-happens-during-sbm-configure-setup)
   - 5.3 [Platform-specific keyring details](#53-platform-specific-keyring-details)
   - 5.4 [Updating your password](#54-updating-your-password)
   - 5.5 [Removing the credential](#55-removing-the-credential)
   - 5.6 [Migration from a plaintext config](#56-migration-from-an-old-plaintext-config)
6. [Command Reference](#6-command-reference)
   - [Global flags](#global-flags)
   - [configure setup](#sbm-configure-setup)
   - [configure transition](#sbm-configure-transition-name)
   - [schema](#sbm-schema)
   - [list](#sbm-list)
   - [get](#sbm-get-ticket-id)
   - [transition](#sbm-transition-name-ticket-id)
   - [field-values](#sbm-field-values-field_name)
   - [fields](#sbm-fields-ticket-id)
   - [teams](#sbm-teams)
7. [Config File Reference](#7-config-file-reference)
8. [Upgrading & Uninstalling](#8-upgrading--uninstalling)

---

## 1. Introduction

**sbm-cli** is a command-line client for the **SBM (Serena Business Manager) 12.0 JSON API**. It is designed for L3 support staff who manage tickets from the terminal — without opening the SBM web interface.

With sbm-cli you can:

- **List** open tickets from a saved report or filter
- **Get** the full details of any ticket by its display ID
- **Transition** tickets between states (assign, close, return to L2, and any other workflow steps your team has configured)
- **Discover** the valid values for relational fields like `L3_SPECIALIST_GROUP`
- **Inspect** the field schema of any ticket type

All operations output clean JSON by default, or formatted tables with the `--pretty` flag. This makes sbm-cli easy to use both interactively and in scripts.

**Supported platforms:** Windows 10/11, macOS 13 (Ventura) or newer, and Linux (Ubuntu 22.04+ or equivalent).

---

## 2. Prerequisites & System Requirements

Before installing sbm-cli, confirm that the following are in place:

**All platforms**

| Requirement | Minimum | How to check |
|---|---|---|
| Python | 3.11 or newer | `python --version` or `python3 --version` |
| Network access | Reachable SBM server URL | Ask your SBM administrator |
| Package installer | `uv` (recommended) or `pip` | `uv --version` or `pip --version` |

**Platform-specific**

| Platform | Requirement | Notes |
|---|---|---|
| Windows 10/11 | Built-in | Python available from python.org or Microsoft Store |
| macOS 13+ | Homebrew Python recommended | `brew install python@3.11` |
| Linux (Ubuntu 22.04+) | System Python or pyenv | `sudo apt install python3 python3-pip` |
| Linux (desktop) | GNOME Keyring or KWallet | Required for persistent password storage; see Section 5.3 |
| Linux (headless/server) | None | Password is prompted interactively on each run; see Section 5.3 |

**Installing uv** (recommended, all platforms):

*Windows (PowerShell):*
```powershell
pip install uv
```

*macOS / Linux (shell):*
```bash
curl -LsSf https://astral.sh/uv/install.sh | sh
```

Or follow the official guide: https://docs.astral.sh/uv/getting-started/installation/

> **Note:** uv installs sbm-cli in an isolated environment, keeping it separate from any other Python projects on your machine.

---

## 3. Installation

### Option A — via uv (recommended)

```
uv tool install sbm-cli
```

Run this command once. uv installs sbm-cli in an isolated environment and makes the `sbm` command available system-wide.

### Option B — via pip

```
pip install sbm-cli
```

### Installing from a wheel file (offline / no internet access)

If you received a `.whl` file directly (for example, `sbm_cli-0.4.0-py3-none-any.whl`):

```
pip install sbm_cli-0.4.0-py3-none-any.whl
```

### Verifying the installation

After installing, confirm the `sbm` command is available:

```
sbm --version
```

Expected output:

```
sbm, version 0.4.0
```

If the command is not found, close and reopen your terminal window and try again.

---

## 4. First-Run Configuration

Run the interactive setup wizard to create your configuration file:

```
sbm configure setup
```

The wizard will prompt you for the following values:

| Prompt | Example | Notes |
|---|---|---|
| SBM host URL | `https://sbm.example.com` | Include `https://` — no trailing slash |
| Username | `john.doe` | Your SBM login name (case-sensitive) |
| Password | *(hidden)* | Typed but not echoed; stored in your system keyring — **never written to disk** |
| Default table ID | `1000` | The SBM table your tickets live in; ask your admin if unsure |
| Default report ID | `2208` | The saved report used by `sbm list`; ask your admin if unsure |
| Verify SSL | `y` or `n` | Enter `n` if your SBM server uses a self-signed certificate |
| Default list fields | `TITLE,STATE,OWNER` | Comma-separated field names shown by `sbm list` |
| Sample ticket ID | `INC-12345` | Optional; sbm-cli uses this ticket to auto-discover field definitions |

After the wizard completes, your configuration file is written to:

```
C:\Users\<you>\.sbm-cli\config.toml
```

> **macOS / Linux:** The config file is at `~/.sbm-cli/config.toml`.

Open it with any text editor to verify. It should look similar to this:

```toml
[connection]
host       = "https://sbm.example.com"
username   = "john.doe"
verify_ssl = false

[defaults]
table_id    = 1000
report_id   = 2208
list_fields = ["TITLE", "STATE", "OWNER"]
```

> **Important:** The config file contains no `password` field. Your password is stored separately in your system's secure keyring (see [Section 5](#5-secure-password-storage) for details).

### Testing the connection

After configuration, run a quick test:

```
sbm --pretty list
```

If the connection succeeds you will see a table of your open tickets. If it fails with an authentication error, re-run `sbm configure setup` to correct your credentials.

---

## 5. Secure Password Storage

> **This is the most important security section of this manual.**  
> Your password is never written to a file. It is always stored in your operating system's secure keyring.

### 5.1 Why this matters

Storing a password in a plain-text config file (`config.toml`) means:

- Any process running as your user account can read the file
- If you accidentally share the file (email, screen share, version control), the password is exposed
- Backup tools may copy the file to cloud storage in plaintext

sbm-cli uses the **system keyring** — a secure, OS-managed credential store protected by your login session. The password never appears in any file on disk.

### 5.2 What happens during `sbm configure setup`

When you type your password at the wizard prompt, sbm-cli performs these steps:

1. Calls the `keyring` library with your password
2. `keyring` stores the credential in your system keyring under the name `sbm-cli:<host>` (for example: `sbm-cli:https://sbm.example.com`)
3. Saves `config.toml` **without** a `password =` field
4. On every subsequent command, sbm-cli retrieves the password from the keyring at runtime

### 5.3 Platform-specific keyring details

**Windows — Credential Manager**

Credentials are stored in Windows Credential Manager.

To verify or remove a stored credential:
1. Press **Win**, type **Credential Manager**, press Enter
2. Click **Windows Credentials**
3. Look for `sbm-cli:https://...`

To remove via PowerShell:
```powershell
cmdkey /delete:sbm-cli:https://sbm.example.com
```

**macOS — Keychain**

Credentials are stored in the macOS Keychain (`login` keychain).

To verify via GUI:
1. Open **Keychain Access** (Applications → Utilities → Keychain Access)
2. Search for `sbm-cli`
3. You should see an entry for your SBM host

To remove via Terminal:
```bash
security delete-generic-password -s "sbm-cli:https://sbm.example.com"
```

**Linux — GNOME Keyring / KWallet (desktop)**

On desktop Linux with GNOME or KDE, credentials are stored via SecretService.

Install GNOME Keyring if not already present:
```bash
sudo apt install gnome-keyring libsecret-tools   # Ubuntu/Debian
sudo dnf install gnome-keyring libsecret         # Fedora
```

To remove a stored credential:
```bash
secret-tool clear service sbm-cli:https://sbm.example.com
```

**Linux — Headless / server (no keyring daemon)**

On servers or CI systems without a desktop keyring daemon, sbm-cli cannot store credentials persistently. It handles this gracefully:

- `sbm configure setup` will warn you that no keyring is available and continue
- On every subsequent command, sbm-cli prompts interactively:
  ```
  Password:
  ```
- The password is used for that invocation only — it is never written to disk

### 5.4 Updating your password

Re-run the setup wizard:

```
sbm configure setup
```

When you reach the password prompt, type your new password. sbm-cli will overwrite the old entry in the keyring.

### 5.5 Removing the credential

See the platform-specific instructions in [Section 5.3](#53-platform-specific-keyring-details) above.

To also remove the config file:

*Windows:*
```powershell
Remove-Item "$env:USERPROFILE\.sbm-cli\config.toml"
```

*macOS / Linux:*
```bash
rm ~/.sbm-cli/config.toml
```

### 5.6 Migration from an old plaintext config

Versions of sbm-cli older than 0.2.0 stored the password directly in `config.toml`. On the first run after upgrading, sbm-cli automatically migrates your credential:

1. The password is read from the old `config.toml`
2. It is stored in the system keyring
3. `config.toml` is rewritten with the `password =` line removed
4. A one-time message appears: `Password migrated to <platform keyring name>.`

On headless Linux without a keyring daemon, migration is skipped and a warning is printed. The plaintext password remains in `config.toml` until you run `sbm configure setup` in an environment with a keyring available.

---

## 6. Command Reference

### Global flags

These flags can be placed immediately after `sbm`, before any subcommand:

| Flag | Short | Meaning |
|---|---|---|
| `--version` | | Show the installed version and exit |
| `--pretty` | `-H` | Format output as a human-readable table instead of JSON |
| `--indent` | | Format JSON output with indentation (pretty-printed JSON) |
| `--config PATH` | | Load a different config file instead of the default |
| `--quiet` | | Suppress informational messages on stderr |

**Example:**

```
sbm --pretty list
sbm --indent get INC-12345
sbm --config ~/alt/config.toml list
```

> **Note:** Use an absolute or home-relative path with `--config`.

---

### `sbm configure setup`

Runs the interactive first-time setup wizard. Re-run any time you need to change the host, username, password, or defaults.

```
sbm configure setup
```

See [Section 4](#4-first-run-configuration) for a full walkthrough.

---

### `sbm configure transition <name>`

Adds or updates a named transition in your config file. A named transition is a shortcut for a specific SBM workflow step, pre-loaded with the fields it requires.

```
sbm configure transition assign
sbm configure transition close
```

The wizard prompts for:

| Prompt | Example | Meaning |
|---|---|---|
| Transition ID | `155` | The numeric SBM transition ID (from `sbm schema`) |
| Required fields | `OWNER,L3_SPECIALIST_GROUP` | Fields that must be provided when running this transition |
| List-type fields | `L3_SPECIALIST_GROUP` | Fields whose values come from a relational lookup (use `sbm field-values` to discover them) |
| Optional fields | `SOLUTION_STEPS` | Fields that may be provided but are not required |
| Pre-transition ID | `142` | Optional: a transition to run automatically before this one |
| Pre-transition optional | `y` / `n` | If `y`, failure of the pre-transition does not abort the main transition |

Once configured, the transition can be run with:

```
sbm transition assign INC-12345 --field OWNER=john.doe
```

---

### `sbm schema`

Prints the full capability summary of your current configuration: all named transitions, teams, and field definitions.

```
sbm schema
sbm --pretty schema
```

Use this command to discover what transitions are available and what fields they expect.

**Sample output (`sbm --pretty schema`):**

```
Host:           https://sbm.example.com
Default table:  1000
Default report: 2208

Transitions:
  assign (id=155) — required: OWNER, L3_SPECIALIST_GROUP — optional: SOLUTION_STEPS
  close (id=160) — required: RESOLUTION, ROOT_CAUSE — optional: SOLUTION_STEPS
  return-l2 (id=16) — required: RETURN_REASON, RETURN_NOTE, SOLUTION_STEPS

Teams:
  windows-l3: L3 Windows Support (id=155)
  networking-l3: L3 Networking (id=160)
```

---

### `sbm list`

Lists tickets from the default report or a specified report/filter.

```
sbm list
sbm --pretty list
sbm list --report 2210
sbm list --filter "My Open Tickets"
sbm list --fields TITLE,STATE,OWNER,FUNCTIONALITY
```

| Flag | Default | Meaning |
|---|---|---|
| `--report N` | `report_id` from config | SBM saved report ID |
| `--filter N` | — | SBM filter ID or filter name |
| `--fields F1,F2` | `list_fields` from config | Comma-separated field database names to include |

**Tip:** Use `sbm --pretty list` to get a readable table. Omit `--pretty` when piping to other tools or scripts.

---

### `sbm get <ticket-id>`

Shows the details of a single ticket. By default returns all fields; use `--fields` to limit the output.

```
sbm get INC-12345
sbm --pretty get INC-12345
sbm get INC-12345 --fields TITLE,STATE,DESCRIPTION,OWNER
```

| Argument/Flag | Meaning |
|---|---|
| `<ticket-id>` | The ticket display ID, for example `INC-12345` |
| `--fields F1,F2` | Comma-separated list of field names to return (default: all) |

---

### `sbm transition <name> <ticket-id>`

Executes a named transition on a ticket. The transition must be defined in your config (see `sbm configure transition`).

```
sbm transition assign INC-12345 --field OWNER=john.doe --field L3_SPECIALIST_GROUP=L3SupportWindows
sbm transition close INC-12345 --field RESOLUTION="Fixed" --field ROOT_CAUSE=1701
sbm transition close INC-12345 --field RESOLUTION="Fixed" --field ROOT_CAUSE=1701 --field SOLUTION_STEPS="Root cause identified and resolved."
sbm transition return-l2 INC-12345
```

| Argument/Flag | Meaning |
|---|---|
| `<name>` | The transition name as defined in config (e.g. `assign`, `close`) |
| `<ticket-id>` | The ticket display ID |
| `--field KEY=VALUE` | A field value to set; repeat for multiple fields |

**Providing optional fields:**

If a transition has `optional_fields` configured (for example `SOLUTION_STEPS`), you may include or omit `--field SOLUTION_STEPS=...`. The field is sent only when you provide it.

**Running an unconfigured transition by ID:**

Use the special name `run` with an explicit `--id` to execute any SBM transition without prior configuration:

```
sbm transition run INC-12345 --id 155 --field OWNER=john.doe
```

---

### `sbm field-values <field_name>`

Discovers all valid values for a relational (list-type) field. Use this when you need to know what values are accepted by a `--field` argument.

```
sbm field-values ROOT_CAUSE --table 9999
sbm field-values RETURN_REASON --table 1080
```

| Argument/Flag | Meaning |
|---|---|
| `<field_name>` | The database name of the field |
| `--table TABLE_ID` | Required; the **relational source table ID** for this field — find it in `sbm get <ticket-id>` output as the `relTableId` property on the field. This is **not** the main ticket table ID. |
| `--max-probe N` | Maximum number of item IDs to probe (default: 500) |

**How to find the correct table ID:**

```
sbm get INC-12345
```

Look for the field in the JSON output. Its `relTableId` property is the value to pass to `--table`.

**Output:**

```json
{"ok": true, "command": "field-values", "data": {"field": "ROOT_CAUSE", "table_id": 9999, "values": [
  {"id": 1673, "name": "Software bug"},
  {"id": 2387, "name": "Configuration issue"},
  ...
]}}
```

Use the `id` (not the name) when passing `--field` arguments to `sbm transition` for relational fields.

---

### `sbm fields <ticket-id>`

Inspects the field definitions available on a ticket. Useful when setting up a new transition and you need to know the exact database names of fields.

```
sbm fields INC-12345
sbm fields INC-12345 --fields OWNER,L3_SPECIALIST_GROUP
```

| Argument/Flag | Meaning |
|---|---|
| `<ticket-id>` | Sample ticket to inspect |
| `--table TABLE_ID` | Table ID (defaults to `table_id` from config) |
| `--fields F1,F2` | Limit output to specific field names |

---

### `sbm teams`

Lists all team → ticket-manager mappings configured in your config file.

```
sbm teams
sbm --pretty teams
```

This command reads from the `[teams]` section of `config.toml` — it does not query SBM live. Use it to confirm team names are correctly configured before running automated assignment workflows.

---

## 7. Config File Reference

Location: `C:\Users\<you>\.sbm-cli\config.toml` (Windows) or `~/.sbm-cli/config.toml` (macOS / Linux)

This file is created and maintained by `sbm configure setup` and `sbm configure transition`. You can also edit it directly in a text editor.

```toml
# ── Connection ───────────────────────────────────────────────────────────
[connection]
host       = "https://sbm.example.com"   # SBM server base URL (required)
username   = "john.doe"                   # Your SBM login name (required)
verify_ssl = false                         # Set false for self-signed certs

# ── Defaults ─────────────────────────────────────────────────────────────
[defaults]
table_id    = 1000                         # Default item table ID
report_id   = 2208                         # Report used by `sbm list`
list_fields = ["TITLE", "STATE", "OWNER"]  # Fields shown by default in list output

# ── Named transitions ─────────────────────────────────────────────────────
# Run with: sbm transition assign INC-xxxxx --field ...
[transitions.assign]
id              = 155                          # SBM transition ID
fields          = ["OWNER", "L3_SPECIALIST_GROUP"]  # Required fields
optional_fields = ["SOLUTION_STEPS"]           # Fields that may be omitted

[transitions.assign.field_types]
L3_SPECIALIST_GROUP = "list"                   # Relational field — value must be looked up

[transitions.close]
id              = 160
fields          = []
optional_fields = ["SOLUTION_STEPS"]
pre_transition_id       = 142                  # Auto-run transition 142 before closing
pre_transition_optional = true                 # Don't abort close if pre-transition fails

# ── Team mappings ─────────────────────────────────────────────────────────
# Shown by `sbm teams`
[teams]
windows-l3   = { id = 155, name = "L3 Windows Support" }
networking-l3 = { id = 160, name = "L3 Networking" }

# ── User aliases ──────────────────────────────────────────────────────────
# Use in --field OWNER=alice instead of --field OWNER=<numeric id>
[users]
alice = { id = 316 }
bob   = { id = 317 }

# ── Cached field definitions ──────────────────────────────────────────────
# Populated automatically by `sbm configure setup` from a sample ticket
[fields]
TITLE       = { type = "text", label = "Title" }
STATE       = { type = "text", label = "State" }
OWNER       = { type = "text", label = "Owner" }
SOLUTION_STEPS = { type = "text", label = "Solution Steps" }
```

### Key rules

| Rule | Detail |
|---|---|
| No `password =` field | Password is in your system keyring, not here |
| Field names are case-sensitive | Use the exact database name from `sbm fields` |
| List-type fields need `field_types` | Without this, sbm-cli sends a text value instead of an array and the transition may fail |
| Config keys must be alphanumeric | Transition names may contain letters, digits, `-`, and `_` only |

---

## 8. Upgrading & Uninstalling

### Upgrading

```
uv tool upgrade sbm-cli        # if installed via uv
pip install --upgrade sbm-cli  # if installed via pip
```

Verify the new version after upgrading:

```
sbm --version
```

Your `config.toml` and keyring entries are not affected by upgrades.

### Uninstalling

```
uv tool uninstall sbm-cli     # if installed via uv
pip uninstall sbm-cli          # if installed via pip
```

After uninstalling, optionally clean up the remaining files:

1. **Remove the config file:**

   *Windows:*
   ```powershell
   Remove-Item "$env:USERPROFILE\.sbm-cli\config.toml"
   ```

   *macOS / Linux:*
   ```bash
   rm ~/.sbm-cli/config.toml
   ```

2. **Remove the stored password from your system keyring:**  
   See [Section 5.3](#53-platform-specific-keyring-details) for platform-specific instructions.

---

*End of manual — sbm-cli v0.4.0*
