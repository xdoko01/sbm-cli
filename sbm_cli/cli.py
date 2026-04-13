"""CLI entry point for sbm-cli."""
from __future__ import annotations

import json
import sys
from pathlib import Path

import click
import requests

from sbm_cli.client import SBMClient, SBMError
from sbm_cli.config import (
    Config, ConfigError, FieldDef, TransitionConfig, UserConfig,
    load_config, save_config, DEFAULT_CONFIG_PATH,
)
from sbm_cli import formatters


# ---------------------------------------------------------------------------
# Application context
# ---------------------------------------------------------------------------

class AppContext:
    def __init__(self, config: Config, pretty: bool, quiet: bool, indent: bool = False) -> None:
        self.config = config
        self.pretty = pretty
        self.quiet = quiet
        self.indent = indent
        self._client: SBMClient | None = None

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

    def status(self, msg: str) -> None:
        """Write a status message to stderr (suppressed with --quiet)."""
        if not self.quiet:
            click.echo(msg, err=True)

    def output(self, command: str, data: object) -> None:
        """Write a successful JSON response to stdout."""
        envelope = {"ok": True, "command": command, "data": data}
        click.echo(json.dumps(envelope, indent=2 if self.indent else None))

    def error(self, command: str, error_type: str, message: str,
               field: str | None = None, exit_code: int = 1) -> None:
        """Write an error JSON response to stdout and exit."""
        err: dict = {"type": error_type, "message": message}
        if field:
            err["field"] = field
        click.echo(json.dumps({"ok": False, "command": command, "error": err},
                               indent=2 if self.indent else None))
        sys.exit(exit_code)


pass_ctx = click.make_pass_decorator(AppContext)


# ---------------------------------------------------------------------------
# Main group
# ---------------------------------------------------------------------------

@click.group()
@click.option("--pretty", "-H", is_flag=True, help="Human-readable output")
@click.option("--config", "config_path", default=None, metavar="PATH",
              help="Override config file location")
@click.option("--quiet", is_flag=True, help="Suppress stderr status messages")
@click.option("--indent", is_flag=True, help="Output formatted JSON with indentation")
@click.pass_context
def main(ctx: click.Context, pretty: bool, config_path: str | None,
         quiet: bool, indent: bool) -> None:
    """SBM 12.0 JSON API command-line client."""
    config_file = Path(config_path) if config_path else DEFAULT_CONFIG_PATH

    if ctx.invoked_subcommand == "configure":
        # configure command creates the config — no existing config needed
        ctx.obj = AppContext(Config("", "", "", False, 0, 0), pretty, quiet, indent)
        return

    # When --help is requested, skip config loading so help text is always
    # available even without a config file on disk.
    if "--help" in sys.argv or "-h" in sys.argv:
        ctx.obj = AppContext(Config("", "", "", False, 0, 0), pretty, quiet, indent)
        return

    try:
        config = load_config(config_file)
    except ConfigError as exc:
        click.echo(json.dumps({
            "ok": False,
            "command": ctx.invoked_subcommand or "",
            "error": {"type": "config_error", "message": str(exc)},
        }, indent=2 if indent else None))
        sys.exit(2)

    ctx.obj = AppContext(config, pretty, quiet, indent)


# ---------------------------------------------------------------------------
# configure group
# ---------------------------------------------------------------------------

@main.group(invoke_without_command=True)
@click.pass_context
def configure(ctx: click.Context) -> None:
    """Interactive setup commands — writes ~/.sbm-cli/config.toml.

    With no subcommand, runs the full setup wizard (same as 'configure setup').
    """
    if ctx.invoked_subcommand is None:
        ctx.invoke(configure_setup)


