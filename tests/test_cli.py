import json
import pytest
from pathlib import Path
from click.testing import CliRunner
from unittest.mock import MagicMock, patch
from sbm_cli.cli import main
from sbm_cli.config import Config, TransitionConfig, TeamConfig
from sbm_cli.client import SBMError


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_app_config() -> Config:
    return Config(
        host="https://sbm.test",
        username="user",
        verify_ssl=False,
        table_id=1000,
        report_ids=[2208],
        transitions={
            "assign": TransitionConfig(id=155, fields=["OWNER", "3RD_LEVEL_SPECIALIST"]),
            "close": TransitionConfig(
                id=19, fields=["RESOLUTION", "ROOT_CAUSE"],
                pre_transition_id=148, pre_transition_optional=True,
            ),
            "return-l2": TransitionConfig(id=88, fields=["RETURN_REASON", "RETURN_NOTE"]),
            "transfer": TransitionConfig(
                id=140, fields=["L3_SPECIALIST_GROUP"],
                field_types={"L3_SPECIALIST_GROUP": "list"},
            ),
        },
        teams={"my-team": TeamConfig(id=155, name="L3 Example Team")},
    )


def _invoke(runner: CliRunner, args: list[str], config: Config | None = None) -> object:
    """Invoke CLI with config pre-loaded via monkeypatching load_config."""
    cfg = config or _make_app_config()
    with patch("sbm_cli.cli.load_config", return_value=cfg):
        return runner.invoke(main, args, catch_exceptions=False)


# ---------------------------------------------------------------------------
# schema
# ---------------------------------------------------------------------------

def test_schema_outputs_json(runner: CliRunner):
    result = _invoke(runner, ["schema"])
    assert result.exit_code == 0
    data = json.loads(result.stdout)
    assert data["ok"] is True
    assert data["command"] == "schema"
    assert "assign" in data["data"]["transitions"]
    assert data["data"]["transitions"]["assign"]["id"] == 155


def test_schema_reports_report_ids(runner: CliRunner):
    cfg = _make_app_config()
    cfg.report_ids = [2208, 2209]
    result = _invoke(runner, ["schema"], config=cfg)
    data = json.loads(result.stdout)
    assert data["data"]["defaults"]["report_ids"] == [2208, 2209]


def test_schema_pretty(runner: CliRunner):
    result = _invoke(runner, ["--pretty", "schema"])
    assert result.exit_code == 0
    assert "assign" in result.output
    assert "155" in result.output


def test_schema_json_includes_optional_fields(runner: CliRunner):
    config = _make_app_config()
    config.transitions["assign"] = TransitionConfig(
        id=155, fields=["OWNER", "3RD_LEVEL_SPECIALIST"],
        optional_fields=["SOLUTION_STEPS"],
    )
    result = _invoke(runner, ["schema"], config=config)
    assert result.exit_code == 0
    data = json.loads(result.stdout)
    assign = data["data"]["transitions"]["assign"]
    assert assign["optional_fields"] == ["SOLUTION_STEPS"]


def test_schema_json_omits_optional_fields_when_empty(runner: CliRunner):
    result = _invoke(runner, ["schema"])
    assert result.exit_code == 0
    data = json.loads(result.stdout)
    assign = data["data"]["transitions"]["assign"]
    assert "optional_fields" not in assign


def test_schema_pretty_shows_optional_fields(runner: CliRunner):
    config = _make_app_config()
    config.transitions["assign"] = TransitionConfig(
        id=155, fields=["OWNER", "3RD_LEVEL_SPECIALIST"],
        optional_fields=["SOLUTION_STEPS"],
    )
    result = _invoke(runner, ["--pretty", "schema"], config=config)
    assert result.exit_code == 0
    assert "optional: SOLUTION_STEPS" in result.output


def test_schema_pretty_omits_optional_when_empty(runner: CliRunner):
    result = _invoke(runner, ["--pretty", "schema"])
    assert result.exit_code == 0
    assert "optional:" not in result.output


# ---------------------------------------------------------------------------
# teams
# ---------------------------------------------------------------------------

def test_teams_outputs_json(runner: CliRunner):
    result = _invoke(runner, ["teams"])
    assert result.exit_code == 0
    data = json.loads(result.stdout)
    assert data["ok"] is True
    assert "my-team" in data["data"]
    assert data["data"]["my-team"]["id"] == 155


def test_teams_pretty(runner: CliRunner):
    result = _invoke(runner, ["--pretty", "teams"])
    assert result.exit_code == 0
    assert "my-team" in result.output


# ---------------------------------------------------------------------------
# missing config
# ---------------------------------------------------------------------------

def test_missing_config_returns_config_error(runner: CliRunner):
    from sbm_cli.config import ConfigError
    with patch("sbm_cli.cli.load_config", side_effect=ConfigError("not found")):
        result = runner.invoke(main, ["schema"], catch_exceptions=False)
    assert result.exit_code == 2
    data = json.loads(result.stdout)
    assert data["ok"] is False
    assert data["error"]["type"] == "config_error"


# ---------------------------------------------------------------------------
# list
# ---------------------------------------------------------------------------

def test_list_returns_json(runner: CliRunner):
    mock_items = [
        {"id": {"id": 1, "itemIdPrefixed": "0001"},
         "fields": {"TITLE": {"value": "Ticket 1"}, "STATE": {"value": "Open"}}}
    ]
    with patch("sbm_cli.cli.load_config", return_value=_make_app_config()):
        with patch("sbm_cli.cli.SBMClient") as MockClient:
            MockClient.return_value.list_items_by_report.return_value = mock_items
            result = runner.invoke(main, ["list"], catch_exceptions=False)
    assert result.exit_code == 0
    data = json.loads(result.stdout)
    assert data["ok"] is True
    assert data["command"] == "list"
    assert len(data["data"]) == 1


def test_list_uses_default_report(runner: CliRunner):
    with patch("sbm_cli.cli.load_config", return_value=_make_app_config()):
        with patch("sbm_cli.cli.SBMClient") as MockClient:
            MockClient.return_value.list_items_by_report.return_value = []
            runner.invoke(main, ["list"], catch_exceptions=False)
            # Just verify it was called with the configured report id 2208
            call_args = MockClient.return_value.list_items_by_report.call_args
            assert call_args[0][0] == 2208


def test_list_with_explicit_report(runner: CliRunner):
    with patch("sbm_cli.cli.load_config", return_value=_make_app_config()):
        with patch("sbm_cli.cli.SBMClient") as MockClient:
            MockClient.return_value.list_items_by_report.return_value = []
            runner.invoke(main, ["list", "--report", "9999"], catch_exceptions=False)
            call_args = MockClient.return_value.list_items_by_report.call_args
            assert call_args[0][0] == 9999


def test_list_with_filter(runner: CliRunner):
    with patch("sbm_cli.cli.load_config", return_value=_make_app_config()):
        with patch("sbm_cli.cli.SBMClient") as MockClient:
            MockClient.return_value.list_items_by_filter.return_value = []
            runner.invoke(main, ["list", "--filter", "36"], catch_exceptions=False)
            MockClient.return_value.list_items_by_filter.assert_called_once()
            call_args = MockClient.return_value.list_items_by_filter.call_args
            assert call_args[0][0] == "36"


def test_list_api_error(runner: CliRunner):
    with patch("sbm_cli.cli.load_config", return_value=_make_app_config()):
        with patch("sbm_cli.cli.SBMClient") as MockClient:
            MockClient.return_value.list_items_by_report.side_effect = SBMError("forbidden")
            result = runner.invoke(main, ["list"], catch_exceptions=False)
    assert result.exit_code == 1
    data = json.loads(result.stdout)
    assert data["ok"] is False
    assert data["error"]["type"] == "api_error"


