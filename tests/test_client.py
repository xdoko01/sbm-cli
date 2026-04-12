import pytest
import requests
from unittest.mock import MagicMock, patch
from sbm_cli.client import SBMClient, SBMError


def _make_client(mocker, responses: list[dict]) -> SBMClient:
    """Create SBMClient with mocked session that returns given JSON responses in order."""
    mock_resp_list = []
    for body in responses:
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = body
        mock_resp.raise_for_status = MagicMock()
        mock_resp_list.append(mock_resp)

    mock_session = MagicMock()
    mock_session.post.side_effect = mock_resp_list

    with patch("sbm_cli.client.requests.Session", return_value=mock_session):
        client = SBMClient("https://sbm.test", "user", "pass", verify_ssl=False)
    client._session = mock_session
    return client


def test_get_item_by_display_id_success(mocker):
    client = _make_client(mocker, [
        {"items": [{"id": {"id": 100, "itemIdPrefixed": "0001"}, "fields": {"TITLE": {"value": "Test"}}}],
         "result": {"type": "OK"}}
    ])
    result = client.get_item_by_display_id("0001", 1000)
    assert result["item"]["id"]["id"] == 100
    assert result["item"]["fields"]["TITLE"]["value"] == "Test"


def test_get_item_by_display_id_not_found(mocker):
    client = _make_client(mocker, [
        {"items": [], "result": {"type": "OK"}}
    ])
    with pytest.raises(ValueError, match="No item found"):
        client.get_item_by_display_id("9999", 1000)


def test_list_items_by_report(mocker):
    client = _make_client(mocker, [
        {"items": [{"id": {"id": 1}}, {"id": {"id": 2}}], "result": {"type": "OK"}}
    ])
    items = client.list_items_by_report(2208)
    assert len(items) == 2


def test_list_items_by_filter(mocker):
    client = _make_client(mocker, [
        {"items": [{"id": {"id": 5}}], "result": {"type": "OK"}}
    ])
    items = client.list_items_by_filter(36)
    assert len(items) == 1
    # Verify pagesize was passed as URL param
    _, kwargs = client._session.post.call_args
    assert kwargs.get("params", {}).get("pagesize") == 200


def test_start_transition_returns_lock_id(mocker):
    client = _make_client(mocker, [
        {"startTransition": {"item": {"id": {"itemLockId": 42}}}, "result": {"type": "OK"}}
    ])
    lock_id = client.start_transition(1000, 100, 155, break_lock=True)
    assert lock_id == 42


def test_update_item_sends_correct_url(mocker):
    client = _make_client(mocker, [
        {"item": {"id": {"id": 100}}, "result": {"type": "OK"}}
    ])
    client.update_item(1000, 100, {"TITLE": "New"}, transition_id=155, record_lock_id=42)
    url = client._session.post.call_args[0][0]
    assert url == "https://sbm.test/jsonapi/finishTransition/1000/100/155/42"


def test_api_error_raises_sbm_error(mocker):
    client = _make_client(mocker, [
        {"result": {"type": "ERROR", "msg": "privilege denied"}}
    ])
    with pytest.raises(SBMError, match="privilege denied"):
        client.list_items_by_report(2208)


def test_api_field_error_includes_field_name(mocker):
    client = _make_client(mocker, [
        {"result": {"type": "ERROR", "errors": {
            "errorfields": [{"dbName": "RESOLUTION", "msg": "required field"}]
        }}}
    ])
    with pytest.raises(SBMError) as exc_info:
        client.update_item(1000, 100, {})
    assert exc_info.value.field == "RESOLUTION"


def test_auth_error_raises_permission_error(mocker):
    mock_resp = MagicMock()
    mock_resp.status_code = 401
    mock_resp.raise_for_status = MagicMock()
    mock_resp.json.return_value = {}
    mock_session = MagicMock()
    mock_session.post.return_value = mock_resp
    with patch("sbm_cli.client.requests.Session", return_value=mock_session):
        client = SBMClient("https://sbm.test", "user", "wrongpass", verify_ssl=False)
    client._session = mock_session
    with pytest.raises(PermissionError):
        client.check_auth()
