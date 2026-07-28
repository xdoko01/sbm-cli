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
verify_ssl = false

[defaults]
table_id  = 1000
report_ids = [2208]

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
    assert cfg.report_ids == [2208]


def test_load_config_parses_report_ids_list(tmp_path):
    toml = """\
[connection]
host = "https://sbm.test"
username = "u"
verify_ssl = false

[defaults]
table_id = 1000
report_ids = [2208, 2209, 2210]
"""
    path = tmp_path / "config.toml"
    path.write_text(toml, encoding="utf-8")
    cfg = load_config(path)
    assert cfg.report_ids == [2208, 2209, 2210]


def test_load_config_migrates_legacy_report_id(tmp_path):
    toml = """\
[connection]
host = "https://sbm.test"
username = "u"
verify_ssl = false

[defaults]
table_id = 1000
report_id = 2208
"""
    path = tmp_path / "config.toml"
    path.write_text(toml, encoding="utf-8")
    cfg = load_config(path)
    assert cfg.report_ids == [2208]


def test_load_config_legacy_report_id_zero_becomes_empty(tmp_path):
    toml = """\
[connection]
host = "https://sbm.test"
username = "u"
verify_ssl = false

[defaults]
table_id = 1000
report_id = 0
"""
    path = tmp_path / "config.toml"
    path.write_text(toml, encoding="utf-8")
    cfg = load_config(path)
    assert cfg.report_ids == []


def test_save_config_round_trips_report_ids(tmp_path):
    cfg = Config(host="https://sbm.test", username="u", verify_ssl=False,
                 table_id=1000, report_ids=[2208, 2209])
    path = tmp_path / "config.toml"
    save_config(cfg, path)
    loaded = load_config(path)
    assert loaded.report_ids == [2208, 2209]


def test_save_config_empty_report_ids_omits_key(tmp_path):
    cfg = Config(host="https://sbm.test", username="u", verify_ssl=False,
                 table_id=1000, report_ids=[])
    path = tmp_path / "config.toml"
    save_config(cfg, path)
    content = path.read_text()
    assert "report_id" not in content


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
    cfg_file.write_text("[connection]\nusername = \"user\"\n", encoding="utf-8")
    with pytest.raises(ConfigError, match="host"):
        load_config(cfg_file)


def test_save_and_reload_roundtrip(tmp_path):
    cfg_file = tmp_path / "config.toml"
    original = Config(
        host="https://sbm.example.com",
        username="myuser",
        verify_ssl=True,
        table_id=1000,
        report_ids=[2208],
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
        verify_ssl=True,
        table_id=1000,
        report_ids=[],
    )
    save_config(cfg, cfg_file)
    reloaded = load_config(cfg_file)
    assert reloaded.username == "domain\\user"


def test_save_config_invalid_transition_name_raises(tmp_path):
    cfg_file = tmp_path / "config.toml"
    cfg = Config(
        host="https://sbm.example.com",
        username="user",
        verify_ssl=True,
        table_id=1000,
        report_ids=[],
        transitions={"bad.name": TransitionConfig(id=1)},
    )
    with pytest.raises(ConfigError, match="Invalid key"):
        save_config(cfg, cfg_file)


def test_save_config_invalid_field_type_key_raises(tmp_path):
    cfg_file = tmp_path / "config.toml"
    cfg = Config(
        host="https://sbm.example.com",
        username="user",
        verify_ssl=True,
        table_id=1000,
        report_ids=[],
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
        verify_ssl=True,
        table_id=1000,
        report_ids=[],
        transitions={
            "mytr": TransitionConfig(id=5, pre_transition_optional=True),
        },
    )
    save_config(cfg, cfg_file)
    reloaded = load_config(cfg_file)
    assert reloaded.transitions["mytr"].pre_transition_optional is True
    assert reloaded.transitions["mytr"].pre_transition_id is None


def test_load_config_parses_users(tmp_path):
    from sbm_cli.config import UserConfig
    toml_content = """\
[connection]
host = "https://sbm.test"
username = "u"
verify_ssl = false

[defaults]
table_id = 1000
report_ids = []

[users]
alice = { id = 316 }
"jaroslav.burget" = { id = 15399 }
"""
    path = tmp_path / "config.toml"
    path.write_text(toml_content, encoding="utf-8")
    config = load_config(path)
    assert "alice" in config.users
    assert config.users["alice"].id == 316
    assert "jaroslav.burget" in config.users
    assert config.users["jaroslav.burget"].id == 15399