@configure.command("setup")
@click.pass_context
def configure_setup(ctx: click.Context) -> None:
    """Full interactive wizard — configures connection, defaults, and list fields."""
    host = click.prompt("SBM host", default="https://sbm.example.com")
    username = click.prompt("Username (bare, no domain prefix)")
    password = click.prompt("Password", hide_input=True)
    table_id = click.prompt("Default table ID", default=1000, type=int)
    report_id = click.prompt("Default report ID", default=0, type=int)
    verify_ssl = click.confirm("Verify SSL certificate?", default=False)
    if not verify_ssl:
        click.echo(
            "Warning: SSL verification disabled — only use for trusted internal hosts.",
            err=True,
        )

    list_fields_input = click.prompt(
        "Default list fields (comma-separated, blank to use built-in default "
        "TITLE,STATE,OWNER,SECONDARYOWNER,URGENCY,SEVERITY)",
        default="",
    )
    list_fields = (
        [f.strip() for f in list_fields_input.split(",") if f.strip()]
        if list_fields_input.strip()
        else []
    )

    config = Config(
        host=host, username=username, password=password,
        verify_ssl=verify_ssl, table_id=table_id, report_id=report_id,
        list_fields=list_fields,
    )
    save_config(config)
    click.echo(f"Config written to {DEFAULT_CONFIG_PATH}", err=True)

    click.echo("Testing connection...", err=True)
    client = None
    try:
        client = SBMClient(host, username, password, verify_ssl)
        client.check_auth()
        click.echo("Connection OK", err=True)
    except PermissionError as exc:
        click.echo(f"Connection failed: {exc}", err=True)
        sys.exit(2)
    except Exception as exc:
        if isinstance(exc, requests.exceptions.ConnectionError):
            click.echo(
                f"Connection failed: could not reach {host} — check the URL and network",
                err=True,
            )
        elif isinstance(exc, requests.exceptions.Timeout):
            click.echo(f"Connection failed: request timed out connecting to {host}", err=True)
        else:
            click.echo(f"Connection test failed: {exc}", err=True)
        sys.exit(2)

    # Optional: discover field definitions from a sample ticket
    sample_id = click.prompt(
        "Sample ticket ID for field discovery (leave blank to skip)",
        default="",
    )
    if sample_id.strip():
        click.echo("Fetching field definitions...", err=True)
        try:
            raw_defs = client.get_field_definitions(sample_id.strip(), table_id)
            config.fields = {
                f["dbname"]: FieldDef(
                    dbname=f["dbname"],
                    type=f.get("type", "text"),
                    label=f.get("label", f["dbname"]),
                )
                for f in raw_defs
                if "dbname" in f
            }
            save_config(config)
            click.echo(f"Stored {len(config.fields)} field definitions.", err=True)
        except Exception as exc:
            click.echo(f"Field discovery failed (skipping): {exc}", err=True)


@configure.command("transition")
@click.argument("name")
def configure_transition(name: str) -> None:
    """Add or update a named transition in ~/.sbm-cli/config.toml.

    Example: sbm configure transition assign
    """
    try:
        config = load_config(DEFAULT_CONFIG_PATH)
    except ConfigError as exc:
        click.echo(f"Error loading config: {exc}", err=True)
        click.echo("Run 'sbm configure setup' first to create the config file.", err=True)
        sys.exit(2)

    if name in config.transitions:
        if not click.confirm(f"Transition '{name}' already exists. Overwrite?", default=False):
            click.echo("Aborted.", err=True)
            return

    transition_id = click.prompt("Transition ID", type=int)

    fields_input = click.prompt(
        "Required fields (comma-separated, blank for none)", default=""
    )
    required_fields = [f.strip() for f in fields_input.split(",") if f.strip()]

    list_fields_input = click.prompt(
        "Fields that take a list value (comma-separated, blank for none)", default=""
    )
    field_types = {
        f.strip(): "list"
        for f in list_fields_input.split(",")
        if f.strip()
    }

    pre_id_str = click.prompt("Pre-transition ID (blank to skip)", default="")
    pre_id = None
    if pre_id_str.strip():
        try:
            pre_id = int(pre_id_str.strip())
        except ValueError:
            click.echo("Pre-transition ID must be an integer — skipping.", err=True)
    pre_optional = False
    if pre_id is not None:
        pre_optional = click.confirm("Pre-transition optional?", default=False)

    config.transitions[name] = TransitionConfig(
        id=transition_id,
        fields=required_fields,
        field_types=field_types,
        pre_transition_id=pre_id,
        pre_transition_optional=pre_optional,
    )
    try:
        save_config(config)
    except ConfigError as exc:
        click.echo(f"Error saving config: {exc}", err=True)
        sys.exit(2)
    click.echo(f"Transition '{name}' saved to {DEFAULT_CONFIG_PATH}", err=True)


# ---------------------------------------------------------------------------
# schema
# ---------------------------------------------------------------------------

