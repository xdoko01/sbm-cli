"""Config file loading, saving, and dataclasses for sbm-cli."""
from __future__ import annotations

import tomllib
from dataclasses import dataclass, field
from pathlib import Path


DEFAULT_CONFIG_PATH = Path.home() / ".sbm-cli" / "config.toml"


@dataclass
class TransitionConfig:
    id: int
    fields: list[str] = field(default_factory=list)
    field_types: dict[str, str] = field(default_factory=dict)
    pre_transition_id: int | None = None
    pre_transition_optional: bool = False


@dataclass
class TeamConfig:
    id: int
    name: str


@dataclass
class Config:
    host: str
    username: str
    password: str
    verify_ssl: bool
    table_id: int
    report_id: int
    transitions: dict[str, TransitionConfig] = field(default_factory=dict)
    teams: dict[str, TeamConfig] = field(default_factory=dict)


class ConfigError(Exception):
    pass


def load_config(path: Path = DEFAULT_CONFIG_PATH) -> Config:
    if not path.exists():
        raise ConfigError(
            f"Config file not found: {path}\n"
            "Run 'sbm configure' to create it."
        )
    try:
        with open(path, "rb") as f:
            data = tomllib.load(f)
    except Exception as exc:
        raise ConfigError(f"Failed to read config file: {exc}") from exc

    conn = data.get("connection", {})
    defaults = data.get("defaults", {})

    missing = [k for k in ("host", "username", "password") if not conn.get(k)]
    if missing:
        raise ConfigError(
            f"Missing required [connection] keys: {', '.join(missing)}"
        )

    transitions: dict[str, TransitionConfig] = {}
    for name, raw in data.get("transitions", {}).items():
        if not isinstance(raw, dict):
            continue
        try:
            transitions[name] = TransitionConfig(
                id=raw["id"],
                fields=raw.get("fields", []),
                field_types=raw.get("field_types", {}),
                pre_transition_id=raw.get("pre_transition_id"),
                pre_transition_optional=raw.get("pre_transition_optional", False),
            )
        except KeyError as exc:
            raise ConfigError(
                f"Transition '{name}' missing required key: {exc}"
            ) from exc

    teams: dict[str, TeamConfig] = {}
    for slug, raw in data.get("teams", {}).items():
        if not isinstance(raw, dict):
            continue
        try:
            teams[slug] = TeamConfig(id=raw["id"], name=raw.get("name", slug))
        except KeyError as exc:
            raise ConfigError(f"Team '{slug}' missing required key: {exc}") from exc

    return Config(
        host=conn["host"],
        username=conn["username"],
        password=conn["password"],
        verify_ssl=conn.get("verify_ssl", True),
        table_id=defaults.get("table_id", 1000),
        report_id=defaults.get("report_id", 0),
        transitions=transitions,
        teams=teams,
    )


def _toml_str(s: str) -> str:
    """Escape a string value for TOML double-quoted strings."""
    return s.replace("\\", "\\\\").replace('"', '\\"')


def save_config(config: Config, path: Path = DEFAULT_CONFIG_PATH) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)

    lines: list[str] = [
        "[connection]",
        f'host       = "{_toml_str(config.host)}"',
        f'username   = "{_toml_str(config.username)}"',
        f'password   = "{_toml_str(config.password)}"',
        f"verify_ssl = {'true' if config.verify_ssl else 'false'}",
        "",
        "[defaults]",
        f"table_id  = {config.table_id}",
        f"report_id = {config.report_id}",
    ]

    for name, t in config.transitions.items():
        lines.append("")
        lines.append(f"[transitions.{name}]")
        lines.append(f"id = {t.id}")
        fields_str = ", ".join(f'"{f}"' for f in t.fields)
        lines.append(f"fields = [{fields_str}]")
        if t.pre_transition_id is not None:
            lines.append(f"pre_transition_id = {t.pre_transition_id}")
            lines.append(f"pre_transition_optional = {'true' if t.pre_transition_optional else 'false'}")
        if t.field_types:
            lines.append("")
            lines.append(f"[transitions.{name}.field_types]")
            for fname, ftype in t.field_types.items():
                lines.append(f'{fname} = "{_toml_str(ftype)}"')

    if config.teams:
        lines.append("")
        lines.append("[teams]")
        for slug, team in config.teams.items():
            lines.append(f'{slug} = {{ id = {team.id}, name = "{_toml_str(team.name)}" }}')

    lines.append("")
    path.write_text("\n".join(lines), encoding="utf-8")
