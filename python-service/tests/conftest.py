import pytest

from app import app

FAKE_CONDUCTOR_ID = "00000000-0000-0000-0000-000000000000"


@pytest.fixture
def client():
    app.config["TESTING"] = True
    with app.test_client() as client:
        yield client


@pytest.fixture(autouse=True)
def conductor_calls(monkeypatch):
    """Replace the Conductor call and record what the app sends."""
    calls = []

    def fake_start(**kwargs):
        calls.append(kwargs)
        return FAKE_CONDUCTOR_ID

    monkeypatch.setattr("app.start_conductor_workflow", fake_start)
    return calls
