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


def test_get_field_definitions_returns_sorted_list(mocker):
    mock_resp = mocker.MagicMock()
    mock_resp.status_code = 200
    mock_resp.json.return_value = {
        "items": [{
            "id": {"id": 100, "itemIdPrefixed": "02440942"},
            "fields": {
                "TITLE": {"value": "Test ticket"},
                "OWNER": {"value": {"id": 316, "name": "Smith, Alice"}},
                "PRIORITY": {"value": 2},
            }
        }],
        "result": {"type": "OK"},
    }
    session_mock = mocker.patch("sbm_cli.client.requests.Session")
    session_mock.return_value.post.return_value = mock_resp

    from sbm_cli.client import SBMClient
    client = SBMClient("https://sbm.test", "u", "p", verify_ssl=False)
    fields = client.get_field_definitions("02440942", 1000)

    assert isinstance(fields, list)
    dbnames = [f["dbname"] for f in fields]
    assert "TITLE" in dbnames
    assert "OWNER" in dbnames
    assert "PRIORITY" in dbnames
    # Should be sorted alphabetically
    assert dbnames == sorted(dbnames)
    # Type inference
    owner = next(f for f in fields if f["dbname"] == "OWNER")
    assert owner["type"] == "relational"
    title = next(f for f in fields if f["dbname"] == "TITLE")
    assert title["type"] == "text"
    priority = next(f for f in fields if f["dbname"] == "PRIORITY")
    assert priority["type"] == "numeric"


def test_get_field_definitions_classifies_no_wrapper_relational(mocker):
    """Fields returned as {id, name} without a 'value' key must be classified as relational."""
    mock_resp = mocker.MagicMock()
    mock_resp.status_code = 200
    mock_resp.raise_for_status = mocker.MagicMock()
    mock_resp.json.return_value = {
        "items": [{
            "id": {"id": 100, "itemIdPrefixed": "02440942"},
            "fields": {
                "URGENCY": {"id": 13, "name": "3 - Medium"},
            },
        }],
        "result": {"type": "OK"},
    }
    session_mock = mocker.patch("sbm_cli.client.requests.Session")
    session_mock.return_value.post.return_value = mock_resp

    from sbm_cli.client import SBMClient
    client = SBMClient("https://sbm.test", "u", "p", verify_ssl=False)
    fields = client.get_field_definitions("02440942", 1000)

    urgency = next(f for f in fields if f["dbname"] == "URGENCY")
    assert urgency["type"] == "relational"
    assert urgency["label"] == "3 - Medium"


def test_get_field_definitions_label_from_display_name(mocker):
    """label prefers displayName over name."""
    mock_resp = mocker.MagicMock()
    mock_resp.status_code = 200
    mock_resp.raise_for_status = mocker.MagicMock()
    mock_resp.json.return_value = {
        "items": [{
            "id": {"id": 100, "itemIdPrefixed": "02440942"},
            "fields": {
                "OWNER": {"value": {"id": 316, "name": "Smith"}, "displayName": "Owner"},
            },
        }],
        "result": {"type": "OK"},
    }
    session_mock = mocker.patch("sbm_cli.client.requests.Session")
    session_mock.return_value.post.return_value = mock_resp

    from sbm_cli.client import SBMClient
    client = SBMClient("https://sbm.test", "u", "p", verify_ssl=False)
    fields = client.get_field_definitions("02440942", 1000)

    owner = next(f for f in fields if f["dbname"] == "OWNER")
    assert owner["label"] == "Owner"


def test_get_field_definitions_with_extra_fields_merges_results(mocker):
    """extra_fields triggers a second API call; both sets of fields appear in output."""
    resp1 = mocker.MagicMock()
    resp1.status_code = 200
    resp1.raise_for_status = mocker.MagicMock()
    resp1.json.return_value = {
        "items": [{
            "id": {"id": 100, "itemIdPrefixed": "02440942"},
            "fields": {
                "TITLE": {"value": "Test"},
                "OWNER": {"value": {"id": 316, "name": "Smith"}},
            },
        }],
        "result": {"type": "OK"},
    }
    resp2 = mocker.MagicMock()
    resp2.status_code = 200
    resp2.raise_for_status = mocker.MagicMock()
    resp2.json.return_value = {
        "items": [{
            "id": {"id": 100, "itemIdPrefixed": "02440942"},
            "fields": {
                "FUNCTIONALITY": {"displayName": "Functionality", "value": None},
            },
        }],
        "result": {"type": "OK"},
    }
    session_mock = mocker.patch("sbm_cli.client.requests.Session")
    session_mock.return_value.post.side_effect = [resp1, resp2]

    from sbm_cli.client import SBMClient
    client = SBMClient("https://sbm.test", "u", "p", verify_ssl=False)
    fields = client.get_field_definitions("02440942", 1000, extra_fields=["FUNCTIONALITY"])

    dbnames = [f["dbname"] for f in fields]
    assert "TITLE" in dbnames
    assert "OWNER" in dbnames
    assert "FUNCTIONALITY" in dbnames
    assert dbnames == sorted(dbnames)
    assert session_mock.return_value.post.call_count == 2


def test_get_field_definitions_call1_wins_on_collision(mocker):
    """When both calls return the same field, call-1 entry is kept."""
    resp1 = mocker.MagicMock()
    resp1.status_code = 200
    resp1.raise_for_status = mocker.MagicMock()
    resp1.json.return_value = {
        "items": [{
            "id": {"id": 100, "itemIdPrefixed": "02440942"},
            "fields": {
                "OWNER": {"value": {"id": 316, "name": "Smith"}, "displayName": "Owner"},
            },
        }],
        "result": {"type": "OK"},
    }
    resp2 = mocker.MagicMock()
    resp2.status_code = 200
    resp2.raise_for_status = mocker.MagicMock()
    resp2.json.return_value = {
        "items": [{
            "id": {"id": 100, "itemIdPrefixed": "02440942"},
            "fields": {
                "OWNER": {"displayName": "Owner", "value": None},
            },
        }],
        "result": {"type": "OK"},
    }
    session_mock = mocker.patch("sbm_cli.client.requests.Session")
    session_mock.return_value.post.side_effect = [resp1, resp2]

    from sbm_cli.client import SBMClient
    client = SBMClient("https://sbm.test", "u", "p", verify_ssl=False)
    fields = client.get_field_definitions("02440942", 1000, extra_fields=["OWNER"])

    owner = next(f for f in fields if f["dbname"] == "OWNER")
    assert owner["type"] == "relational"  # from call 1; call 2 would give "text"


def test_get_field_definitions_without_extra_fields_makes_one_call(mocker):
    """Without extra_fields, only one API call is made (unchanged behaviour)."""
    resp = mocker.MagicMock()
    resp.status_code = 200
    resp.raise_for_status = mocker.MagicMock()
    resp.json.return_value = {
        "items": [{"id": {"id": 100, "itemIdPrefixed": "0001"}, "fields": {"TITLE": {"value": "T"}}}],
        "result": {"type": "OK"},
    }
    session_mock = mocker.patch("sbm_cli.client.requests.Session")
    session_mock.return_value.post.return_value = resp

    from sbm_cli.client import SBMClient
    client = SBMClient("https://sbm.test", "u", "p", verify_ssl=False)
    client.get_field_definitions("0001", 1000)
    assert session_mock.return_value.post.call_count == 1