@main.command()
@pass_ctx
def schema(ctx: AppContext) -> None:
    """Print machine-readable capabilities JSON."""
    cfg = ctx.config
    data = {
        "connection": {"host": cfg.host, "table_id": cfg.table_id},
        "defaults": {"report_id": cfg.report_id},
        "transitions": {
            name: {
                "id": t.id,
                "required_fields": t.fields,
                **({"field_types": t.field_types} if t.field_types else {}),
                **({"pre_transition_id": t.pre_transition_id} if t.pre_transition_id else {}),
            }
            for name, t in cfg.transitions.items()
        },
        "teams": {
            slug: {"id": team.id, "name": team.name}
            for slug, team in cfg.teams.items()
        },
    }
    if cfg.fields:
        data["fields"] = {
            dbname: {"type": fdef.type, "label": fdef.label}
            for dbname, fdef in cfg.fields.items()
        }
    if ctx.pretty:
        click.echo(formatters.format_schema(data))
    else:
        ctx.output("schema", data)


# ---------------------------------------------------------------------------
# teams
# ---------------------------------------------------------------------------

@main.command()
@pass_ctx
def teams(ctx: AppContext) -> None:
    """List configured teams from [teams] config section."""
    teams_data = {
        slug: {"id": t.id, "name": t.name}
        for slug, t in ctx.config.teams.items()
    }
    if ctx.pretty:
        click.echo(formatters.format_teams(teams_data))
    else:
        ctx.output("teams", teams_data)


# ---------------------------------------------------------------------------
# list
# ---------------------------------------------------------------------------

_DEFAULT_LIST_FIELDS = ["TITLE", "STATE", "OWNER", "SECONDARYOWNER", "URGENCY", "SEVERITY"]


@main.command("list")
@click.option("--report", "report_id", default=None, type=int,
              help="Report ID (overrides default)")
@click.option("--filter", "filter_id", default=None,
              help="Filter ID or name")
@click.option("--fields", default=None,
              help="Comma-separated field dbnames (default: TITLE,STATE,OWNER,SECONDARYOWNER,URGENCY,SEVERITY)")
@pass_ctx
def list_tickets(ctx: AppContext, report_id: int | None,
                 filter_id: str | None, fields: str | None) -> None:
    """List tickets from a report or filter."""
    field_list = (
        fields.split(",") if fields          # explicit --fields always wins
        else ctx.config.list_fields          # user's configured default
        or _DEFAULT_LIST_FIELDS              # hardcoded fallback when neither is set
    )

    items: list = []
    try:
        if filter_id is not None:
            items = ctx.client.list_items_by_filter(filter_id, fields=field_list)
        else:
            rid = report_id or ctx.config.report_id
            if not rid:
                ctx.error("list", "config_error",
                          "No report_id configured. Use --report or set defaults.report_id in config.",
                          exit_code=2)
            items = ctx.client.list_items_by_report(rid, fields=field_list)
    except PermissionError as exc:
        ctx.error("list", "auth_error", str(exc), exit_code=2)
    except SBMError as exc:
        ctx.error("list", "api_error", str(exc), exit_code=1)

    if ctx.pretty:
        click.echo(formatters.format_ticket_list(items, columns=field_list))
    else:
        ctx.output("list", items)


# ---------------------------------------------------------------------------
# get
# ---------------------------------------------------------------------------

@main.command()
@click.argument("ticket_id")
@click.option("--fields", default=None,
              help="Comma-separated field dbnames (default: all)")
@pass_ctx
def get(ctx: AppContext, ticket_id: str, fields: str | None) -> None:
    """Get a ticket by display ID (e.g. 02440942)."""
    field_list = fields.split(",") if fields else None

    data: dict = {}
    try:
        data = ctx.client.get_item_by_display_id(ticket_id, ctx.config.table_id,
                                                   fields=field_list)
    except PermissionError as exc:
        ctx.error("get", "auth_error", str(exc), exit_code=2)
    except ValueError as exc:
        ctx.error("get", "api_error", str(exc), exit_code=1)
    except SBMError as exc:
        ctx.error("get", "api_error", str(exc), field=exc.field, exit_code=1)

    item = data.get("item", {})
    if ctx.pretty:
        click.echo(formatters.format_ticket(item))
    else:
        ctx.output("get", item)


# ---------------------------------------------------------------------------
# transition helpers
# ---------------------------------------------------------------------------