def test_list_auth_error(runner: CliRunner):
    with patch("sbm_cli.cli.load_config", return_value=_make_app_config()):
        with patch("sbm_cli.cli.SBMClient") as MockClient:
            MockClient.return_value.list_items_by_report.side_effect = PermissionError("401")
            result = runner.invoke(main, ["list"], catch_exceptions=False)
    assert result.exit_code == 2
    data = json.loads(result.stdout)
    assert data["error"]["type"] == "auth_error"


def test_list_merges_and_dedups_multiple_reports(runner: CliRunner):
    cfg = _make_app_config()
    cfg.report_ids = [2208, 2209]

    def by_report(rid, fields=None, **kw):
        if rid == 2208:
            return [{"id": {"id": 1}}, {"id": {"id": 2}}]
        return [{"id": {"id": 2}}, {"id": {"id": 3}}]

    with patch("sbm_cli.cli.load_config", return_value=cfg):
        with patch("sbm_cli.cli.SBMClient") as MockClient:
            MockClient.return_value.list_items_by_report.side_effect = by_report
            result = runner.invoke(main, ["list"], catch_exceptions=False)
    assert result.exit_code == 0
    data = json.loads(result.stdout)
    ids = [i["id"]["id"] for i in data["data"]]
    assert ids == [1, 2, 3]


def test_list_multiple_report_flags_override_config(runner: CliRunner):
    cfg = _make_app_config()
    cfg.report_ids = [2208]
    with patch("sbm_cli.cli.load_config", return_value=cfg):
        with patch("sbm_cli.cli.SBMClient") as MockClient:
            MockClient.return_value.list_items_by_report.return_value = []
            runner.invoke(main, ["list", "--report", "10", "--report", "20"],
                          catch_exceptions=False)
            called = [c[0][0] for c in
                      MockClient.return_value.list_items_by_report.call_args_list]
    assert called == [10, 20]


def test_list_best_effort_skips_failing_report(runner: CliRunner):
    cfg = _make_app_config()
    cfg.report_ids = [2208, 2209]

    def by_report(rid, fields=None, **kw):
        if rid == 2209:
            raise SBMError("bad report")
        return [{"id": {"id": 1}}]

    with patch("sbm_cli.cli.load_config", return_value=cfg):
        with patch("sbm_cli.cli.SBMClient") as MockClient:
            MockClient.return_value.list_items_by_report.side_effect = by_report
            result = runner.invoke(main, ["list"], catch_exceptions=False)
    assert result.exit_code == 0
    data = json.loads(result.stdout)
    assert [i["id"]["id"] for i in data["data"]] == [1]
    assert "Warning" in result.output and "2209" in result.output


def test_list_all_reports_fail_returns_api_error(runner: CliRunner):
    cfg = _make_app_config()
    cfg.report_ids = [2208, 2209]
    with patch("sbm_cli.cli.load_config", return_value=cfg):
        with patch("sbm_cli.cli.SBMClient") as MockClient:
            MockClient.return_value.list_items_by_report.side_effect = SBMError("nope")
            result = runner.invoke(main, ["list"], catch_exceptions=False)
    assert result.exit_code == 1
    data = json.loads(result.stdout)
    assert data["error"]["type"] == "api_error"


def test_list_no_reports_configured_returns_config_error(runner: CliRunner):
    cfg = _make_app_config()
    cfg.report_ids = []
    with patch("sbm_cli.cli.load_config", return_value=cfg):
        with patch("sbm_cli.cli.SBMClient") as MockClient:
            MockClient.return_value.list_items_by_report.return_value = []
            result = runner.invoke(main, ["list"], catch_exceptions=False)
    assert result.exit_code == 2
    data = json.loads(result.stdout)
    assert data["error"]["type"] == "config_error"


# ---------------------------------------------------------------------------
# get
# ---------------------------------------------------------------------------

def test_get_returns_ticket(runner: CliRunner):
    mock_data = {
        "item": {"id": {"id": 100, "itemIdPrefixed": "02440942"},
                 "fields": {"TITLE": {"value": "Test"}}},
        "result": {"type": "OK"},
    }
    with patch("sbm_cli.cli.load_config", return_value=_make_app_config()):
        with patch("sbm_cli.cli.SBMClient") as MockClient:
            MockClient.return_value.get_item_by_display_id.return_value = mock_data
            result = runner.invoke(main, ["get", "02440942"], catch_exceptions=False)
    assert result.exit_code == 0
    data = json.loads(result.stdout)
    assert data["ok"] is True
    assert data["command"] == "get"
    assert data["data"]["id"]["itemIdPrefixed"] == "02440942"


def test_get_not_found(runner: CliRunner):
    with patch("sbm_cli.cli.load_config", return_value=_make_app_config()):
        with patch("sbm_cli.cli.SBMClient") as MockClient:
            MockClient.return_value.get_item_by_display_id.side_effect = ValueError("No item found")
            result = runner.invoke(main, ["get", "9999999"], catch_exceptions=False)
    assert result.exit_code == 1
    data = json.loads(result.stdout)
    assert data["ok"] is False
    assert "No item found" in data["error"]["message"]


def test_get_auth_error(runner: CliRunner):
    with patch("sbm_cli.cli.load_config", return_value=_make_app_config()):
        with patch("sbm_cli.cli.SBMClient") as MockClient:
            MockClient.return_value.get_item_by_display_id.side_effect = PermissionError("401")
            result = runner.invoke(main, ["get", "02440942"], catch_exceptions=False)
    assert result.exit_code == 2
    data = json.loads(result.stdout)
    assert data["error"]["type"] == "auth_error"


# ---------------------------------------------------------------------------
# transition (named)
# ---------------------------------------------------------------------------

def _mock_transition(MockClient, lock_id: int = 42) -> None:
    """Configure mock client for a successful transition flow."""
    MockClient.return_value.get_item_by_display_id.return_value = {
        "item": {"id": {"id": 100, "itemIdPrefixed": "02440942"}, "fields": {}},
        "result": {"type": "OK"},
    }
    MockClient.return_value.start_transition.return_value = lock_id
    MockClient.return_value.update_item.return_value = {
        "item": {"id": {"id": 100}}, "result": {"type": "OK"}
    }


def test_transition_assign_success(runner: CliRunner):
    with patch("sbm_cli.cli.load_config", return_value=_make_app_config()):
        with patch("sbm_cli.cli.SBMClient") as MockClient:
            _mock_transition(MockClient)
            result = runner.invoke(
                main,
                ["transition", "assign", "02440942",
                 "--field", "OWNER=316", "--field", "3RD_LEVEL_SPECIALIST=316"],
                catch_exceptions=False,
            )
    assert result.exit_code == 0
    data = json.loads(result.stdout)
    assert data["ok"] is True
    assert data["command"] == "transition"
    # Verify start_transition was called with transition id=155
    MockClient.return_value.start_transition.assert_called_once_with(1000, 100, 155, break_lock=True)
    # Verify update_item was called with correct field values
    call_kwargs = MockClient.return_value.update_item.call_args[1]
    assert call_kwargs["transition_id"] == 155
    assert call_kwargs["field_values"]["OWNER"] == 316


def test_transition_missing_required_field(runner: CliRunner):
    with patch("sbm_cli.cli.load_config", return_value=_make_app_config()):
        with patch("sbm_cli.cli.SBMClient"):
            result = runner.invoke(
                main,
                ["transition", "assign", "02440942", "--field", "OWNER=316"],
                # Missing 3RD_LEVEL_SPECIALIST
                catch_exceptions=False,
            )
    assert result.exit_code == 3
    data = json.loads(result.stdout)
    assert data["ok"] is False
    assert data["error"]["type"] == "validation_error"
    assert "3RD_LEVEL_SPECIALIST" in data["error"]["message"]


def test_transition_unknown_name(runner: CliRunner):
    with patch("sbm_cli.cli.load_config", return_value=_make_app_config()):
        with patch("sbm_cli.cli.SBMClient"):
            result = runner.invoke(
                main, ["transition", "foobar", "02440942"],
                catch_exceptions=False,
            )
    assert result.exit_code == 2
    data = json.loads(result.stdout)
    assert data["error"]["type"] == "config_error"