def test_save_config_round_trips_users(tmp_path):
    from sbm_cli.config import UserConfig
    config = Config(
        host="https://sbm.test", username="u",
        verify_ssl=False, table_id=1000, report_ids=[],
        users={
            "alice": UserConfig(id=316),
            "jaroslav.burget": UserConfig(id=15399),
        },
    )
    path = tmp_path / "config.toml"
    save_config(config, path)
    loaded = load_config(path)
    assert loaded.users["alice"].id == 316
    assert loaded.users["jaroslav.burget"].id == 15399


def test_load_config_parses_fields(tmp_path):
    from sbm_cli.config import FieldDef
    toml_content = """\
[connection]
host = "https://sbm.test"
username = "u"
verify_ssl = false

[defaults]
table_id = 1000
report_ids = []

[fields]
TITLE = { type = "text", label = "Title" }
OWNER = { type = "relational", label = "Owner" }
"""
    path = tmp_path / "config.toml"
    path.write_text(toml_content, encoding="utf-8")
    config = load_config(path)
    assert "TITLE" in config.fields
    assert config.fields["TITLE"].type == "text"
    assert config.fields["TITLE"].label == "Title"
    assert "OWNER" in config.fields
    assert config.fields["OWNER"].type == "relational"


def test_save_config_round_trips_fields(tmp_path):
    from sbm_cli.config import FieldDef
    config = Config(
        host="https://sbm.test", username="u",
        verify_ssl=False, table_id=1000, report_ids=[],
        fields={
            "TITLE": FieldDef(dbname="TITLE", type="text", label="Title"),
            "OWNER": FieldDef(dbname="OWNER", type="relational", label="Owner"),
        },
    )
    path = tmp_path / "config.toml"
    save_config(config, path)
    loaded = load_config(path)
    assert loaded.fields["TITLE"].type == "text"
    assert loaded.fields["TITLE"].label == "Title"
    assert loaded.fields["OWNER"].type == "relational"
    assert loaded.fields["OWNER"].label == "Owner"


def test_load_config_parses_list_fields(tmp_path):
    toml = """\
[connection]
host = "https://sbm.test"
username = "u"
verify_ssl = false

[defaults]
table_id = 1000
report_ids = []
list_fields = ["TITLE", "STATE", "FUNCTIONALITY", "URGENCY"]
"""
    path = tmp_path / "config.toml"
    path.write_text(toml, encoding="utf-8")
    cfg = load_config(path)
    assert cfg.list_fields == ["TITLE", "STATE", "FUNCTIONALITY", "URGENCY"]


def test_load_config_no_list_fields_returns_empty_list(tmp_path):
    path = tmp_path / "config.toml"
    path.write_text(VALID_TOML, encoding="utf-8")
    cfg = load_config(path)
    assert cfg.list_fields == []


def test_save_config_round_trips_list_fields(tmp_path):
    cfg = Config(
        host="https://sbm.test", username="u",
        verify_ssl=False, table_id=1000, report_ids=[],
        list_fields=["TITLE", "FUNCTIONALITY", "URGENCY"],
    )
    path = tmp_path / "config.toml"
    save_config(cfg, path)
    loaded = load_config(path)
    assert loaded.list_fields == ["TITLE", "FUNCTIONALITY", "URGENCY"]


def test_save_config_empty_list_fields_omits_key(tmp_path):
    cfg = Config(
        host="https://sbm.test", username="u",
        verify_ssl=False, table_id=1000, report_ids=[],
        list_fields=[],
    )
    path = tmp_path / "config.toml"
    save_config(cfg, path)
    content = path.read_text()
    assert "list_fields" not in content


def test_load_config_no_password_required(tmp_path, mocker):
    mocker.patch("sbm_cli.credentials.set_password")
    toml_content = """\
[connection]
host     = "https://sbm.test"
username = "user"
verify_ssl = false

[defaults]
table_id  = 1000
report_ids = []
"""
    path = tmp_path / "config.toml"
    path.write_text(toml_content, encoding="utf-8")
    config = load_config(path)
    assert config.host == "https://sbm.test"
    assert config.username == "user"


def test_save_config_does_not_write_password(tmp_path):
    config = Config(
        host="https://sbm.test", username="user",
        verify_ssl=False, table_id=1000, report_ids=[],
    )
    path = tmp_path / "config.toml"
    save_config(config, path)
    content = path.read_text()
    assert "password" not in content


def test_load_config_migrates_plaintext_password(tmp_path, mocker):
    set_pw = mocker.patch("sbm_cli.credentials.set_password")
    cfg_file = tmp_path / "config.toml"
    cfg_file.write_text("""\
[connection]
host     = "https://sbm.test"
username = "user"
password = "oldpass"
verify_ssl = false

[defaults]
table_id  = 1000
report_ids = []
""", encoding="utf-8")
    config = load_config(cfg_file)
    set_pw.assert_called_once_with("https://sbm.test", "user", "oldpass")
    content = cfg_file.read_text()
    assert "password" not in content
    assert "oldpass" not in content
    assert config.host == "https://sbm.test"


