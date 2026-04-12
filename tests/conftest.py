import pytest
from click.testing import CliRunner


@pytest.fixture
def runner():
    return CliRunner()


@pytest.fixture
def sample_config():
    from sbm_cli.config import Config, TransitionConfig, TeamConfig
    return Config(
        host="https://sbm.test",
        username="testuser",
        password="testpass",
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
        teams={
            "market-finance": TeamConfig(id=155, name="L3 SD Market Finance"),
        },
    )


@pytest.fixture
def mock_session(mocker):
    return mocker.patch("requests.Session")