def _parse_fields(field_args: tuple) -> dict:
    """Parse ('KEY=VALUE', ...) into a dict with int coercion where possible."""
    result: dict = {}
    for arg in field_args:
        if "=" not in arg:
            raise click.BadParameter(f"Field must be KEY=VALUE, got: {arg!r}")
        key, _, value = arg.partition("=")
        try:
            result[key] = int(value)
        except ValueError:
            result[key] = value
    return result


def _apply_field_types(field_values: dict, field_types: dict) -> dict:
    """Apply field type transformations declared in TransitionConfig.field_types."""
    result = dict(field_values)
    for field_name, ftype in field_types.items():
        if ftype == "list" and field_name in result:
            val = result[field_name]
            if not isinstance(val, list):
                result[field_name] = [val]
    return result


def _resolve_users(field_values: dict, users: dict) -> dict:
    """Replace string field values matching a configured user login with their numeric ID."""
    return {
        k: users[v].id if isinstance(v, str) and v in users else v
        for k, v in field_values.items()
    }


def _run_pre_transition(ctx: AppContext, table_id: int, item_id: int,
                        pre_id: int, optional: bool) -> None:
    """
    Execute a pre-transition (e.g. 'Start Solving' before 'Resolved').
    If optional=True, swallows SBMError (ticket already in correct state).
    """
    try:
        lock_id = ctx.client.start_transition(table_id, item_id, pre_id, break_lock=True)
        ctx.client.update_item(table_id, item_id, field_values={}, transition_id=pre_id, record_lock_id=lock_id)
    except SBMError:
        if not optional:
            raise


# ---------------------------------------------------------------------------
# transition command
# ---------------------------------------------------------------------------

@main.command()
@click.argument("name")
@click.argument("ticket_id")
@click.option("--id", "transition_id", default=None, type=int,
              help="Transition ID (required when NAME is 'run')")
@click.option("--field", "field_args", multiple=True, metavar="KEY=VALUE",
              help="Field value to set (repeatable)")
@pass_ctx
def transition(ctx: AppContext, name: str, ticket_id: str,
               transition_id: int | None, field_args: tuple) -> None:
    """Run a named transition or a raw transition by ID.

    Named:  sbm transition assign 02440942 --field OWNER=316
    Raw:    sbm transition run 02440942 --id 155 --field OWNER=316
    """
    result: dict = {}

    # ---- raw mode ----------------------------------------------------------
    if name == "run":
        if transition_id is None:
            ctx.error("transition", "validation_error",
                      "'sbm transition run' requires --id TRANSITION_ID", exit_code=3)
        field_values = _parse_fields(field_args)
        field_values = _resolve_users(field_values, ctx.config.users)
        try:
            data = ctx.client.get_item_by_display_id(ticket_id, ctx.config.table_id)
            item_id: int = data["item"]["id"]["id"]
            ctx.status(f"Starting transition id={transition_id}...")
            lock_id = ctx.client.start_transition(ctx.config.table_id, item_id,
                                                  transition_id, break_lock=True)
            result = ctx.client.update_item(
                ctx.config.table_id, item_id,
                field_values=field_values,
                transition_id=transition_id, record_lock_id=lock_id,
            )
        except PermissionError as exc:
            ctx.error("transition", "auth_error", str(exc), exit_code=2)
        except (SBMError, ValueError) as exc:
            field = exc.field if isinstance(exc, SBMError) else None
            ctx.error("transition", "api_error", str(exc), field=field, exit_code=1)
        if ctx.pretty:
            click.echo(f"Transition {transition_id} completed on {ticket_id}")
        else:
            ctx.output("transition", result)
        return

    # ---- named mode --------------------------------------------------------
    t = ctx.config.transitions.get(name)
    if t is None:
        known = ", ".join(ctx.config.transitions) or "none"
        ctx.error("transition", "config_error",
                  f"Unknown transition '{name}'. Configured: {known}", exit_code=2)
    assert t is not None  # narrowing for type checker

    field_values = _parse_fields(field_args)
    field_values = _resolve_users(field_values, ctx.config.users)

    missing = [f for f in t.fields if f not in field_values]
    if missing:
        ctx.error("transition", "validation_error",
                  f"Missing required fields for '{name}': {', '.join(missing)}",
                  exit_code=3)

    field_values = _apply_field_types(field_values, t.field_types)

    try:
        data = ctx.client.get_item_by_display_id(ticket_id, ctx.config.table_id)
        item_id = data["item"]["id"]["id"]

        # Execute optional pre-transition (e.g. "Start Solving" before "Resolved")
        if t.pre_transition_id is not None:
            ctx.status(f"Running pre-transition id={t.pre_transition_id}...")
            _run_pre_transition(ctx, ctx.config.table_id, item_id,
                                t.pre_transition_id, t.pre_transition_optional)

        ctx.status(f"Running transition '{name}' (id={t.id})...")
        lock_id = ctx.client.start_transition(ctx.config.table_id, item_id, t.id, break_lock=True)
        result = ctx.client.update_item(
            ctx.config.table_id, item_id,
            field_values=field_values,
            transition_id=t.id, record_lock_id=lock_id,
        )
    except PermissionError as exc:
        ctx.error("transition", "auth_error", str(exc), exit_code=2)
    except (SBMError, ValueError) as exc:
        field = exc.field if isinstance(exc, SBMError) else None
        ctx.error("transition", "api_error", str(exc), field=field, exit_code=1)

    if ctx.pretty:
        click.echo(f"Transition '{name}' completed on {ticket_id}")
    else:
        ctx.output("transition", result)


