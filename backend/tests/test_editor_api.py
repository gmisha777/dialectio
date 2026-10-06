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


def approved_forms(concept: dict) -> list[dict]:
    return [f for f in concept["forms"] if f["status"] == "approved"]


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
    missing = next(c for c in concepts() if not approved_forms(c))
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
    assert not approved_forms(next(c for c in concepts() if c["id"] == missing["id"]))


def test_cannot_delete_imported_word() -> None:
    water = next(c for c in concepts() if c["wikidata_id"] == "Q283")
    response = client.delete(f"/api/editor/forms/{water['forms'][0]['id']}", headers=auth())
    assert response.status_code == 403


def test_pending_draft_is_hidden_until_approved() -> None:
    from sqlalchemy import select

    from app.api.editor import EDITOR_SOURCE_LICENSE, EDITOR_SOURCE_URL, SUGGESTION_SOURCE_NAME
    from app.db.session import SessionLocal
    from app.importers.common import upsert_source
    from app.models import PENDING, Form, Variety

    missing = next(c for c in concepts() if not approved_forms(c))
    with SessionLocal() as session:
        source = upsert_source(
            session, SUGGESTION_SOURCE_NAME, EDITOR_SOURCE_URL, EDITOR_SOURCE_LICENSE
        )
        ukr = session.scalar(select(Variety).where(Variety.iso639_3 == "ukr"))
        draft = Form(
            concept_id=missing["id"],
            variety=ukr,
            spelling="чернеткатест",
            status=PENDING,
            source=source,
        )
        session.add(draft)
        session.commit()
        draft_id = draft.id
    try:
        assert client.get("/api/search", params={"q": "чернеткатест"}).json() == []
        row = next(c for c in concepts() if c["id"] == missing["id"])
        assert row["forms"][0]["status"] == "pending" and row["forms"][0]["editable"]

        approved = client.post(f"/api/editor/forms/{draft_id}/approve", headers=auth())
        assert approved.status_code == 200
        assert approved.json()["status"] == "approved"
        assert approved.json()["is_primary"]
        assert approved.json()["source"] == "Dialectio editors"
        assert (
            client.post(f"/api/editor/forms/{draft_id}/approve", headers=auth()).status_code == 409
        )

        hits = client.get("/api/search", params={"q": "чернеткатест"}).json()
        assert hits and hits[0]["matched_spelling"] == "чернеткатест"
    finally:
        client.delete(f"/api/editor/forms/{draft_id}", headers=auth())