def test_transition_transfer_wraps_list_field(runner: CliRunner):
    with patch("sbm_cli.cli.load_config", return_value=_make_app_config()):
        with patch("sbm_cli.cli.SBMClient") as MockClient:
            _mock_transition(MockClient)
            runner.invoke(
                main,
                ["transition", "transfer", "02440942",
                 "--field", "L3_SPECIALIST_GROUP=155"],
                catch_exceptions=False,
            )
    call_kwargs = MockClient.return_value.update_item.call_args[1]
    assert call_kwargs["field_values"]["L3_SPECIALIST_GROUP"] == [155]


def test_transition_close_runs_pre_transition(runner: CliRunner):
    """close has pre_transition_id=148 — must call start_transition + update_item twice."""
    with patch("sbm_cli.cli.load_config", return_value=_make_app_config()):
        with patch("sbm_cli.cli.SBMClient") as MockClient:
            _mock_transition(MockClient)
            runner.invoke(
                main,
                ["transition", "close", "02440942",
                 "--field", "RESOLUTION=Fixed", "--field", "ROOT_CAUSE=1701"],
                catch_exceptions=False,
            )
    # start_transition called twice: once for pre (148), once for main (19)
    assert MockClient.return_value.start_transition.call_count == 2
    ids_called = [c[0][2] for c in MockClient.return_value.start_transition.call_args_list]
    assert 148 in ids_called
    assert 19 in ids_called


def test_transition_close_pre_transition_failure_is_ignored(runner: CliRunner):
    """If pre_transition_optional=True, SBMError from pre-transition is ignored."""
    with patch("sbm_cli.cli.load_config", return_value=_make_app_config()):
        with patch("sbm_cli.cli.SBMClient") as MockClient:
            mock_client = MockClient.return_value
            mock_client.get_item_by_display_id.return_value = {
                "item": {"id": {"id": 100, "itemIdPrefixed": "02440942"}, "fields": {}},
                "result": {"type": "OK"},
            }
            # Pre-transition fails (ticket already in solving state)
            mock_client.start_transition.side_effect = [
                SBMError("privilege denied"),  # pre-transition fails
                42,                            # main transition succeeds
            ]
            mock_client.update_item.return_value = {
                "item": {"id": {"id": 100}}, "result": {"type": "OK"}
            }
            result = runner.invoke(
                main,
                ["transition", "close", "02440942",
                 "--field", "RESOLUTION=Fixed", "--field", "ROOT_CAUSE=1701"],
                catch_exceptions=False,
            )
    assert result.exit_code == 0
    data = json.loads(result.stdout)
    assert data["ok"] is True


# ---------------------------------------------------------------------------
# transition run (raw)
# ---------------------------------------------------------------------------

def test_transition_run_calls_with_given_id(runner: CliRunner):
    with patch("sbm_cli.cli.load_config", return_value=_make_app_config()):
        with patch("sbm_cli.cli.SBMClient") as MockClient:
            _mock_transition(MockClient)
            result = runner.invoke(
                main,
                ["transition", "run", "02440942", "--id", "99",
                 "--field", "SOME_FIELD=hello"],
                catch_exceptions=False,
            )
    assert result.exit_code == 0
    call_kwargs = MockClient.return_value.update_item.call_args[1]
    assert call_kwargs["transition_id"] == 99
    assert call_kwargs["field_values"]["SOME_FIELD"] == "hello"


def test_transition_run_requires_id_flag(runner: CliRunner):
    with patch("sbm_cli.cli.load_config", return_value=_make_app_config()):
        with patch("sbm_cli.cli.SBMClient"):
            result = runner.invoke(
                main, ["transition", "run", "02440942"],
                catch_exceptions=False,
            )
    assert result.exit_code == 3
    data = json.loads(result.stdout)
    assert data["error"]["type"] == "validation_error"


def test_transition_resolves_username_to_id(runner: CliRunner):
    from sbm_cli.config import UserConfig
    config = _make_app_config()
    config.users["jaroslav.burget"] = UserConfig(id=15399)
    with patch("sbm_cli.cli.load_config", return_value=config):
        with patch("sbm_cli.cli.SBMClient") as MockClient:
            _mock_transition(MockClient)
            result = runner.invoke(
                main,
                ["transition", "assign", "02440942",
                 "--field", "OWNER=jaroslav.burget",
                 "--field", "3RD_LEVEL_SPECIALIST=jaroslav.burget"],
                catch_exceptions=False,
            )
    assert result.exit_code == 0
    call_kwargs = MockClient.return_value.update_item.call_args[1]
    assert call_kwargs["field_values"]["OWNER"] == 15399
    assert call_kwargs["field_values"]["3RD_LEVEL_SPECIALIST"] == 15399


def test_transition_unknown_string_field_passes_through(runner: CliRunner):
    """String field values not matching any configured user login pass through unchanged."""
    with patch("sbm_cli.cli.load_config", return_value=_make_app_config()):
        with patch("sbm_cli.cli.SBMClient") as MockClient:
            _mock_transition(MockClient)
            runner.invoke(
                main,
                ["transition", "assign", "02440942",
                 "--field", "OWNER=bob.unknown",
                 "--field", "3RD_LEVEL_SPECIALIST=316"],
                catch_exceptions=False,
            )
    call_kwargs = MockClient.return_value.update_item.call_args[1]
    # "bob.unknown" is not in config.users (empty by default) — passes through as string
    assert call_kwargs["field_values"]["OWNER"] == "bob.unknown"
    # Numeric strings are still coerced to int by _parse_fields
    assert call_kwargs["field_values"]["3RD_LEVEL_SPECIALIST"] == 316


def test_transition_warns_on_unknown_field(runner: CliRunner):
    """Fields not in required or optional lists emit a warning to stderr but still proceed."""
    config = _make_app_config()
    config.transitions["assign"] = TransitionConfig(
        id=155, fields=["OWNER", "3RD_LEVEL_SPECIALIST"],
        optional_fields=["SOLUTION_STEPS"],
    )
    with patch("sbm_cli.cli.load_config", return_value=config):
        with patch("sbm_cli.cli.SBMClient") as MockClient:
            mock_client = MockClient.return_value
            mock_client.get_item_by_display_id.return_value = {
                "item": {"id": {"id": 100, "itemIdPrefixed": "02440942"}, "fields": {}},
                "result": {"type": "OK"},
            }
            mock_client.start_transition.return_value = 42
            mock_client.update_item.return_value = {
                "item": {"id": {"id": 100}}, "result": {"type": "OK"}
            }
            result = runner.invoke(
                main,
                ["transition", "assign", "02440942",
                 "--field", "OWNER=316",
                 "--field", "3RD_LEVEL_SPECIALIST=316",
                 "--field", "UNKNOWN_FIELD=foo"],
                catch_exceptions=False,
            )
    # Should succeed despite unknown field
    assert result.exit_code == 0
    # CliRunner captures stderr in result.output (mix_stderr=True by default)
    assert "Warning: unknown fields" in result.output
    assert "UNKNOWN_FIELD" in result.output
    # Field is still sent to the API
    call_kwargs = MockClient.return_value.update_item.call_args[1]
    assert call_kwargs["field_values"]["UNKNOWN_FIELD"] == "foo"


