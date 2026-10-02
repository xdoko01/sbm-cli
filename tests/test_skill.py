"""Keep the bundled Claude Code skill (skills/sbm-cli) in sync with the code.

Each test names the file to fix when it fails. The command reference is
generated: regenerate it with `uv run python scripts/gen_skill_reference.py`.
"""
import dataclasses
import importlib.util
import json
import re
import tomllib
from pathlib import Path

import click
import pytest

from sbm_cli import cli, config, credentials

REPO_ROOT = Path(__file__).resolve().parent.parent
SKILL_DIR = REPO_ROOT / "skills" / "sbm-cli"
SKILL_MD = (SKILL_DIR / "SKILL.md").read_text(encoding="utf-8")
CONFIG_MD = (SKILL_DIR / "references" / "config.md").read_text(encoding="utf-8")


def _load_generator():
    spec = importlib.util.spec_from_file_location(
        "gen_skill_reference", REPO_ROOT / "scripts" / "gen_skill_reference.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _command_paths(group: click.Group, prefix: str = "sbm") -> list[str]:
    paths = []
    for name, cmd in group.commands.items():
        if cmd.hidden:
            continue
        path = f"{prefix} {name}"
        if isinstance(cmd, click.Group) and cmd.commands:
            paths += _command_paths(cmd, path)
        else:
            paths.append(path)
    return paths


def _pyproject_version() -> str:
    with open(REPO_ROOT / "pyproject.toml", "rb") as fh:
        return tomllib.load(fh)["project"]["version"]


def test_command_reference_is_up_to_date():
    generator = _load_generator()
    current = generator.REFERENCE_PATH.read_text(encoding="utf-8")
    assert current == generator.render(), (
        "skills/sbm-cli/references/commands.md is stale — "
        "run: uv run python scripts/gen_skill_reference.py")


def test_plugin_version_matches_package():
    manifest = json.loads((REPO_ROOT / ".claude-plugin" / "plugin.json").read_text("utf-8"))
    assert manifest["version"] == _pyproject_version(), (
        "bump .claude-plugin/plugin.json 'version' to match pyproject.toml")


@pytest.mark.parametrize("doc", ["README.md", "docs/manual.md"])
def test_docs_show_plugin_install_commands(doc):
    marketplace = json.loads(
        (REPO_ROOT / ".claude-plugin" / "marketplace.json").read_text("utf-8"))
    plugin = marketplace["plugins"][0]["name"]
    text = (REPO_ROOT / doc).read_text(encoding="utf-8")
    for command in (f"plugin marketplace add xdoko01/{marketplace['name']}",
                    f"plugin install {plugin}@{marketplace['name']}",
                    f"plugin update {plugin}@{marketplace['name']}"):
        assert command in text, f"{doc} must show `{command}`"
    assert "skills/sbm-cli/" in text, f"{doc} must explain copying skills/sbm-cli/ for other assistants"
    assert "git clone https://github.com/xdoko01/sbm-cli.git" in text, (
        f"{doc} must explain how to get the repo with the skill")


def test_skill_is_assistant_neutral():
    assert "Claude" not in SKILL_MD, "keep SKILL.md usable by any AI assistant"


def test_skill_frontmatter():
    match = re.match(r"---\n(.*?)\n---\n", SKILL_MD, re.DOTALL)
    assert match, "SKILL.md must start with YAML frontmatter"
    meta = dict(line.split(": ", 1) for line in match.group(1).splitlines())
    assert meta["name"] == SKILL_DIR.name
    assert 0 < len(meta["description"]) <= 1024


def test_skill_relative_links_resolve():
    for target in re.findall(r"\]\(([^)#:]+)(?:#[^)]*)?\)", SKILL_MD):
        assert (SKILL_DIR / target).exists(), f"SKILL.md links to missing {target}"


@pytest.mark.parametrize("path", _command_paths(cli.main))
def test_skill_mentions_every_command(path):
    assert path in SKILL_MD, f"SKILL.md never mentions `{path}` — document it"


@pytest.mark.parametrize("opt", [
    o for p in cli.main.params if isinstance(p, click.Option) for o in p.opts
])
def test_skill_mentions_every_global_flag(opt):
    assert opt in SKILL_MD, f"SKILL.md never mentions global flag {opt}"


@pytest.mark.parametrize("var", [credentials.PASSWORD_ENV_VAR, cli.CONFIG_ENV_VAR])
def test_skill_mentions_env_vars(var):
    assert var in SKILL_MD, f"SKILL.md never mentions {var}"


def _error_types() -> set[str]:
    source = Path(cli.__file__).read_text(encoding="utf-8")
    return set(re.findall(r'\.error\(\s*"[^"]*",\s*"([a-z_]+)"', source))


def test_error_types_are_discovered():
    assert {"api_error", "auth_error", "config_error", "validation_error"} <= _error_types()


@pytest.mark.parametrize("error_type", sorted(_error_types()))
def test_skill_troubleshoots_every_error_type(error_type):
    assert f"`{error_type}" in SKILL_MD, (
        f"SKILL.md Troubleshooting has no entry for {error_type}")


def _config_keys() -> set[str]:
    """Every key `dump_config` can write, for a config with every option set."""
    sample = config.Config(
        host="https://h", username="u", verify_ssl=False, table_id=1,
        report_ids=[1], list_fields=["TITLE"],
        transitions={"t": config.TransitionConfig(
            id=1, fields=["A"], optional_fields=["B"], field_types={"A": "list"},
            pre_transition_id=2, pre_transition_optional=True)},
        teams={"team": config.TeamConfig(id=1, name="n")},
        users={"user": config.UserConfig(id=1)},
        fields={"F": config.FieldDef(dbname="F", type="text", label="l")},
    )
    data = tomllib.loads(config.dump_config(sample))
    keys = set(data) | set(data["connection"]) | set(data["defaults"])
    for section in ("transitions", "teams", "users", "fields"):
        for entry in data[section].values():
            keys |= set(entry)
    keys |= {f.name for f in dataclasses.fields(config.TransitionConfig)}
    return keys


@pytest.mark.parametrize("key", sorted(_config_keys()))
def test_config_reference_covers_every_key(key):
    assert re.search(rf"\b{re.escape(key)}\b", CONFIG_MD), (
        f"skills/sbm-cli/references/config.md never mentions config key '{key}'")
