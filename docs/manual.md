# sbm-cli — Installation and Usage Manual

**Version:** 0.3.1  
**Date:** 2026-06-09  
**Platform:** Windows 10 / Windows 11

---

## Table of Contents

1. [Introduction](#1-introduction)
2. [Prerequisites & System Requirements](#2-prerequisites--system-requirements)
3. [Installation](#3-installation)
4. [First-Run Configuration](#4-first-run-configuration)
5. [Secure Password Storage (Windows Credential Manager)](#5-secure-password-storage-windows-credential-manager)
   - 5.1 [Why this matters](#51-why-this-matters)
   - 5.2 [What happens during configure setup](#52-what-happens-during-sbm-configure-setup)
   - 5.3 [Verifying the stored credential](#53-verifying-the-stored-credential-gui)
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

**Supported platform:** Windows 10 and Windows 11 only.

---

## 2. Prerequisites & System Requirements

Before installing sbm-cli, confirm that the following are in place:

| Requirement | Minimum | How to check |
|---|---|---|
| Operating system | Windows 10 or Windows 11 | *Settings → System → About* |
| Python | 3.11 or newer | `python --version` |
| Network access | Reachable SBM server URL | Ask your SBM administrator |
| Package installer | `uv` (recommended) or `pip` | `uv --version` or `pip --version` |

**Installing uv** (if not already present):

```
pip install uv
```

Or follow the official guide: https://docs.astral.sh/uv/getting-started/installation/

> **Note:** uv is the recommended way to install sbm-cli because it places the tool in an isolated environment, keeping it separate from any other Python projects on your machine.

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

If you received a `.whl` file directly (for example, `sbm_cli-0.3.1-py3-none-any.whl`):

```
pip install sbm_cli-0.3.1-py3-none-any.whl
```

### Verifying the installation

After installing, confirm the `sbm` command is available:

```
sbm --version
```

Expected output:

```
sbm-cli, version 0.3.1
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
| Password | *(hidden)* | Typed but not echoed; stored in Windows Credential Manager — **never written to disk** |
| Default table ID | `1000` | The SBM table your tickets live in; ask your admin if unsure |
| Default report ID | `2208` | The saved report used by `sbm list`; ask your admin if unsure |
| Verify SSL | `y` or `n` | Enter `n` if your SBM server uses a self-signed certificate |
| Default list fields | `TITLE,STATE,OWNER` | Comma-separated field names shown by `sbm list` |
| Sample ticket ID | `INC-12345` | Optional; sbm-cli uses this ticket to auto-discover field definitions |

After the wizard completes, your configuration file is written to:

```
C:\Users\<you>\.sbm-cli\config.toml
```

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

> **Important:** The config file contains no `password` field. Your password is stored separately in Windows Credential Manager. See [Section 5](#5-secure-password-storage-windows-credential-manager) for details.

### Testing the connection

After configuration, run a quick test:

```
sbm list --pretty
```

If the connection succeeds you will see a table of your open tickets. If it fails with an authentication error, re-run `sbm configure setup` to correct your credentials.

---

## 5. Secure Password Storage (Windows Credential Manager)

> **This is the most important security section of this manual.**  
> Your password is never written to a file. It is always stored in Windows Credential Manager.

### 5.1 Why this matters

Storing a password in a plain-text config file (`config.toml`) means:

- Any process running as your user account can read the file
- If you accidentally share the file (email, screen share, version control), the password is exposed
- Backup tools may copy the file to cloud storage in plaintext

**Windows Credential Manager** stores credentials in encrypted form, protected by your Windows login. Only your own user session can decrypt and read them. The password never appears in any file on disk.

### 5.2 What happens during `sbm configure setup`

When you type your password at the wizard prompt, sbm-cli performs these steps:

1. Calls the `keyring` library with your password
2. `keyring` stores the credential in Windows Credential Manager under the name `sbm-cli:<host>` (for example: `sbm-cli:https://sbm.example.com`)
3. Saves `config.toml` **without** a `password =` field
4. On every subsequent command, sbm-cli retrieves the password from Credential Manager at runtime — it is never cached in memory between commands

### 5.3 Verifying the stored credential (GUI)

To confirm that your password has been stored correctly:

1. Press **Win**, type **Credential Manager**, and press Enter
2. Click **Windows Credentials**
3. Scroll through the list and look for an entry beginning with `sbm-cli:`  
   (for example: `sbm-cli:https://sbm.example.com`)
4. Click the entry to expand it — you should see your username listed

If the entry is present, sbm-cli will be able to authenticate. If it is missing, re-run `sbm configure setup`.

### 5.4 Updating your password

If your SBM password changes, run the setup wizard again:

```
sbm configure setup
```

At each prompt you can press **Enter** to keep the existing value. When you reach the password prompt, type your new password. sbm-cli will overwrite the old entry in Credential Manager.

### 5.5 Removing the credential

You may want to remove the stored credential when changing accounts, uninstalling the tool, or rotating credentials on a shared machine.

**Via the GUI:**

1. Open Credential Manager (see [Section 5.3](#53-verifying-the-stored-credential-gui))
2. Click **Windows Credentials**
3. Find the `sbm-cli:https://…` entry and click it to expand
4. Click **Remove** and confirm

**Via PowerShell (command line only):**

Replace the URL with your actual SBM host:

```powershell
cmdkey /delete:sbm-cli:https://sbm.example.com
```

To also remove the config file:

```powershell
Remove-Item "$env:USERPROFILE\.sbm-cli\config.toml"
```

### 5.6 Migration from an old plaintext config

Versions of sbm-cli older than 0.2.0 stored the password directly in `config.toml`. If you upgrade from such a version, sbm-cli automatically migrates your credential on the first run:

1. The password is read from the old `config.toml`
2. It is stored in Windows Credential Manager
3. `config.toml` is rewritten with the `password =` line removed
4. A one-time message appears on the terminal: `Password migrated to Windows Credential Manager.`

No manual action is needed. After migration, your config file will no longer contain a password.

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
sbm --config C:\alt\config.toml list
```

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
sbm schema --pretty
```

Use this command to discover what transitions are available and what fields they expect.

**Sample output (--pretty):**

```
Transitions: assign, close, return
Teams: windows-l3, networking-l3
Fields: TITLE, STATE, OWNER, L3_SPECIALIST_GROUP, SOLUTION_STEPS
```

---

### `sbm list`

Lists tickets from the default report or a specified report/filter.

```
sbm list
sbm list --pretty
sbm list --report 2210
sbm list --filter "My Open Tickets"
sbm list --fields TITLE,STATE,OWNER,FUNCTIONALITY
```

| Flag | Default | Meaning |
|---|---|---|
| `--report N` | `report_id` from config | SBM saved report ID |
| `--filter N` | — | SBM filter ID or filter name |
| `--fields F1,F2` | `list_fields` from config | Comma-separated field database names to include |

**Tip:** Use `--pretty` to get a readable table. Omit it when piping to other tools or scripts.

---

### `sbm get <ticket-id>`

Shows the details of a single ticket. By default returns all fields; use `--fields` to limit the output.

```
sbm get INC-12345
sbm get INC-12345 --pretty
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
sbm transition close INC-12345 --field SOLUTION_STEPS="Resolved by rebooting the server."
sbm transition return INC-12345
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
sbm field-values L3_SPECIALIST_GROUP --table 1000
sbm field-values OWNER --table 1000
```

| Argument/Flag | Meaning |
|---|---|
| `<field_name>` | The database name of the field |
| `--table TABLE_ID` | Required; the SBM table ID that contains this field |
| `--max-probe N` | Maximum number of item IDs to probe (default: 500) |

**Output:**

```json
[
  {"id": 201, "value": "L3SupportWindows"},
  {"id": 202, "value": "L3SupportNetwork"},
  ...
]
```

Use the `value` string (not the `id`) when passing `--field` arguments to `sbm transition`.

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
sbm teams --pretty
```

This command reads from the `[teams]` section of `config.toml` — it does not query SBM live. Use it to confirm team names are correctly configured before running automated assignment workflows.

---

## 7. Config File Reference

Location: `C:\Users\<you>\.sbm-cli\config.toml`

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
| No `password =` field | Password is in Windows Credential Manager, not here |
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

Your `config.toml` and Credential Manager entries are not affected by upgrades.

### Uninstalling

```
uv tool uninstall sbm-cli     # if installed via uv
pip uninstall sbm-cli          # if installed via pip
```

After uninstalling, optionally clean up the remaining files:

1. **Remove the config file:**
   ```powershell
   Remove-Item "$env:USERPROFILE\.sbm-cli\config.toml"
   ```

2. **Remove the stored password from Windows Credential Manager:**  
   Open Credential Manager → Windows Credentials → find `sbm-cli:https://…` → click Remove  
   
   Or via PowerShell:
   ```powershell
   cmdkey /delete:sbm-cli:https://sbm.example.com
   ```

---

*End of manual — sbm-cli v0.3.1*