def test_transition_with_optional_field_passes_to_api(runner: CliRunner):
    """SOLUTION_STEPS in optional_fields is sent to the API without warnings."""
    config = _make_app_config()
    config.transitions["assign"] = TransitionConfig(
        id=155, fields=["OWNER", "3RD_LEVEL_SPECIALIST"],
        optional_fields=["SOLUTION_STEPS"],
    )
    with patch("sbm_cli.cli.load_config", return_value=config):
        with patch("sbm_cli.cli.SBMClient") as MockClient:
            mock_client = MockClient.return_value
            mock_client.get_item_by_display_id.return_value = {
                "item": {"id": {"id": 100, "itemIdPrefixed": "02440942"}, "fields": {}},
                "result": {"type": "OK"},
            }
            mock_client.start_transition.return_value = 42
            mock_client.update_item.return_value = {
                "item": {"id": {"id": 100}}, "result": {"type": "OK"}
            }
            result = runner.invoke(
                main,
                ["transition", "assign", "02440942",
                 "--field", "OWNER=316",
                 "--field", "3RD_LEVEL_SPECIALIST=316",
                 "--field", "SOLUTION_STEPS=Taking ownership."],
                catch_exceptions=False,
            )
    assert result.exit_code == 0
    # No warning for a known optional field
    assert "Warning" not in result.output
    call_kwargs = MockClient.return_value.update_item.call_args[1]
    assert call_kwargs["field_values"]["SOLUTION_STEPS"] == "Taking ownership."


# ---------------------------------------------------------------------------
# field-values
# ---------------------------------------------------------------------------

def test_field_values_returns_json(runner: CliRunner):
    probe_results = [{"id": 1701, "name": "Other cause"}, {"id": 1700, "name": "User side issue"}]
    with patch("sbm_cli.cli.load_config", return_value=_make_app_config()):
        with patch("sbm_cli.cli.SBMClient") as MockClient:
            MockClient.return_value.probe_table.return_value = probe_results
            result = runner.invoke(
                main,
                ["field-values", "ROOT_CAUSE", "--table", "9999"],
                catch_exceptions=False,
            )
    assert result.exit_code == 0
    data = json.loads(result.stdout)
    assert data["ok"] is True
    assert data["command"] == "field-values"
    assert data["data"]["field"] == "ROOT_CAUSE"
    assert data["data"]["table_id"] == 9999
    assert len(data["data"]["values"]) == 2


def test_field_values_pretty(runner: CliRunner):
    probe_results = [{"id": 1701, "name": "Other cause"}]
    with patch("sbm_cli.cli.load_config", return_value=_make_app_config()):
        with patch("sbm_cli.cli.SBMClient") as MockClient:
            MockClient.return_value.probe_table.return_value = probe_results
            result = runner.invoke(
                main,
                ["--pretty", "field-values", "ROOT_CAUSE", "--table", "9999"],
                catch_exceptions=False,
            )
    assert result.exit_code == 0
    assert "Other cause" in result.output


def test_field_values_auth_error(runner: CliRunner):
    with patch("sbm_cli.cli.load_config", return_value=_make_app_config()):
        with patch("sbm_cli.cli.SBMClient") as MockClient:
            MockClient.return_value.probe_table.side_effect = PermissionError("401")
            result = runner.invoke(
                main,
                ["field-values", "ROOT_CAUSE", "--table", "9999"],
                catch_exceptions=False,
            )
    assert result.exit_code == 2
    data = json.loads(result.stdout)
    assert data["error"]["type"] == "auth_error"


def test_field_values_api_error(runner: CliRunner):
    with patch("sbm_cli.cli.load_config", return_value=_make_app_config()):
        with patch("sbm_cli.cli.SBMClient") as MockClient:
            MockClient.return_value.probe_table.side_effect = SBMError("probe failed")
            result = runner.invoke(
                main,
                ["field-values", "ROOT_CAUSE", "--table", "9999"],
                catch_exceptions=False,
            )
    assert result.exit_code == 1
    data = json.loads(result.stdout)
    assert data["error"]["type"] == "api_error"


# ---------------------------------------------------------------------------
# --indent flag
# ---------------------------------------------------------------------------

def test_indent_flag_formats_json(runner: CliRunner):
    result = _invoke(runner, ["--indent", "schema"])
    assert result.exit_code == 0
    assert "\n  " in result.stdout  # indented JSON has nested newlines
    data = json.loads(result.stdout)
    assert data["ok"] is True


def test_indent_flag_formats_error_json(runner: CliRunner):
    from sbm_cli.config import ConfigError
    with patch("sbm_cli.cli.load_config", side_effect=ConfigError("not found")):
        result = runner.invoke(main, ["--indent", "schema"], catch_exceptions=False)
    assert result.exit_code == 2
    assert "\n  " in result.stdout
    data = json.loads(result.stdout)
    assert data["ok"] is False


def test_no_indent_by_default(runner: CliRunner):
    result = _invoke(runner, ["schema"])
    assert result.exit_code == 0
    # compact JSON has no leading spaces
    assert result.stdout.startswith('{"ok"')


def test_list_pretty_uses_requested_columns(runner: CliRunner):
    mock_items = [
        {
            "id": {"id": 1, "itemIdPrefixed": "00001"},
            "fields": {
                "TITLE": {"value": "My Ticket"},
                "URGENCY": {"value": "High"},
            }
        }
    ]
    with patch("sbm_cli.cli.load_config", return_value=_make_app_config()):
        with patch("sbm_cli.cli.SBMClient") as MockClient:
            MockClient.return_value.list_items_by_report.return_value = mock_items
            result = runner.invoke(
                main,
                ["--pretty", "list", "--fields", "TITLE,URGENCY"],
                catch_exceptions=False,
            )
    assert result.exit_code == 0
    assert "My Ticket" in result.output
    assert "High" in result.output


# ---------------------------------------------------------------------------
# fields
# ---------------------------------------------------------------------------

def test_fields_command_returns_json(runner: CliRunner):
    mock_fields = [
        {"dbname": "OWNER", "type": "relational", "label": "Owner"},
        {"dbname": "TITLE", "type": "text", "label": "TITLE"},
    ]
    with patch("sbm_cli.cli.load_config", return_value=_make_app_config()):
        with patch("sbm_cli.cli.SBMClient") as MockClient:
            MockClient.return_value.get_field_definitions.return_value = mock_fields
            result = runner.invoke(
                main,
                ["fields", "02440942"],
                catch_exceptions=False,
            )
    assert result.exit_code == 0
    data = json.loads(result.stdout)
    assert data["ok"] is True
    assert data["command"] == "fields"
    assert data["data"]["ticket_id"] == "02440942"
    assert data["data"]["table_id"] == 1000
    assert len(data["data"]["fields"]) == 2
    assert data["data"]["fields"][0]["dbname"] == "OWNER"


def test_fields_command_pretty(runner: CliRunner):
    mock_fields = [{"dbname": "TITLE", "type": "text", "label": "TITLE"}]
    with patch("sbm_cli.cli.load_config", return_value=_make_app_config()):
        with patch("sbm_cli.cli.SBMClient") as MockClient:
            MockClient.return_value.get_field_definitions.return_value = mock_fields
            result = runner.invoke(
                main,
                ["--pretty", "fields", "02440942"],
                catch_exceptions=False,
            )
    assert result.exit_code == 0
    assert "TITLE" in result.output


def test_fields_command_custom_table(runner: CliRunner):
    with patch("sbm_cli.cli.load_config", return_value=_make_app_config()):
        with patch("sbm_cli.cli.SBMClient") as MockClient:
            MockClient.return_value.get_field_definitions.return_value = []
            runner.invoke(
                main,
                ["fields", "02440942", "--table", "9999"],
                catch_exceptions=False,
            )
    MockClient.return_value.get_field_definitions.assert_called_once_with(
        "02440942", 9999, extra_fields=None
    )


def test_fields_command_not_found(runner: CliRunner):
    with patch("sbm_cli.cli.load_config", return_value=_make_app_config()):
        with patch("sbm_cli.cli.SBMClient") as MockClient:
            MockClient.return_value.get_field_definitions.side_effect = ValueError("No item found")
            result = runner.invoke(
                main,
                ["fields", "9999999"],
                catch_exceptions=False,
            )
    assert result.exit_code == 1
    data = json.loads(result.stdout)
    assert data["ok"] is False
    assert data["error"]["type"] == "api_error"


# ---------------------------------------------------------------------------
# schema fields
# ---------------------------------------------------------------------------

