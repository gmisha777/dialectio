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
    # Ukrainian first; Crimean Tatar is also mapped to Ukraine at country level
    assert labels["UKR"].split(" / ")[0] == "вода"


def test_concept_detail_404() -> None:
    assert client.get("/api/concepts/999999999").status_code == 404


def test_country_vector_tile() -> None:
    response = client.get("/api/regions/tiles/0/0/0.mvt")
    assert response.status_code == 200
    assert response.headers["content-type"] == "application/vnd.mapbox-vector-tile"
    assert len(response.content) > 1000
    # Layer name and attribute names are stored as strings inside the protobuf
    assert b"countries" in response.content and b"UKR" in response.content


def test_vector_tile_out_of_range() -> None:
    assert client.get("/api/regions/tiles/1/2/0.mvt").status_code == 404


def test_labels_use_curated_point_and_rank() -> None:
    concept_id = search("water")[0]["concept"]["id"]
    labels = client.get(f"/api/concepts/{concept_id}").json()["labels"]["features"]
    russia = next(f for f in labels if f["properties"]["code"] == "RUS")
    lng, lat = russia["geometry"]["coordinates"]
    assert lng < 60  # European Russia, not the middle of Siberia
    ranks = [f["properties"]["rank"] for f in labels]
    assert ranks == sorted(ranks)


def test_concept_by_slug_and_listing() -> None:
    water = client.get("/api/concepts/by-slug/water").json()
    assert water["wikidata_id"] == "Q283"
    assert water["slug"] == "water"
    assert client.get("/api/concepts/by-slug/no-such-word").status_code == 404

    slugs = {c["slug"] for c in client.get("/api/concepts").json()}
    assert {"water", "bark-q38681", "bark-q184453"} <= slugs


def test_region_labels_show_dialect_words() -> None:
    from sqlalchemy import select

    from app.db.session import SessionLocal
    from app.models import Concept, Form, Variety

    with SessionLocal() as session:
        concept = session.scalar(select(Concept).where(Concept.wikidata_id == "Q283"))
        hutsul = session.scalar(select(Variety).where(Variety.code == "ukr-hutsul"))
        form = Form(concept=concept, variety=hutsul, spelling="тестводиця", is_primary=True)
        session.add(form)
        session.commit()
        form_id = form.id
    try:
        labels = {
            f["properties"]["code"]: f["properties"]
            for f in client.get("/api/concepts/by-slug/water").json()["labels"]["features"]
        }
        # Hutsul is mapped to Ivano-Frankivsk, Chernivtsi and Transcarpathia
        assert labels["UA-26"]["text"] == "тестводиця"
        assert labels["UA-26"]["dialect"] and labels["UA-26"]["parent_code"] == "UKR"
        # other oblasts inherit the standard Ukrainian word; Crimea adds Crimean Tatar
        assert labels["UA-63"]["text"] == "вода" and not labels["UA-63"]["dialect"]
        assert labels["UA-43"]["text"].split(" / ")[0] == "вода"
        assert len(labels["UA-43"]["text"].split(" / ")) == 2
    finally:
        with SessionLocal() as session:
            session.delete(session.get(Form, form_id))
            session.commit()
