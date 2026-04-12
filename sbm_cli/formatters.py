"""Human-readable output formatters using rich."""
from __future__ import annotations

from io import StringIO

from rich.console import Console
from rich.table import Table
from rich import box


def _console() -> Console:
    return Console(file=StringIO(), highlight=False)


def _field_val(item: dict, dbname: str) -> str:
    """Extract display value from an SBM field dict."""
    f = item.get("fields", {}).get(dbname, {})
    if not isinstance(f, dict):
        return ""
    val = f.get("value")
    if isinstance(val, dict):
        return val.get("name", str(val.get("id", "")))
    return str(val) if val is not None else ""


def format_ticket_list(items: list[dict]) -> str:
    c = _console()
    table = Table(box=box.SIMPLE_HEAD, show_edge=False)
    table.add_column("ID", style="cyan", no_wrap=True)
    table.add_column("Title")
    table.add_column("State", style="yellow")
    table.add_column("Owner", style="green")
    table.add_column("Team")
    for item in items:
        iid = item.get("id", {})
        display_id = iid.get("itemIdPrefixed", str(iid.get("id", "")))
        table.add_row(
            display_id,
            _field_val(item, "TITLE"),
            _field_val(item, "STATE"),
            _field_val(item, "OWNER"),
            _field_val(item, "SECONDARYOWNER"),
        )
    c.print(table)
    return c.file.getvalue()


def format_ticket(item: dict) -> str:
    iid = item.get("id", {})
    display_id = iid.get("itemIdPrefixed", str(iid.get("id", "")))
    lines = [f"Ticket: {display_id}"]
    for dbname, fdata in item.get("fields", {}).items():
        if not isinstance(fdata, dict):
            continue
        val = fdata.get("value")
        if isinstance(val, dict):
            val = val.get("name", str(val.get("id", "")))
        lines.append(f"  {dbname}: {val if val is not None else ''}")
    return "\n".join(lines)


def format_schema(schema: dict) -> str:
    conn = schema.get("connection", {})
    lines = [
        f"Host:           {conn.get('host', '?')}",
        f"Default table:  {conn.get('table_id', '?')}",
        f"Default report: {schema.get('defaults', {}).get('report_id', '?')}",
        "",
        "Transitions:",
    ]
    for name, t in schema.get("transitions", {}).items():
        req = ", ".join(t.get("required_fields", []))
        lines.append(f"  {name} (id={t.get('id')}) — required: {req or 'none'}")
    lines += ["", "Teams:"]
    for slug, team in schema.get("teams", {}).items():
        lines.append(f"  {slug}: {team.get('name')} (id={team.get('id')})")
    if not schema.get("teams"):
        lines.append("  (none configured)")
    return "\n".join(lines)


def format_teams(teams: dict) -> str:
    if not teams:
        return "No teams configured. Add [teams] section to ~/.sbm-cli/config.toml"
    c = _console()
    table = Table(box=box.SIMPLE_HEAD, show_edge=False)
    table.add_column("Slug", style="cyan")
    table.add_column("Name")
    table.add_column("ID", style="yellow")
    for slug, team in teams.items():
        table.add_row(slug, team.get("name", ""), str(team.get("id", "")))
    c.print(table)
    return c.file.getvalue()


def format_field_values(items: list[dict]) -> str:
    c = _console()
    table = Table(box=box.SIMPLE_HEAD, show_edge=False)
    table.add_column("ID", style="cyan")
    table.add_column("Name")
    for item in items:
        table.add_row(str(item.get("id", "")), item.get("name", ""))
    c.print(table)
    return c.file.getvalue()