def test_schema_includes_fields_when_configured(runner: CliRunner):
    from sbm_cli.config import FieldDef
    config = _make_app_config()
    config.fields = {
        "TITLE": FieldDef(dbname="TITLE", type="text", label="Title"),
        "OWNER": FieldDef(dbname="OWNER", type="relational", label="Owner"),
    }
    result = _invoke(runner, ["schema"], config=config)
    assert result.exit_code == 0
    data = json.loads(result.stdout)
    assert "fields" in data["data"]
    assert data["data"]["fields"]["TITLE"]["type"] == "text"
    assert data["data"]["fields"]["OWNER"]["label"] == "Owner"


def test_schema_omits_fields_key_when_none_configured(runner: CliRunner):
    result = _invoke(runner, ["schema"])  # default config has no fields
    assert result.exit_code == 0
    data = json.loads(result.stdout)
    assert "fields" not in data["data"]


def test_schema_pretty_shows_fields(runner: CliRunner):
    from sbm_cli.config import FieldDef
    config = _make_app_config()
    config.fields = {
        "TITLE": FieldDef(dbname="TITLE", type="text", label="Title"),
    }
    result = _invoke(runner, ["--pretty", "schema"], config=config)
    assert result.exit_code == 0
    assert "TITLE" in result.output
    assert "text" in result.output


# ---------------------------------------------------------------------------
# configure field discovery
# ---------------------------------------------------------------------------

def test_configure_with_field_discovery_stores_fields(runner: CliRunner):
    user_input = (
        "https://sbm.test\n"   # host
        "testuser\n"            # username
        "testpass\n"            # password
        "1000\n"                # table_id
        "\n"                    # report_ids (blank → none)
        "n\n"                   # verify_ssl (No)
        "\n"                    # list_fields (blank → use default)
        "02440942\n"            # sample ticket ID
    )

    saved_configs = []

    def capture_save(config, path=None):
        saved_configs.append(config)

    with patch("sbm_cli.cli.save_config", side_effect=capture_save):
        with patch("sbm_cli.cli.SBMClient") as MockClient:
            MockClient.return_value.check_auth.return_value = None
            MockClient.return_value.get_field_definitions.return_value = [
                {"dbname": "OWNER", "type": "relational", "label": "Owner"},
                {"dbname": "TITLE", "type": "text", "label": "TITLE"},
            ]
            result = runner.invoke(
                main,
                ["configure"],
                input=user_input,
                catch_exceptions=False,
            )

    assert result.exit_code == 0
    assert len(saved_configs) == 2  # once before fields, once after
    final_config = saved_configs[-1]
    assert "TITLE" in final_config.fields
    assert final_config.fields["TITLE"].type == "text"
    assert "OWNER" in final_config.fields
    assert final_config.fields["OWNER"].type == "relational"


# ---------------------------------------------------------------------------
# list — field priority: --fields > config.list_fields > _DEFAULT_LIST_FIELDS
# ---------------------------------------------------------------------------

def test_list_uses_config_list_fields_when_no_flag(runner: CliRunner):
    """config.list_fields is used as default when --fields is not given."""
    cfg = _make_app_config()
    cfg.list_fields = ["TITLE", "FUNCTIONALITY", "URGENCY"]
    with patch("sbm_cli.cli.load_config", return_value=cfg):
        with patch("sbm_cli.cli.SBMClient") as MockClient:
            MockClient.return_value.list_items_by_report.return_value = []
            runner.invoke(main, ["list"], catch_exceptions=False)
            call_args = MockClient.return_value.list_items_by_report.call_args
            assert call_args[1]["fields"] == ["TITLE", "FUNCTIONALITY", "URGENCY"]


def test_list_explicit_fields_flag_overrides_config_list_fields(runner: CliRunner):
    """--fields always wins over config.list_fields."""
    cfg = _make_app_config()
    cfg.list_fields = ["TITLE", "FUNCTIONALITY"]
    with patch("sbm_cli.cli.load_config", return_value=cfg):
        with patch("sbm_cli.cli.SBMClient") as MockClient:
            MockClient.return_value.list_items_by_report.return_value = []
            runner.invoke(main, ["list", "--fields", "TITLE,STATE"], catch_exceptions=False)
            call_args = MockClient.return_value.list_items_by_report.call_args
            assert call_args[1]["fields"] == ["TITLE", "STATE"]


def test_list_falls_back_to_default_when_config_list_fields_empty(runner: CliRunner):
    """When config.list_fields is [], the hardcoded _DEFAULT_LIST_FIELDS is used."""
    from sbm_cli.cli import _DEFAULT_LIST_FIELDS
    cfg = _make_app_config()
    cfg.list_fields = []
    with patch("sbm_cli.cli.load_config", return_value=cfg):
        with patch("sbm_cli.cli.SBMClient") as MockClient:
            MockClient.return_value.list_items_by_report.return_value = []
            runner.invoke(main, ["list"], catch_exceptions=False)
            call_args = MockClient.return_value.list_items_by_report.call_args
            assert call_args[1]["fields"] == _DEFAULT_LIST_FIELDS


def test_fields_cmd_passes_extra_fields(runner: CliRunner):
    """--fields option is passed as extra_fields to get_field_definitions."""
    with patch("sbm_cli.cli.load_config", return_value=_make_app_config()):
        with patch("sbm_cli.cli.SBMClient") as MockClient:
            MockClient.return_value.get_field_definitions.return_value = [
                {"dbname": "FUNCTIONALITY", "type": "relational", "label": "Functionality"},
            ]
            result = runner.invoke(
                main,
                ["fields", "02440942", "--fields", "FUNCTIONALITY,APPLICATION1"],
                catch_exceptions=False,
            )
    assert result.exit_code == 0
    call_kwargs = MockClient.return_value.get_field_definitions.call_args[1]
    assert call_kwargs["extra_fields"] == ["FUNCTIONALITY", "APPLICATION1"]


def test_fields_cmd_without_extra_fields_passes_none(runner: CliRunner):
    """Without --fields, extra_fields=None is passed."""
    with patch("sbm_cli.cli.load_config", return_value=_make_app_config()):
        with patch("sbm_cli.cli.SBMClient") as MockClient:
            MockClient.return_value.get_field_definitions.return_value = []
            runner.invoke(main, ["fields", "02440942"], catch_exceptions=False)
    call_kwargs = MockClient.return_value.get_field_definitions.call_args[1]
    assert call_kwargs["extra_fields"] is None


def test_configure_skips_field_discovery_when_no_sample_id(runner: CliRunner):
    user_input = (
        "https://sbm.test\n"
        "testuser\n"
        "testpass\n"
        "1000\n"
        "\n"  # report_ids (blank → none)
        "n\n"
        "\n"  # list_fields (blank → use default)
        "\n"  # blank → skip field discovery
    )

    saved_configs = []

    def capture_save(config, path=None):
        saved_configs.append(config)

    with patch("sbm_cli.cli.save_config", side_effect=capture_save):
        with patch("sbm_cli.cli.SBMClient") as MockClient:
            MockClient.return_value.check_auth.return_value = None
            result = runner.invoke(
                main,
                ["configure"],
                input=user_input,
                catch_exceptions=False,
            )

    assert result.exit_code == 0
    # Only one save: field discovery was skipped
    assert len(saved_configs) == 1
    assert saved_configs[0].fields == {}
    # get_field_definitions should never have been called
    MockClient.return_value.get_field_definitions.assert_not_called()


# ---------------------------------------------------------------------------
# configure group — new subcommands (Task 6)
# ---------------------------------------------------------------------------

