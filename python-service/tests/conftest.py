import pytest


@pytest.fixture(autouse=True)
def mock_conductor(monkeypatch):
    monkeypatch.setattr(
        "app.start_conductor_workflow",
        lambda **kwargs: "00000000-0000-0000-0000-000000000000",
    )


@pytest.fixture(autouse=True)
def conductor_calls(monkeypatch):
    calls = []

    def fake_start(**kwargs):
        calls.append(kwargs)
        return "00000000-0000-0000-0000-000000000000"

    monkeypatch.setattr("app.start_conductor_workflow", fake_start)
    return calls