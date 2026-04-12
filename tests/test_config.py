import pytest
import tomllib
from pathlib import Path
from sbm_cli.config import (
    Config, TransitionConfig, TeamConfig,
    ConfigError, load_config, save_config, DEFAULT_CONFIG_PATH,
)

VALID_TOML = """\
[connection]
host       = "https://sbm.test"
username   = "user"
password   = "pass"
verify_ssl = false

[defaults]
table_id  = 1000
report_id = 2208

[transitions]
assign    = { id = 155, fields = ["OWNER", "3RD_LEVEL_SPECIALIST"] }
close     = { id = 19,  fields = ["RESOLUTION", "ROOT_CAUSE"], pre_transition_id = 148, pre_transition_optional = true }
return-l2 = { id = 88,  fields = ["RETURN_REASON", "RETURN_NOTE"] }

[transitions.transfer]
id     = 140
fields = ["L3_SPECIALIST_GROUP"]

[transitions.transfer.field_types]
L3_SPECIALIST_GROUP = "list"

[teams]
market-finance = { id = 155, name = "L3 SD Market Finance" }
"""


def test_load_config_parses_connection(tmp_path):
    cfg_file = tmp_path / "config.toml"
    cfg_file.write_text(VALID_TOML, encoding="utf-8")
    cfg = load_config(cfg_file)
    assert cfg.host == "https://sbm.test"
    assert cfg.username == "user"
    assert cfg.verify_ssl is False
    assert cfg.table_id == 1000
    assert cfg.report_id == 2208


def test_load_config_parses_transitions(tmp_path):
    cfg_file = tmp_path / "config.toml"
    cfg_file.write_text(VALID_TOML, encoding="utf-8")
    cfg = load_config(cfg_file)
    assert "assign" in cfg.transitions
    assert cfg.transitions["assign"].id == 155
    assert cfg.transitions["assign"].fields == ["OWNER", "3RD_LEVEL_SPECIALIST"]
    assert cfg.transitions["close"].pre_transition_id == 148
    assert cfg.transitions["close"].pre_transition_optional is True
    assert cfg.transitions["transfer"].field_types == {"L3_SPECIALIST_GROUP": "list"}


def test_load_config_parses_teams(tmp_path):
    cfg_file = tmp_path / "config.toml"
    cfg_file.write_text(VALID_TOML, encoding="utf-8")
    cfg = load_config(cfg_file)
    assert "market-finance" in cfg.teams
    assert cfg.teams["market-finance"].id == 155
    assert cfg.teams["market-finance"].name == "L3 SD Market Finance"


def test_load_config_missing_file_raises_config_error(tmp_path):
    with pytest.raises(ConfigError, match="Run 'sbm configure'"):
        load_config(tmp_path / "nonexistent.toml")


def test_load_config_missing_required_field_raises(tmp_path):
    cfg_file = tmp_path / "config.toml"
    cfg_file.write_text("[connection]\nusername = \"user\"\npassword = \"pass\"\n", encoding="utf-8")
    with pytest.raises(ConfigError, match="host"):
        load_config(cfg_file)


def test_save_and_reload_roundtrip(tmp_path):
    cfg_file = tmp_path / "config.toml"
    original = Config(
        host="https://sbm.example.com",
        username="myuser",
        password="mypass",
        verify_ssl=True,
        table_id=1000,
        report_id=2208,
        transitions={
            "assign": TransitionConfig(id=155, fields=["OWNER"]),
            "close": TransitionConfig(
                id=19, fields=["RESOLUTION", "ROOT_CAUSE"],
                pre_transition_id=148, pre_transition_optional=True,
            ),
            "transfer": TransitionConfig(
                id=140, fields=["L3_SPECIALIST_GROUP"],
                field_types={"L3_SPECIALIST_GROUP": "list"},
            ),
        },
        teams={"test-team": TeamConfig(id=99, name="Test Team")},
    )
    save_config(original, cfg_file)
    reloaded = load_config(cfg_file)
    assert reloaded.host == original.host
    assert reloaded.verify_ssl == original.verify_ssl
    assert reloaded.transitions["assign"].id == 155
    assert reloaded.transitions["close"].pre_transition_id == 148
    assert reloaded.transitions["close"].pre_transition_optional is True
    assert reloaded.transitions["transfer"].field_types == {"L3_SPECIALIST_GROUP": "list"}
    assert reloaded.teams["test-team"].name == "Test Team"


def test_save_and_reload_special_chars(tmp_path):
    cfg_file = tmp_path / "config.toml"
    cfg = Config(
        host="https://sbm.example.com",
        username="domain\\user",
        password='p@ss"word',
        verify_ssl=True,
        table_id=1000,
        report_id=0,
    )
    save_config(cfg, cfg_file)
    reloaded = load_config(cfg_file)
    assert reloaded.username == "domain\\user"
    assert reloaded.password == 'p@ss"word'


def test_save_config_invalid_transition_name_raises(tmp_path):
    cfg_file = tmp_path / "config.toml"
    cfg = Config(
        host="https://sbm.example.com",
        username="user",
        password="pass",
        verify_ssl=True,
        table_id=1000,
        report_id=0,
        transitions={"bad.name": TransitionConfig(id=1)},
    )
    with pytest.raises(ConfigError, match="Invalid key"):
        save_config(cfg, cfg_file)


def test_save_config_invalid_field_type_key_raises(tmp_path):
    cfg_file = tmp_path / "config.toml"
    cfg = Config(
        host="https://sbm.example.com",
        username="user",
        password="pass",
        verify_ssl=True,
        table_id=1000,
        report_id=0,
        transitions={
            "assign": TransitionConfig(id=1, field_types={"bad key": "list"}),
        },
    )
    with pytest.raises(ConfigError, match="Invalid key"):
        save_config(cfg, cfg_file)


def test_pre_transition_optional_without_id_roundtrip(tmp_path):
    cfg_file = tmp_path / "config.toml"
    cfg = Config(
        host="https://sbm.example.com",
        username="user",
        password="pass",
        verify_ssl=True,
        table_id=1000,
        report_id=0,
        transitions={
            "mytr": TransitionConfig(id=5, pre_transition_optional=True),
        },
    )
    save_config(cfg, cfg_file)
    reloaded = load_config(cfg_file)
    assert reloaded.transitions["mytr"].pre_transition_optional is True
    assert reloaded.transitions["mytr"].pre_transition_id is None