def test_configure_transition_adds_named_transition(runner: CliRunner):
    """configure transition writes a new transition into the loaded config."""
    initial_cfg = Config(
        host="https://sbm.test", username="u",
        verify_ssl=False, table_id=1000, report_ids=[2208],
    )
    with patch("sbm_cli.cli.load_config", return_value=initial_cfg):
        with patch("sbm_cli.cli.save_config") as mock_save:
            result = runner.invoke(
                main,
                ["configure", "transition", "assign"],
                # Inputs: transition_id, required_fields, list_fields, pre_id
                input="155\nOWNER,3RD_LEVEL_SPECIALIST\n\n\n",
                catch_exceptions=False,
            )
    assert result.exit_code == 0
    saved_cfg = mock_save.call_args[0][0]
    assert "assign" in saved_cfg.transitions
    assert saved_cfg.transitions["assign"].id == 155
    assert saved_cfg.transitions["assign"].fields == ["OWNER", "3RD_LEVEL_SPECIALIST"]
    assert saved_cfg.transitions["assign"].field_types == {}
    assert saved_cfg.transitions["assign"].pre_transition_id is None


def test_configure_transition_with_pre_transition(runner: CliRunner):
    """configure transition saves pre_transition_id and pre_transition_optional."""
    initial_cfg = Config(
        host="https://sbm.test", username="u",
        verify_ssl=False, table_id=1000, report_ids=[],
    )
    with patch("sbm_cli.cli.load_config", return_value=initial_cfg):
        with patch("sbm_cli.cli.save_config") as mock_save:
            result = runner.invoke(
                main,
                ["configure", "transition", "close"],
                # transition_id=19, fields=RESOLUTION,ROOT_CAUSE, list_fields=blank,
                # pre_id=148, pre_optional=y
                input="19\nRESOLUTION,ROOT_CAUSE\n\n148\ny\n",
                catch_exceptions=False,
            )
    assert result.exit_code == 0
    saved_cfg = mock_save.call_args[0][0]
    t = saved_cfg.transitions["close"]
    assert t.id == 19
    assert t.pre_transition_id == 148
    assert t.pre_transition_optional is True


def test_configure_transition_overwrite_confirm_no_aborts(runner: CliRunner):
    """Answering N to overwrite prompt leaves config unchanged."""
    cfg = _make_app_config()  # already has 'assign' transition
    with patch("sbm_cli.cli.load_config", return_value=cfg):
        with patch("sbm_cli.cli.save_config") as mock_save:
            result = runner.invoke(
                main,
                ["configure", "transition", "assign"],
                input="N\n",
                catch_exceptions=False,
            )
    assert result.exit_code == 0
    mock_save.assert_not_called()


def test_configure_transition_missing_config_exits_2(runner: CliRunner):
    """configure transition exits 2 when config file does not exist."""
    from sbm_cli.config import ConfigError
    with patch("sbm_cli.cli.load_config", side_effect=ConfigError("not found")):
        result = runner.invoke(
            main,
            ["configure", "transition", "assign"],
            catch_exceptions=False,
        )
    assert result.exit_code == 2


def test_configure_transition_save_config_error_exits_2(runner: CliRunner):
    """configure transition exits 2 when save_config raises ConfigError (e.g. invalid name)."""
    from sbm_cli.config import ConfigError
    initial_cfg = Config(
        host="https://sbm.test", username="u",
        verify_ssl=False, table_id=1000, report_ids=[],
    )
    with patch("sbm_cli.cli.load_config", return_value=initial_cfg):
        with patch("sbm_cli.cli.save_config", side_effect=ConfigError("invalid key")):
            result = runner.invoke(
                main,
                ["configure", "transition", "bad name"],
                input="155\n\n\n\n",
                catch_exceptions=False,
            )
    assert result.exit_code == 2


def test_configure_setup_saves_list_fields(runner: CliRunner):
    """configure setup persists list_fields when user provides them."""
    with patch("sbm_cli.cli.save_config") as mock_save:
        with patch("sbm_cli.cli.SBMClient") as MockClient:
            MockClient.return_value.check_auth.side_effect = PermissionError("401")
            result = runner.invoke(
                main,
                ["configure", "setup"],
                # host, username, password, table_id, report_ids, verify_ssl,
                # list_fields, sample_ticket
                input="https://sbm.test\nuser\npass\n1000\n\nn\nTITLE,FUNCTIONALITY,URGENCY\n\n",
                catch_exceptions=False,
            )
    assert result.exit_code in (0, 2)  # 2 because auth fails, but save still happens
    saved_cfg = mock_save.call_args[0][0]
    assert saved_cfg.list_fields == ["TITLE", "FUNCTIONALITY", "URGENCY"]


def test_configure_setup_saves_report_ids(runner: CliRunner):
    with patch("sbm_cli.cli.save_config") as mock_save:
        with patch("sbm_cli.cli.SBMClient") as MockClient:
            MockClient.return_value.check_auth.side_effect = PermissionError("401")
            runner.invoke(
                main, ["configure", "setup"],
                input="https://sbm.test\nuser\npass\n1000\n2208, 2209\nn\n\n\n",
                catch_exceptions=False,
            )
    saved_cfg = mock_save.call_args[0][0]
    assert saved_cfg.report_ids == [2208, 2209]


def test_configure_no_subcommand_runs_setup_wizard(runner: CliRunner):
    """sbm configure with no subcommand invokes the setup wizard."""
    with patch("sbm_cli.cli.save_config"):
        with patch("sbm_cli.cli.SBMClient") as MockClient:
            MockClient.return_value.check_auth.side_effect = PermissionError("401")
            result = runner.invoke(
                main,
                ["configure"],
                input="https://sbm.test\nuser\npass\n1000\n\nn\n\n\n",
                catch_exceptions=False,
            )
    assert "SBM host" in result.output


def test_missing_credentials_returns_auth_error(runner: CliRunner, mocker):
    mocker.patch("sbm_cli.credentials.get_password", return_value=None)
    with patch("sbm_cli.cli.load_config", return_value=_make_app_config()):
        with patch("sbm_cli.cli.SBMClient"):
            result = runner.invoke(main, ["list"], catch_exceptions=False)
    assert result.exit_code == 2
    data = json.loads(result.stdout)
    assert data["ok"] is False
    assert data["error"]["type"] == "auth_error"
    assert "sbm configure" in data["error"]["message"]


def test_configure_setup_stores_password_in_keyring(runner: CliRunner, mocker):
    set_pw = mocker.patch("sbm_cli.credentials.set_password")
    with patch("sbm_cli.cli.save_config"):
        with patch("sbm_cli.cli.SBMClient") as MockClient:
            MockClient.return_value.check_auth.return_value = None
            result = runner.invoke(
                main,
                ["configure", "setup"],
                input="https://sbm.test\nuser\nsecretpass\n1000\n\nn\n\n\n",
                catch_exceptions=False,
            )
    assert result.exit_code == 0
    set_pw.assert_called_once_with("https://sbm.test", "user", "secretpass")


# ---------------------------------------------------------------------------
# cross-platform credentials
# ---------------------------------------------------------------------------

def test_client_prompts_interactively_when_no_keyring(runner: CliRunner, mocker):
    """When get_password raises NoKeyringAvailable, client prompts for password."""
    from sbm_cli.credentials import NoKeyringAvailable
    mocker.patch(
        "sbm_cli.credentials.get_password",
        side_effect=NoKeyringAvailable("no keyring"),
    )
    # The prompt is TTY-gated now, and CliRunner's stdin is not a TTY.
    mocker.patch("sbm_cli.credentials._stdin_is_tty", return_value=True)
    mock_items = [
        {"id": {"id": 1, "itemIdPrefixed": "0001"},
         "fields": {"TITLE": {"value": "T1"}, "STATE": {"value": "Open"}}}
    ]
    with patch("sbm_cli.cli.load_config", return_value=_make_app_config()):
        with patch("sbm_cli.cli.SBMClient") as MockClient:
            MockClient.return_value.list_items_by_report.return_value = mock_items
            result = runner.invoke(
                main, ["list"],
                input="mypassword\n",  # interactive prompt response
                catch_exceptions=False,
            )
    assert result.exit_code == 0
    _, kwargs = MockClient.call_args
    assert kwargs.get("password") == "mypassword"


