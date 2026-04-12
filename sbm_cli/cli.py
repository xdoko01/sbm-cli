"""CLI entry point for sbm-cli."""
from __future__ import annotations

import json
import sys
from pathlib import Path

import click

from sbm_cli.client import SBMClient, SBMError
from sbm_cli.config import (
    Config, ConfigError, TransitionConfig,
    load_config, save_config, DEFAULT_CONFIG_PATH,
)
from sbm_cli import formatters


# ---------------------------------------------------------------------------
# Application context
# ---------------------------------------------------------------------------

class AppContext:
    def __init__(self, config: Config, pretty: bool, quiet: bool) -> None:
        self.config = config
        self.pretty = pretty
        self.quiet = quiet
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
        click.echo(json.dumps({"ok": True, "command": command, "data": data}))

    def error(self, command: str, error_type: str, message: str,
               field: str | None = None, exit_code: int = 1) -> None:
        """Write an error JSON response to stdout and exit."""
        err: dict = {"type": error_type, "message": message}
        if field:
            err["field"] = field
        click.echo(json.dumps({"ok": False, "command": command, "error": err}))
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
@click.pass_context
def main(ctx: click.Context, pretty: bool, config_path: str | None, quiet: bool) -> None:
    """SBM 12.0 JSON API command-line client."""
    config_file = Path(config_path) if config_path else DEFAULT_CONFIG_PATH

    if ctx.invoked_subcommand == "configure":
        # configure command creates the config — no existing config needed
        ctx.obj = AppContext(Config("", "", "", False, 0, 0), pretty, quiet)
        return

    try:
        config = load_config(config_file)
    except ConfigError as exc:
        click.echo(json.dumps({
            "ok": False,
            "command": ctx.invoked_subcommand or "",
            "error": {"type": "config_error", "message": str(exc)},
        }))
        sys.exit(2)

    ctx.obj = AppContext(config, pretty, quiet)


# ---------------------------------------------------------------------------
# configure
# ---------------------------------------------------------------------------

@main.command()
@click.pass_context
def configure(ctx: click.Context) -> None:
    """Interactive setup wizard — writes ~/.sbm-cli/config.toml."""
    host = click.prompt("SBM host", default="https://sbm.example.com")
    username = click.prompt("Username (bare, no domain prefix)")
    password = click.prompt("Password", hide_input=True)
    table_id = click.prompt("Default table ID", default=1000, type=int)
    report_id = click.prompt("Default report ID", default=0, type=int)
    verify_ssl = click.confirm("Verify SSL certificate?", default=False)

    config = Config(
        host=host, username=username, password=password,
        verify_ssl=verify_ssl, table_id=table_id, report_id=report_id,
    )
    save_config(config)
    click.echo(f"Config written to {DEFAULT_CONFIG_PATH}", err=True)

    click.echo("Testing connection...", err=True)
    try:
        client = SBMClient(host, username, password, verify_ssl)
        client.check_auth()
        click.echo("Connection OK", err=True)
    except PermissionError as exc:
        click.echo(f"Connection failed: {exc}", err=True)
        sys.exit(2)
    except Exception as exc:
        click.echo(f"Connection test failed: {exc}", err=True)
        sys.exit(2)


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