def test_load_config_no_migration_when_no_password(tmp_path, mocker):
    set_pw = mocker.patch("sbm_cli.credentials.set_password")
    path = tmp_path / "config.toml"
    path.write_text(VALID_TOML, encoding="utf-8")
    load_config(path)
    set_pw.assert_not_called()


def test_load_config_parses_optional_fields(tmp_path):
    toml = """\
[connection]
host       = "https://sbm.test"
username   = "user"
verify_ssl = false

[defaults]
table_id  = 1000
report_ids = []

[transitions.assign]
id              = 155
fields          = ["OWNER", "3RD_LEVEL_SPECIALIST"]
optional_fields = ["SOLUTION_STEPS"]
"""
    cfg_file = tmp_path / "config.toml"
    cfg_file.write_text(toml, encoding="utf-8")
    cfg = load_config(cfg_file)
    assert cfg.transitions["assign"].optional_fields == ["SOLUTION_STEPS"]


def test_load_config_optional_fields_defaults_to_empty(tmp_path):
    toml = """\
[connection]
host       = "https://sbm.test"
username   = "user"
verify_ssl = false

[defaults]
table_id  = 1000
report_ids = []

[transitions]
assign = { id = 155, fields = ["OWNER"] }
"""
    cfg_file = tmp_path / "config.toml"
    cfg_file.write_text(toml, encoding="utf-8")
    cfg = load_config(cfg_file)
    assert cfg.transitions["assign"].optional_fields == []


def test_save_and_reload_roundtrip_optional_fields(tmp_path):
    cfg = Config(
        host="https://sbm.test", username="user", verify_ssl=False,
        table_id=1000, report_ids=[],
        transitions={
            "assign": TransitionConfig(
                id=155,
                fields=["OWNER"],
                optional_fields=["SOLUTION_STEPS"],
            )
        },
    )
    path = tmp_path / "config.toml"
    save_config(cfg, path)
    reloaded = load_config(path)
    assert reloaded.transitions["assign"].optional_fields == ["SOLUTION_STEPS"]


def test_load_config_migration_skipped_when_no_keyring(tmp_path, mocker, capsys):
    """When set_password raises NoKeyringAvailable, config is NOT rewritten and a warning is printed."""
    from sbm_cli.credentials import NoKeyringAvailable
    mocker.patch(
        "sbm_cli.credentials.set_password",
        side_effect=NoKeyringAvailable("no daemon"),
    )
    mock_save = mocker.patch("sbm_cli.config.save_config")
    cfg_file = tmp_path / "config.toml"
    cfg_file.write_text("""\
[connection]
host     = "https://sbm.test"
username = "user"
password = "oldpass"
verify_ssl = false

[defaults]
table_id  = 1000
report_ids = []
""", encoding="utf-8")
    config = load_config(cfg_file)
    captured = capsys.readouterr()
    # save_config must NOT have been called (password stays in file)
    mock_save.assert_not_called()
    # A warning about keyring was printed to stderr
    assert "keyring" in captured.err.lower()
    # Config was still returned correctly
    assert config.host == "https://sbm.test"


# ---------------------------------------------------------------------------
# dump_config
# ---------------------------------------------------------------------------

def test_dump_config_matches_save_config(tmp_path, sample_config):
    from sbm_cli.config import dump_config
    path = tmp_path / "config.toml"
    save_config(sample_config, path)
    assert dump_config(sample_config) == path.read_text(encoding="utf-8")


def test_dump_config_round_trips(tmp_path, sample_config):
    """dump -> load preserves every section."""
    from sbm_cli.config import dump_config
    path = tmp_path / "config.toml"
    path.write_text(dump_config(sample_config), encoding="utf-8")
    loaded = load_config(path)
    assert loaded.host == sample_config.host
    assert loaded.username == sample_config.username
    assert loaded.verify_ssl == sample_config.verify_ssl
    assert loaded.table_id == sample_config.table_id
    assert loaded.report_ids == sample_config.report_ids
    assert set(loaded.transitions) == set(sample_config.transitions)
    assert loaded.transitions["transfer"].field_types == {"L3_SPECIALIST_GROUP": "list"}
    assert loaded.transitions["close"].pre_transition_id == 148
    assert loaded.teams["my-team"].name == "L3 Example Team"


def test_dump_config_contains_no_password_key(sample_config):
    """Config has no password field, so exported TOML structurally cannot leak one."""
    from sbm_cli.config import dump_config
    assert "password" not in dump_config(sample_config).lower()
