from sbm_cli import formatters


def _make_item(display_id: str, title: str, state: str = "Open") -> dict:
    return {
        "id": {"id": 100, "itemIdPrefixed": display_id},
        "fields": {
            "TITLE": {"value": title},
            "STATE": {"value": state},
            "OWNER": {"value": {"id": 1, "name": "Smith, Alice"}},
            "SECONDARYOWNER": {"value": {"id": -155, "name": "L3 Example Team"}},
        },
    }


def test_format_ticket_list_contains_id_and_title():
    items = [_make_item("02440942", "Test ticket")]
    output = formatters.format_ticket_list(items)
    assert "02440942" in output
    assert "Test ticket" in output


def test_format_ticket_list_empty():
    output = formatters.format_ticket_list([])
    assert isinstance(output, str)


def test_format_ticket_contains_fields():
    item = _make_item("02440942", "Test ticket")
    output = formatters.format_ticket(item)
    assert "02440942" in output
    assert "TITLE" in output
    assert "Test ticket" in output


def test_format_schema_contains_transitions():
    schema = {
        "connection": {"host": "https://sbm.test", "table_id": 1000},
        "defaults": {"report_id": 2208},
        "transitions": {
            "assign": {"id": 155, "required_fields": ["OWNER"]},
        },
        "teams": {},
    }
    output = formatters.format_schema(schema)
    assert "assign" in output
    assert "155" in output


def test_format_teams_contains_slug_and_name():
    teams = {"my-team": {"id": 155, "name": "L3 Example Team"}}
    output = formatters.format_teams(teams)
    assert "my-team" in output
    assert "L3 Example Team" in output
    assert "155" in output


def test_format_teams_empty():
    output = formatters.format_teams({})
    assert "No teams" in output


def test_format_field_values_contains_id_and_name():
    items = [{"id": 1701, "name": "Other cause"}, {"id": 1700, "name": "User side issue"}]
    output = formatters.format_field_values(items)
    assert "1701" in output
    assert "Other cause" in output


def test_format_ticket_list_dynamic_columns():
    items = [
        {
            "id": {"id": 1, "itemIdPrefixed": "00001"},
            "fields": {
                "TITLE": {"value": "Bug report"},
                "CUSTOM_SEVERITY": {"value": "Critical"},
            }
        }
    ]
    output = formatters.format_ticket_list(items, columns=["TITLE", "CUSTOM_SEVERITY"])
    assert "Bug report" in output
    assert "Critical" in output
    # Default "Team" column should NOT appear when custom columns are given
    assert "Team" not in output


def test_format_ticket_list_default_columns_unchanged():
    items = [
        {
            "id": {"id": 1, "itemIdPrefixed": "00001"},
            "fields": {
                "TITLE": {"value": "Ticket"},
                "STATE": {"value": "Open"},
            }
        }
    ]
    output = formatters.format_ticket_list(items)  # no columns arg
    assert "Ticket" in output
    assert "Open" in output