def _valid_config_toml() -> str:
    from sbm_cli.config import dump_config
    return dump_config(_make_app_config())


def test_configure_import_writes_config(runner: CliRunner, tmp_path, monkeypatch):
    from sbm_cli.config import load_config
    target = tmp_path / "sbm.toml"
    monkeypatch.setenv("SBM_CLI_CONFIG", str(target))
    result = runner.invoke(main, ["configure", "import", "-"],
                           input=_valid_config_toml(), catch_exceptions=False)
    assert result.exit_code == 0
    data = json.loads(result.stdout)
    assert data["ok"] is True
    assert data["data"]["path"] == str(target)
    assert data["data"]["transitions"] == 4
    assert data["data"]["teams"] == 1
    assert data["data"]["report_ids"] == [2208]
    assert load_config(target).transitions["assign"].id == 155


def test_configure_import_from_file(runner: CliRunner, tmp_path, monkeypatch):
    source = tmp_path / "incoming.toml"
    source.write_text(_valid_config_toml(), encoding="utf-8")
    target = tmp_path / "sbm.toml"
    monkeypatch.setenv("SBM_CLI_CONFIG", str(target))
    result = runner.invoke(main, ["configure", "import", str(source)],
                           catch_exceptions=False)
    assert result.exit_code == 0
    assert target.exists()


def test_configure_import_accepts_utf8_bom_from_file(runner: CliRunner, tmp_path,
                                                      monkeypatch):
    """PowerShell's `Out-File -Encoding utf8` writes a BOM; tomllib rejects one."""
    source = tmp_path / "incoming.toml"
    source.write_text(_valid_config_toml(), encoding="utf-8-sig")
    assert source.read_bytes().startswith(b"\xef\xbb\xbf")
    target = tmp_path / "sbm.toml"
    monkeypatch.setenv("SBM_CLI_CONFIG", str(target))
    result = runner.invoke(main, ["configure", "import", str(source)],
                           catch_exceptions=False)
    assert result.exit_code == 0
    # The installed config must be BOM-free so load_config can read it back.
    assert not target.read_bytes().startswith(b"\xef\xbb\xbf")


def test_configure_import_accepts_utf8_bom_from_stdin(runner: CliRunner, tmp_path,
                                                       monkeypatch):
    target = tmp_path / "sbm.toml"
    monkeypatch.setenv("SBM_CLI_CONFIG", str(target))
    result = runner.invoke(main, ["configure", "import", "-"],
                           input="﻿" + _valid_config_toml(),
                           catch_exceptions=False)
    assert result.exit_code == 0
    assert not target.read_bytes().startswith(b"\xef\xbb\xbf")


def test_configure_import_refuses_overwrite_without_force(runner: CliRunner, tmp_path,
                                                          monkeypatch):
    target = tmp_path / "sbm.toml"
    target.write_text("original", encoding="utf-8")
    monkeypatch.setenv("SBM_CLI_CONFIG", str(target))
    result = runner.invoke(main, ["configure", "import", "-"],
                           input=_valid_config_toml(), catch_exceptions=False)
    assert result.exit_code == 2
    data = json.loads(result.stdout)
    assert data["error"]["type"] == "config_error"
    assert "--force" in data["error"]["message"]
    assert target.read_text(encoding="utf-8") == "original"


def test_configure_import_force_overwrites(runner: CliRunner, tmp_path, monkeypatch):
    target = tmp_path / "sbm.toml"
    target.write_text("original", encoding="utf-8")
    monkeypatch.setenv("SBM_CLI_CONFIG", str(target))
    result = runner.invoke(main, ["configure", "import", "-", "--force"],
                           input=_valid_config_toml(), catch_exceptions=False)
    assert result.exit_code == 0
    assert "[connection]" in target.read_text(encoding="utf-8")


def test_configure_import_malformed_leaves_existing_config_intact(runner: CliRunner,
                                                                  tmp_path, monkeypatch):
    target = tmp_path / "sbm.toml"
    original = _valid_config_toml()
    target.write_text(original, encoding="utf-8")
    monkeypatch.setenv("SBM_CLI_CONFIG", str(target))
    result = runner.invoke(main, ["configure", "import", "-", "--force"],
                           input="[connection\nthis is not toml",
                           catch_exceptions=False)
    assert result.exit_code == 3
    data = json.loads(result.stdout)
    assert data["error"]["type"] == "validation_error"
    assert target.read_text(encoding="utf-8") == original
    assert list(tmp_path.iterdir()) == [target]  # no temp file left behind


def test_configure_import_missing_required_keys_is_validation_error(runner: CliRunner,
                                                                    tmp_path, monkeypatch):
    target = tmp_path / "sbm.toml"
    monkeypatch.setenv("SBM_CLI_CONFIG", str(target))
    result = runner.invoke(main, ["configure", "import", "-"],
                           input='[defaults]\ntable_id = 1000\n',
                           catch_exceptions=False)
    assert result.exit_code == 3
    assert json.loads(result.stdout)["error"]["type"] == "validation_error"
    assert not target.exists()


def test_configure_import_strips_plaintext_password(runner: CliRunner, tmp_path,
                                                     monkeypatch):
    target = tmp_path / "sbm.toml"
    monkeypatch.setenv("SBM_CLI_CONFIG", str(target))
    incoming = (
        '[connection]\n'
        'host = "https://sbm.test"\n'
        'username = "alice"\n'
        'password = "leaked"\n'
        'verify_ssl = false\n'
        '\n[defaults]\ntable_id = 1000\n'
    )
    result = runner.invoke(main, ["configure", "import", "-"], input=incoming,
                           catch_exceptions=False)
    assert result.exit_code == 0
    assert "leaked" not in target.read_text(encoding="utf-8")
    assert "plaintext password" in result.stderr.lower()


def test_configure_export_prints_raw_toml(runner: CliRunner, tmp_path, monkeypatch):
    from sbm_cli.config import save_config, load_config
    target = tmp_path / "sbm.toml"
    save_config(_make_app_config(), target)
    monkeypatch.setenv("SBM_CLI_CONFIG", str(target))
    result = runner.invoke(main, ["configure", "export"], catch_exceptions=False)
    assert result.exit_code == 0
    assert '{"ok"' not in result.stdout          # raw TOML, not the envelope
    assert result.stdout.lstrip().startswith("[connection]")
    round_trip = tmp_path / "round.toml"
    round_trip.write_text(result.stdout, encoding="utf-8")
    assert load_config(round_trip).report_ids == [2208]


def test_configure_export_omits_password(runner: CliRunner, tmp_path, monkeypatch):
    from sbm_cli.config import save_config
    target = tmp_path / "sbm.toml"
    save_config(_make_app_config(), target)
    monkeypatch.setenv("SBM_CLI_CONFIG", str(target))
    monkeypatch.setenv("SBM_CLI_PASSWORD", "supersecret")
    result = runner.invoke(main, ["configure", "export"], catch_exceptions=False)
    assert "supersecret" not in result.stdout
    assert "password" not in result.stdout.lower()


def test_configure_export_missing_config_errors(runner: CliRunner, tmp_path, monkeypatch):
    monkeypatch.setenv("SBM_CLI_CONFIG", str(tmp_path / "absent.toml"))
    result = runner.invoke(main, ["configure", "export"], catch_exceptions=False)
    assert result.exit_code == 2
    data = json.loads(result.stdout)
    assert data["error"]["type"] == "config_error"


def test_config_env_var_is_used(runner: CliRunner, monkeypatch):
    monkeypatch.setenv("SBM_CLI_CONFIG", "/tmp/custom/sbm.toml")
    with patch("sbm_cli.cli.load_config", return_value=_make_app_config()) as mock_load:
        runner.invoke(main, ["schema"], catch_exceptions=False)
    assert mock_load.call_args[0][0] == Path("/tmp/custom/sbm.toml")


