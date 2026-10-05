"""Integration tests against the local database with imported data.

Skipped when the database is not reachable or the importers have not been run.
"""

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import text
from sqlalchemy.exc import OperationalError

from app.db.session import engine
from app.main import app


def _has_data() -> bool:
    try:
        with engine.connect() as conn:
            return bool(conn.execute(text("SELECT EXISTS (SELECT 1 FROM form)")).scalar())
    except OperationalError:
        return False


pytestmark = pytest.mark.skipif(not _has_data(), reason="database with imported data required")

client = TestClient(app)


def search(q: str, **params: str) -> list[dict]:
    response = client.get("/api/search", params={"q": q, **params})
    assert response.status_code == 200
    return response.json()


def test_search_finds_same_concept_from_any_language() -> None:
    concept_ids = {search(q)[0]["concept"]["wikidata_id"] for q in ("water", "Wasser", "woda")}
    assert concept_ids == {"Q283"}


def test_search_prefers_requested_language_on_shared_spelling() -> None:
    assert search("вода", prefer="ukr")[0]["matched_language_en"] == "Ukrainian"
    assert search("вода", prefer="rus")[0]["matched_language_en"] == "Russian"


def test_search_treats_like_wildcards_literally() -> None:
    assert search("%") == []


def test_concept_detail_has_forms_and_map_labels() -> None:
    concept_id = search("water")[0]["concept"]["id"]
    detail = client.get(f"/api/concepts/{concept_id}").json()

    english = next(lang for lang in detail["languages"] if lang["iso639_3"] == "eng")
    assert english["forms"][0]["spelling"] == "water"
    assert english["forms"][0]["is_primary"]
    assert "GBR" in english["region_codes"]

    labels = {
        f["properties"]["code"]: f["properties"]["text"] for f in detail["labels"]["features"]
    }
    assert labels["UKR"] == "вода"


def test_concept_detail_404() -> None:
    assert client.get("/api/concepts/999999999").status_code == 404


def test_countries_geojson() -> None:
    response = client.get("/api/regions/countries.geojson")
    assert response.status_code == 200
    codes = {f["properties"]["code"] for f in response.json()["features"]}
    assert {"UKR", "FRA", "NOR"} <= codes