# ---------------------------------------------------------------------------
# field-values
# ---------------------------------------------------------------------------

@main.command("field-values")
@click.argument("field_name")
@click.option("--table", "table_id", required=True, type=int,
              help="Table ID for the relational field (find in 'sbm get' field metadata as relTableId)")
@click.option("--max-probe", default=500, type=int, show_default=True,
              help="Max item IDs to probe")
@pass_ctx
def field_values(ctx: AppContext, field_name: str, table_id: int, max_probe: int) -> None:
    """Discover valid values for a relational field.

    Probes the field's source table by ID range using 10 concurrent requests.
    Find the table ID in 'sbm get <ticket-id>' output under relTableId.

    Example: sbm field-values ROOT_CAUSE --table 9999
    """
    items: list = []
    ctx.status(f"Probing table {table_id} (up to {max_probe} items)...")
    try:
        items = ctx.client.probe_table(table_id, max_probe=max_probe)
    except PermissionError as exc:
        ctx.error("field-values", "auth_error", str(exc), exit_code=2)
    except SBMError as exc:
        ctx.error("field-values", "api_error", str(exc), exit_code=1)

    if ctx.pretty:
        click.echo(formatters.format_field_values(items))
    else:
        ctx.output("field-values", {"field": field_name, "table_id": table_id, "values": items})


# ---------------------------------------------------------------------------
# fields
# ---------------------------------------------------------------------------

@main.command("fields")
@click.argument("ticket_id")
@click.option("--table", "table_id", default=None, type=int,
              help="Table ID (defaults to configured table_id)")
@click.option("--fields", "extra_fields", default=None,
              help="Comma-separated field dbnames to probe explicitly "
                   "(for fields absent from this ticket due to null values)")
@pass_ctx
def fields_cmd(ctx: AppContext, ticket_id: str, table_id: int | None,
               extra_fields: str | None) -> None:
    """List field definitions by inspecting a sample ticket.

    Fetches TICKET_ID and reports all field dbnames, inferred types, and labels.
    Uses the configured table_id by default; override with --table.

    To discover fields that are null on this ticket, pass them explicitly:

      sbm fields 02440942 --fields FUNCTIONALITY,APPLICATION1,COUNTRY_IM

    Example: sbm fields 02440942
    """
    tid = table_id if table_id is not None else ctx.config.table_id
    extra = [f.strip() for f in extra_fields.split(",") if f.strip()] if extra_fields else None
    ctx.status(f"Fetching field definitions from ticket {ticket_id}...")
    field_defs: list = []
    try:
        field_defs = ctx.client.get_field_definitions(ticket_id, tid, extra_fields=extra)
    except PermissionError as exc:
        ctx.error("fields", "auth_error", str(exc), exit_code=2)
    except ValueError as exc:
        ctx.error("fields", "api_error", str(exc), exit_code=1)
    except SBMError as exc:
        ctx.error("fields", "api_error", str(exc), field=exc.field, exit_code=1)

    if ctx.pretty:
        click.echo(formatters.format_field_definitions(field_defs))
    else:
        ctx.output("fields", {"ticket_id": ticket_id, "table_id": tid, "fields": field_defs})