def test_config_flag_beats_config_env_var(runner: CliRunner, monkeypatch):
    monkeypatch.setenv("SBM_CLI_CONFIG", "/tmp/from-env.toml")
    with patch("sbm_cli.cli.load_config", return_value=_make_app_config()) as mock_load:
        runner.invoke(main, ["--config", "/tmp/from-flag.toml", "schema"],
                      catch_exceptions=False)
    assert mock_load.call_args[0][0] == Path("/tmp/from-flag.toml")


def test_default_config_path_when_nothing_set(runner: CliRunner):
    from sbm_cli.config import DEFAULT_CONFIG_PATH
    with patch("sbm_cli.cli.load_config", return_value=_make_app_config()) as mock_load:
        runner.invoke(main, ["schema"], catch_exceptions=False)
    assert mock_load.call_args[0][0] == DEFAULT_CONFIG_PATH


def test_configure_transition_honours_config_path(runner: CliRunner, tmp_path, monkeypatch):
    """Regression: configure transition used to hardcode DEFAULT_CONFIG_PATH."""
    target = tmp_path / "sbm.toml"
    monkeypatch.setenv("SBM_CLI_CONFIG", str(target))
    with patch("sbm_cli.cli.load_config", return_value=_make_app_config()) as mock_load:
        with patch("sbm_cli.cli.save_config") as mock_save:
            result = runner.invoke(
                main, ["configure", "transition", "newone"],
                input="777\nFIELD_A\n\n\n",
                catch_exceptions=False,
            )
    assert result.exit_code == 0
    assert mock_load.call_args[0][0] == target
    assert mock_save.call_args[0][1] == target


def test_client_uses_env_password(runner: CliRunner, monkeypatch, mocker):
    """SBM_CLI_PASSWORD reaches SBMClient and the keyring is never consulted."""
    monkeypatch.setenv("SBM_CLI_PASSWORD", "envsecret")
    mock_get = mocker.patch("sbm_cli.credentials.get_password", return_value="keyringsecret")
    with patch("sbm_cli.cli.load_config", return_value=_make_app_config()):
        with patch("sbm_cli.cli.SBMClient") as MockClient:
            MockClient.return_value.list_items_by_report.return_value = []
            result = runner.invoke(main, ["list"], catch_exceptions=False)
    assert result.exit_code == 0
    _, kwargs = MockClient.call_args
    assert kwargs.get("password") == "envsecret"
    mock_get.assert_not_called()


def test_client_no_password_no_tty_exits_2_without_hanging(runner: CliRunner, mocker):
    """A headless box with no keyring must fail fast, not block on stdin."""
    from sbm_cli.credentials import NoKeyringAvailable
    mocker.patch("sbm_cli.credentials.get_password",
                 side_effect=NoKeyringAvailable("no daemon"))
    mocker.patch("sbm_cli.credentials._stdin_is_tty", return_value=False)
    result = _invoke(runner, ["list"])
    assert result.exit_code == 2
    data = json.loads(result.stdout)
    assert data["ok"] is False
    assert data["error"]["type"] == "auth_error"
    assert "SBM_CLI_PASSWORD" in data["error"]["message"]


# ---------------------------------------------------------------------------
# auth check
# ---------------------------------------------------------------------------

def test_auth_check_reports_env_source(runner: CliRunner, monkeypatch):
    monkeypatch.setenv("SBM_CLI_PASSWORD", "envsecret")
    with patch("sbm_cli.cli.load_config", return_value=_make_app_config()):
        with patch("sbm_cli.cli.SBMClient") as MockClient:
            MockClient.return_value.check_auth.return_value = None
            result = runner.invoke(main, ["auth", "check"], catch_exceptions=False)
    assert result.exit_code == 0
    data = json.loads(result.stdout)
    assert data["ok"] is True
    assert data["command"] == "auth check"
    assert data["data"]["authenticated"] is True
    assert data["data"]["password_source"] == "env:SBM_CLI_PASSWORD"
    assert data["data"]["host"] == "https://sbm.test"
    assert data["data"]["username"] == "user"
    assert "envsecret" not in result.stdout


def test_auth_check_reports_keyring_source(runner: CliRunner):
    with patch("sbm_cli.cli.load_config", return_value=_make_app_config()):
        with patch("sbm_cli.cli.SBMClient") as MockClient:
            MockClient.return_value.check_auth.return_value = None
            result = runner.invoke(main, ["auth", "check"], catch_exceptions=False)
    assert json.loads(result.stdout)["data"]["password_source"] == "keyring"


def test_auth_check_401_exits_2(runner: CliRunner):
    with patch("sbm_cli.cli.load_config", return_value=_make_app_config()):
        with patch("sbm_cli.cli.SBMClient") as MockClient:
            MockClient.return_value.check_auth.side_effect = PermissionError(
                "401 Unauthorized")
            result = runner.invoke(main, ["auth", "check"], catch_exceptions=False)
    assert result.exit_code == 2
    data = json.loads(result.stdout)
    assert data["ok"] is False
    assert data["error"]["type"] == "auth_error"


def test_auth_check_no_password_exits_2(runner: CliRunner, mocker):
    from sbm_cli.credentials import NoKeyringAvailable
    mocker.patch("sbm_cli.credentials.get_password",
                 side_effect=NoKeyringAvailable("no daemon"))
    mocker.patch("sbm_cli.credentials._stdin_is_tty", return_value=False)
    result = _invoke(runner, ["auth", "check"])
    assert result.exit_code == 2
    assert json.loads(result.stdout)["error"]["type"] == "auth_error"


def test_auth_check_network_failure_exits_1(runner: CliRunner):
    with patch("sbm_cli.cli.load_config", return_value=_make_app_config()):
        with patch("sbm_cli.cli.SBMClient") as MockClient:
            MockClient.return_value.check_auth.side_effect = SBMError("boom")
            result = runner.invoke(main, ["auth", "check"], catch_exceptions=False)
    assert result.exit_code == 1
    assert json.loads(result.stdout)["error"]["type"] == "api_error"


def test_auth_check_pretty(runner: CliRunner):
    with patch("sbm_cli.cli.load_config", return_value=_make_app_config()):
        with patch("sbm_cli.cli.SBMClient") as MockClient:
            MockClient.return_value.check_auth.return_value = None
            result = runner.invoke(main, ["--pretty", "auth", "check"],
                                   catch_exceptions=False)
    assert result.exit_code == 0
    assert "https://sbm.test" in result.output
    assert '{"ok"' not in result.output


def test_client_error_message_uses_platform_keyring_name(runner: CliRunner, mocker):
    """When get_password returns None, error message includes platform keyring name."""
    mocker.patch("sbm_cli.credentials.get_password", return_value=None)
    mocker.patch(
        "sbm_cli.credentials.platform_keyring_name",
        return_value="macOS Keychain",
    )
    with patch("sbm_cli.cli.load_config", return_value=_make_app_config()):
        with patch("sbm_cli.cli.SBMClient"):
            result = runner.invoke(main, ["list"], catch_exceptions=False)
    assert result.exit_code == 2
    data = json.loads(result.stdout)
    assert data["error"]["type"] == "auth_error"
    assert "macOS Keychain" in data["error"]["message"]
    assert "sbm configure" in data["error"]["message"]


def test_configure_setup_warns_when_no_keyring(runner: CliRunner, mocker):
    """configure setup warns but continues when set_password raises NoKeyringAvailable."""
    from sbm_cli.credentials import NoKeyringAvailable
    mocker.patch(
        "sbm_cli.credentials.set_password",
        side_effect=NoKeyringAvailable("no daemon"),
    )
    with patch("sbm_cli.cli.save_config"):
        with patch("sbm_cli.cli.SBMClient") as MockClient:
            MockClient.return_value.check_auth.return_value = None
            result = runner.invoke(
                main,
                ["configure", "setup"],
                input="https://sbm.test\nuser\npass\n1000\n\nn\n\n\n",
                catch_exceptions=False,
            )
    assert result.exit_code == 0
    assert "no keyring backend" in result.output.lower()
