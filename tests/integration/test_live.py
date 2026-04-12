"""
Live integration tests — require a real SBM connection.

Set up:
  1. Copy .env.example to .env and fill in credentials
  2. Run: pytest -m integration

These tests are skipped by default in CI.
"""
import os
import pytest
from sbm_cli.client import SBMClient


def _client() -> SBMClient:
    host = os.environ.get("SBM_AE_HOST", "")
    username = os.environ.get("SBM_USERNAME", "")
    password = os.environ.get("SBM_PASSWORD", "")
    if not all([host, username, password]):
        pytest.skip("SBM_AE_HOST, SBM_USERNAME, SBM_PASSWORD not set")
    return SBMClient(host, username, password, verify_ssl=False)


@pytest.mark.integration
def test_auth_succeeds():
    client = _client()
    client.check_auth()  # should not raise


@pytest.mark.integration
def test_list_items_by_report():
    client = _client()
    report_id = int(os.environ.get("SBM_DEFAULT_REPORT", "2208"))
    items = client.list_items_by_report(report_id, fields=["TITLE"], page_size=5)
    assert isinstance(items, list)


@pytest.mark.integration
def test_get_item_by_display_id():
    client = _client()
    display_id = os.environ.get("SBM_DEMO_DISPLAY_ID", "")
    if not display_id:
        pytest.skip("SBM_DEMO_DISPLAY_ID not set")
    table_id = int(os.environ.get("SBM_DEFAULT_TABLE", "1000"))
    result = client.get_item_by_display_id(display_id, table_id, fields=["TITLE"])
    assert "item" in result
    assert result["item"]["id"]["itemIdPrefixed"] == display_id
