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
        password="pass",
        verify_ssl=False,
        table_id=1000,
        report_id=2208,
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
        teams={"market-finance": TeamConfig(id=155, name="L3 SD Market Finance")},
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


def test_schema_pretty(runner: CliRunner):
    result = _invoke(runner, ["--pretty", "schema"])
    assert result.exit_code == 0
    assert "assign" in result.output
    assert "155" in result.output


# ---------------------------------------------------------------------------
# teams
# ---------------------------------------------------------------------------

def test_teams_outputs_json(runner: CliRunner):
    result = _invoke(runner, ["teams"])
    assert result.exit_code == 0
    data = json.loads(result.stdout)
    assert data["ok"] is True
    assert "market-finance" in data["data"]
    assert data["data"]["market-finance"]["id"] == 155


def test_teams_pretty(runner: CliRunner):
    result = _invoke(runner, ["--pretty", "teams"])
    assert result.exit_code == 0
    assert "market-finance" in result.output


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
            # Just verify it was called with report_id=2208
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
