# sbm-cli config file reference

Location: `~/.sbm-cli/config.toml` (Windows: `C:\Users\<you>\.sbm-cli\config.toml`).
Override with `--config PATH` or the `SBM_CLI_CONFIG` environment variable.

Written by `sbm configure setup`, `sbm configure transition` and `sbm configure import`;
safe to edit by hand. Validate an edit with `sbm schema` (parses the file, no network call).

```toml
[connection]
host       = "https://sbm.example.com"   # required; full URL, no trailing slash
username   = "alice"                     # required; bare login, no DOMAIN\ prefix
verify_ssl = false                       # false for self-signed internal certificates (default true)

[defaults]
table_id    = 1000                       # table the tickets live in (default 1000)
report_ids  = [2208, 2209]               # reports `sbm list` merges and de-duplicates
list_fields = ["TITLE", "STATE", "OWNER"] # default `sbm list` columns; empty = built-in default

# One section per named transition: sbm transition <name> <ticket> --field K=V
[transitions.close]
id                      = 19                  # SBM transition ID (instance-specific)
fields                  = ["RESOLUTION", "ROOT_CAUSE"]  # required --field keys
optional_fields         = ["SOLUTION_STEPS"]  # accepted without a warning
pre_transition_id       = 148                 # run this transition first (e.g. Start Solving)
pre_transition_optional = true                # ignore a pre-transition failure (already in state)

[transitions.close.field_types]
L3_SPECIALIST_GROUP = "list"                  # value is sent as a JSON array

[teams]                                       # shown by `sbm teams` and `sbm schema`
my-team = { id = 155, name = "L3 My Team" }

[users]                                       # --field OWNER=alice is sent as OWNER=316
alice = { id = 316 }

[fields]                                      # cached by the wizard from a sample ticket
TITLE = { type = "text", label = "Title" }
```

## Rules

- **No `password` key.** The password comes from `SBM_CLI_PASSWORD`, the system keyring, or a
  terminal prompt. An old plaintext `password =` is migrated to the keyring on the next run;
  `sbm configure import` strips it instead of installing it.
- Field dbnames are case-sensitive — copy them from `sbm fields <ticket>`.
- A relational field that SBM expects as an array (e.g. `L3_SPECIALIST_GROUP`) must be declared
  `"list"` under `field_types`, or the transition fails.
- Transition names may contain letters, digits, `-` and `_`.
- A legacy singular `report_id = 2208` is read as `report_ids = [2208]` and rewritten on the next save.
- `sbm configure transition` does not prompt for `optional_fields`; add them by hand.
