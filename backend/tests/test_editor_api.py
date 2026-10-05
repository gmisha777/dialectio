"""Integration tests for the word editor (need the local database with imported data)."""

import pytest
from fastapi.testclient import TestClient

from app.config import settings
from app.main import app
from tests.test_lexicon_api import pytestmark  # noqa: F401  (skip without data)

TOKEN = "test-token"
client = TestClient(app)


@pytest.fixture(autouse=True)
def editor_token(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(settings, "editor_token", TOKEN)


def auth(token: str = TOKEN) -> dict[str, str]:
    return {"X-Editor-Token": token}


def concepts(lang: str = "ukr") -> list[dict]:
    response = client.get("/api/editor/concepts", params={"lang": lang}, headers=auth())
    assert response.status_code == 200
    return response.json()


def test_requires_token() -> None:
    assert client.get("/api/editor/concepts").status_code == 401
    assert client.get("/api/editor/concepts", headers=auth("wrong")).status_code == 401


def test_disabled_without_configured_token(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(settings, "editor_token", "")
    assert client.get("/api/editor/concepts", headers=auth()).status_code == 503


def test_lists_concepts_with_hints() -> None:
    water = next(c for c in concepts() if c["wikidata_id"] == "Q283")
    assert water["hints"]["eng"] == "water"
    assert [f["spelling"] for f in water["forms"]] == ["вода"]
    assert not water["forms"][0]["editable"]  # imported from Wikidata


def test_add_and_delete_word() -> None:
    missing = next(c for c in concepts() if not c["forms"])
    payload = {"concept_id": missing["id"], "iso639_3": "ukr", "spelling": "  тестслово "}

    created = client.post("/api/editor/forms", json=payload, headers=auth())
    assert created.status_code == 201
    form = created.json()
    try:
        assert form["spelling"] == "тестслово"
        assert form["is_primary"] and form["editable"]

        duplicate = client.post("/api/editor/forms", json=payload, headers=auth())
        assert duplicate.status_code == 409

        detail = client.get(f"/api/concepts/{missing['id']}").json()
        ukrainian = next(lang for lang in detail["languages"] if lang["iso639_3"] == "ukr")
        assert ukrainian["forms"][0]["spelling"] == "тестслово"
    finally:
        deleted = client.delete(f"/api/editor/forms/{form['id']}", headers=auth())
    assert deleted.status_code == 204
    assert not next(c for c in concepts() if c["id"] == missing["id"])["forms"]


def test_cannot_delete_imported_word() -> None:
    water = next(c for c in concepts() if c["wikidata_id"] == "Q283")
    response = client.delete(f"/api/editor/forms/{water['forms'][0]['id']}", headers=auth())
    assert response.status_code == 403
