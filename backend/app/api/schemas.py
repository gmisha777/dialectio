from typing import Any

from pydantic import BaseModel, ConfigDict


class ORMModel(BaseModel):
    model_config = ConfigDict(from_attributes=True)


class ConceptSummary(ORMModel):
    id: int
    wikidata_id: str | None
    slug: str | None
    gloss_en: str
    gloss_uk: str | None
    description_en: str | None
    description_uk: str | None


class ConceptLink(ORMModel):
    slug: str
    gloss_en: str
    gloss_uk: str | None


class SearchHit(BaseModel):
    concept: ConceptSummary
    matched_spelling: str
    matched_language_en: str
    matched_language_uk: str | None


class AudioOut(ORMModel):
    url: str
    license: str
    speaker: str | None
    is_synthetic: bool


class FormOut(BaseModel):
    spelling: str
    ipa: str | None
    transliteration: str | None
    is_primary: bool
    external_id: str | None
    source: str | None = None
    # True for words not checked by a person or a dictionary (taken from concept labels or
    # generated automatically); the site marks them as possibly inaccurate.
    unverified: bool = False
    audio: list[AudioOut]


class LanguageForms(BaseModel):
    variety_id: int
    code: str
    # "language", "dialect_group" or "dialect"
    kind: str
    parent_code: str | None
    iso639_3: str | None
    name_en: str
    name_uk: str | None
    region_codes: list[str]
    forms: list[FormOut]


class ConceptDetail(ConceptSummary):
    languages: list[LanguageForms]
    # GeoJSON FeatureCollection of points: one label per region with its primary spellings
    labels: dict[str, Any]
