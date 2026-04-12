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
    data = json.loads(result.output)
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
    data = json.loads(result.output)
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
    data = json.loads(result.output)
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
    data = json.loads(result.output)
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
    data = json.loads(result.output)
    assert data["ok"] is False
    assert data["error"]["type"] == "api_error"


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
    data = json.loads(result.output)
    assert data["ok"] is True
    assert data["command"] == "get"
    assert data["data"]["id"]["itemIdPrefixed"] == "02440942"


def test_get_not_found(runner: CliRunner):
    with patch("sbm_cli.cli.load_config", return_value=_make_app_config()):
        with patch("sbm_cli.cli.SBMClient") as MockClient:
            MockClient.return_value.get_item_by_display_id.side_effect = ValueError("No item found")
            result = runner.invoke(main, ["get", "9999999"], catch_exceptions=False)
    assert result.exit_code == 1
    data = json.loads(result.output)
    assert data["ok"] is False
    assert "No item found" in data["error"]["message"]
