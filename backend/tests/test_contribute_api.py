"""Integration tests for visitor contributions (need the local database with imported data)."""

import pytest
from fastapi.testclient import TestClient

from app.api import contribute
from app.config import MEDIA_DIR, settings
from app.main import app
from tests.test_lexicon_api import pytestmark  # noqa: F401  (skip without data)

TOKEN = "test-token"
client = TestClient(app)


@pytest.fixture(autouse=True)
def setup(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(settings, "editor_token", TOKEN)
    contribute._recent.clear()


def editor(method: str, path: str) -> dict | list:
    response = client.request(method, f"/api/editor{path}", headers={"X-Editor-Token": TOKEN})
    assert response.status_code in (200, 204), response.text
    return response.json() if response.status_code == 200 else {}


def water_id() -> int:
    return client.get("/api/concepts/by-slug/water").json()["id"]


def submit(**overrides: object) -> object:
    data = {
        "concept_id": str(water_id()),
        "variety": "ukr-hutsul",
        "spelling": "вудатест",
        "consent": "true",
        "place": "Верховина",
        "contributor": "Тестер",
    }
    files = overrides.pop("files", None)
    data.update({k: str(v) for k, v in overrides.items()})
    return client.post("/api/contributions", data=data, files=files)


def find_submission(spelling: str) -> dict | None:
    return next(
        (s for s in editor("GET", "/submissions") if s["form"]["spelling"] == spelling), None
    )


def test_submission_is_hidden_until_approved_and_keeps_attribution() -> None:
    audio = ("rec.webm", b"\x1aE\xdf\xa3fake-webm", "audio/webm")
    response = submit(files={"audio": audio})
    assert response.status_code == 201
    submission = find_submission("вудатест")
    assert submission is not None
    form = submission["form"]
    try:
        assert submission["variety_code"] == "ukr-hutsul"
        assert form["contributor"] == "Тестер" and form["place"] == "Верховина"
        assert len(form["audio_urls"]) == 1
        audio_file = MEDIA_DIR / form["audio_urls"][0].removeprefix("/media/")
        assert audio_file.exists()
        assert client.get("/api/search", params={"q": "вудатест"}).json() == []

        approved = editor("POST", f"/forms/{form['id']}/approve")
        assert approved["status"] == "approved" and approved["is_primary"]
        assert approved["source"] == "Dialectio contributors"
        hits = client.get("/api/search", params={"q": "вудатест"}).json()
        assert hits and hits[0]["matched_spelling"] == "вудатест"
    finally:
        editor("DELETE", f"/forms/{form['id']}")
    assert not audio_file.exists()


def test_duplicate_submission_is_not_stored_twice() -> None:
    first = submit(spelling="двічітест")
    second = submit(spelling="двічітест")
    found = find_submission("двічітест")
    try:
        assert first.status_code == 201 and second.status_code == 201
        assert second.json()["status"] == "exists"
    finally:
        if found:
            editor("DELETE", f"/forms/{found['form']['id']}")


def test_honeypot_is_silently_ignored() -> None:
    assert submit(spelling="ботслово", website="http://spam").status_code == 201
    assert find_submission("ботслово") is None


def test_consent_is_required() -> None:
    assert submit(consent="false").status_code == 422


def test_rejects_unknown_variety_and_non_audio_files() -> None:
    assert submit(variety="ukr-north").status_code == 404  # dialect groups aren't selectable
    text_file = ("notes.txt", b"hello", "text/plain")
    assert submit(files={"audio": text_file}).status_code == 415


def test_rate_limit(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(contribute, "RATE_LIMIT", 2)
    created = []
    try:
        for i in range(2):
            assert submit(spelling=f"лімітслово{i}").status_code == 201
            created.append(f"лімітслово{i}")
        assert submit(spelling="лімітслово9").status_code == 429
    finally:
        for spelling in created:
            if (found := find_submission(spelling)) is not None:
                editor("DELETE", f"/forms/{found['form']['id']}")


def test_public_variety_list() -> None:
    varieties = {v["code"]: v for v in client.get("/api/varieties").json()}
    assert varieties["ukr-hutsul"]["parent_code"] == "ukr-southwest"
    assert "ukr-north" not in varieties
