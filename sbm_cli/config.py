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
        transitions[name] = TransitionConfig(
            id=raw["id"],
            fields=raw.get("fields", []),
            field_types=raw.get("field_types", {}),
            pre_transition_id=raw.get("pre_transition_id"),
            pre_transition_optional=raw.get("pre_transition_optional", False),
        )

    teams: dict[str, TeamConfig] = {}
    for slug, raw in data.get("teams", {}).items():
        if isinstance(raw, dict):
            teams[slug] = TeamConfig(id=raw["id"], name=raw.get("name", slug))

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


def save_config(config: Config, path: Path = DEFAULT_CONFIG_PATH) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)

    transition_lines: list[str] = []
    field_type_sections: list[str] = []
    for name, t in config.transitions.items():
        fields_str = ", ".join(f'"{f}"' for f in t.fields)
        line = f'{name} = {{ id = {t.id}, fields = [{fields_str}]'
        if t.pre_transition_id is not None:
            line += f", pre_transition_id = {t.pre_transition_id}"
            line += f", pre_transition_optional = {'true' if t.pre_transition_optional else 'false'}"
        line += " }"
        transition_lines.append(line)
        if t.field_types:
            field_type_sections.append(f"\n[transitions.{name}.field_types]")
            for fname, ftype in t.field_types.items():
                field_type_sections.append(f'{fname} = "{ftype}"')

    team_lines = [
        f'{slug} = {{ id = {t.id}, name = "{t.name}" }}'
        for slug, t in config.teams.items()
    ]

    content = (
        "[connection]\n"
        f'host       = "{config.host}"\n'
        f'username   = "{config.username}"\n'
        f'password   = "{config.password}"\n'
        f"verify_ssl = {'true' if config.verify_ssl else 'false'}\n"
        "\n[defaults]\n"
        f"table_id  = {config.table_id}\n"
        f"report_id = {config.report_id}\n"
        "\n[transitions]\n"
        + "\n".join(transition_lines)
        + "\n".join(field_type_sections)
        + "\n\n[teams]\n"
        + "\n".join(team_lines)
        + "\n"
    )
    path.write_text(content, encoding="utf-8")
