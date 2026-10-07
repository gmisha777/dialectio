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
    response = client.get("/api/editor/concepts", params={"variety": lang}, headers=auth())
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
    # a concept with no word at all in this dialect: the new word becomes the main one
    missing = next(c for c in concepts("ukr-hutsul") if not c["forms"])
    payload = {"concept_id": missing["id"], "variety": "ukr-hutsul", "spelling": "  тестслово "}

    created = client.post("/api/editor/forms", json=payload, headers=auth())
    assert created.status_code == 201
    form = created.json()
    try:
        assert form["spelling"] == "тестслово"
        assert form["is_primary"] and form["editable"]

        duplicate = client.post("/api/editor/forms", json=payload, headers=auth())
        assert duplicate.status_code == 409

        detail = client.get(f"/api/concepts/{missing['id']}").json()
        hutsul = next(lang for lang in detail["languages"] if lang["code"] == "ukr-hutsul")
        assert hutsul["forms"][0]["spelling"] == "тестслово"
    finally:
        deleted = client.delete(f"/api/editor/forms/{form['id']}", headers=auth())
    assert deleted.status_code == 204
    assert not next(c for c in concepts("ukr-hutsul") if c["id"] == missing["id"])["forms"]


def test_cannot_delete_imported_word() -> None:
    water = next(c for c in concepts() if c["wikidata_id"] == "Q283")
    response = client.delete(f"/api/editor/forms/{water['forms'][0]['id']}", headers=auth())
    assert response.status_code == 403


def test_pending_draft_is_public_but_unverified_until_approved() -> None:
    from sqlalchemy import select

    from app.api.editor import EDITOR_SOURCE_LICENSE, EDITOR_SOURCE_URL, SUGGESTION_SOURCE_NAME
    from app.db.session import SessionLocal
    from app.importers.common import upsert_source
    from app.models import PENDING, Form, Variety

    concept = next(c for c in concepts("ukr-hutsul") if not c["forms"])
    with SessionLocal() as session:
        source = upsert_source(
            session, SUGGESTION_SOURCE_NAME, EDITOR_SOURCE_URL, EDITOR_SOURCE_LICENSE
        )
        hutsul = session.scalar(select(Variety).where(Variety.code == "ukr-hutsul"))
        draft = Form(
            concept_id=concept["id"],
            variety=hutsul,
            spelling="чернеткатест",
            status=PENDING,
            is_primary=True,
            source=source,
        )
        session.add(draft)
        session.commit()
        draft_id = draft.id

    def public_form() -> dict:
        detail = client.get(f"/api/concepts/{concept['id']}").json()
        lang = next(lang for lang in detail["languages"] if lang["code"] == "ukr-hutsul")
        return lang["forms"][0]

    try:
        hits = client.get("/api/search", params={"q": "чернеткатест"}).json()
        assert hits and hits[0]["matched_spelling"] == "чернеткатест"
        assert public_form()["unverified"]

        approved = client.post(f"/api/editor/forms/{draft_id}/approve", headers=auth())
        assert approved.status_code == 200
        assert approved.json()["status"] == "approved"
        assert approved.json()["is_primary"]
        assert approved.json()["source"] == "Dialectio editors"
        assert (
            client.post(f"/api/editor/forms/{draft_id}/approve", headers=auth()).status_code == 409
        )
        assert not public_form()["unverified"]
    finally:
        client.delete(f"/api/editor/forms/{draft_id}", headers=auth())


def test_new_word_is_added_as_variant_and_star_makes_it_main() -> None:
    concept = next(
        c
        for c in concepts()
        if any(f["status"] == "pending" and f["is_primary"] for f in c["forms"])
    )
    draft = next(f for f in concept["forms"] if f["status"] == "pending" and f["is_primary"])
    payload = {"concept_id": concept["id"], "variety": "ukr", "spelling": "моєслово"}
    created = client.post("/api/editor/forms", json=payload, headers=auth()).json()

    def forms() -> dict[int, dict]:
        row = next(c for c in concepts() if c["id"] == concept["id"])
        return {f["id"]: f for f in row["forms"]}

    try:
        # added next to the existing main word, which stays main
        assert not created["is_primary"]
        assert forms()[draft["id"]]["is_primary"]
        # ★ makes it the main word
        starred = client.post(f"/api/editor/forms/{created['id']}/primary", headers=auth())
        assert starred.status_code == 200 and starred.json()["is_primary"]
        assert not forms()[draft["id"]]["is_primary"]
    finally:
        client.delete(f"/api/editor/forms/{created['id']}", headers=auth())
    # deleting the main word gives the role back to the draft
    assert forms()[draft["id"]]["is_primary"]
