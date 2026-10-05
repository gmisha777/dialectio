"""Import concepts and word forms from Wikidata Lexemes, with audio metadata from Wikimedia Commons.

Concepts are the Wikidata items that English Swadesh-list lexemes point to (P5137 "item for
this sense"). For each concept we take the lexemes in LANGUAGES that point to the same item,
with IPA (P898) and pronunciation audio (P443) from the lemma form.

Re-runnable: concepts and varieties are upserted, forms from this source are replaced.

Run from backend/:  uv run python -m app.importers.wikidata_lexemes
"""

import re
import time
from collections import defaultdict
from collections.abc import Iterable, Iterator
from dataclasses import dataclass, field
from pathlib import Path
from typing import TypeVar
from urllib.parse import unquote

import httpx2
from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from app.db.session import SessionLocal
from app.importers.common import upsert_source
from app.importers.languages import LANGUAGES, Language
from app.models import Audio, Concept, Form, Region, Variety

SPARQL_URL = "https://query.wikidata.org/sparql"
COMMONS_API = "https://commons.wikimedia.org/w/api.php"
USER_AGENT = "Dialectio/0.1 (https://github.com/gmisha777/dialectio)"
SWADESH_FILE = Path(__file__).parent / "data" / "swadesh_en.txt"

# Keep only concepts that have a word in at least this many of our languages.
MIN_LANGUAGES = 8
CONCEPT_BATCH = 10
LEXEME_BATCH = 50
COMMONS_BATCH = 50
# Be polite to the public endpoints (seconds between requests).
REQUEST_PAUSE = 1.0

ENTITY_PREFIX = "http://www.wikidata.org/entity/"
FILEPATH_MARKER = "Special:FilePath/"


@dataclass
class Lexeme:
    lexeme_id: str
    lemma: str
    ipas: list[str] = field(default_factory=list)
    audio_files: list[str] = field(default_factory=list)

    @property
    def number(self) -> int:
        return int(self.lexeme_id.removeprefix("L"))


@dataclass
class CommonsFile:
    url: str
    license: str
    artist: str | None


T = TypeVar("T")


def chunks(items: list[T], size: int) -> Iterator[list[T]]:
    for i in range(0, len(items), size):
        yield items[i : i + size]


def entity_id(uri: str) -> str:
    return uri.removeprefix(ENTITY_PREFIX)


def literal(value: str) -> str:
    return '"' + value.replace("\\", "\\\\").replace('"', '\\"') + '"'


class WikimediaClient:
    def __init__(self) -> None:
        self.http = httpx2.Client(headers={"User-Agent": USER_AGENT}, timeout=90)

    def get_json(self, url: str, params: dict[str, str]) -> dict:
        for attempt in range(8):
            time.sleep(REQUEST_PAUSE)
            response = self.http.get(url, params=params)
            if response.status_code in (429, 500, 502, 503, 504):
                wait = int(response.headers.get("Retry-After", 0)) or 5 * (attempt + 1)
                print(f"  {response.status_code}, retrying in {wait}s ...")
                time.sleep(wait)
                continue
            response.raise_for_status()
            return response.json()
        response.raise_for_status()
        raise RuntimeError("unreachable")

    def sparql(self, query: str) -> list[dict[str, str]]:
        data = self.get_json(SPARQL_URL, {"query": query, "format": "json"})
        return [
            {key: cell["value"] for key, cell in row.items()} for row in data["results"]["bindings"]
        ]


def find_concepts(client: WikimediaClient, lemmas: list[str]) -> list[str]:
    qids: set[str] = set()
    for batch in chunks(lemmas, 100):
        values = " ".join(f"{literal(lemma)}@en" for lemma in batch)
        rows = client.sparql(f"""
            SELECT DISTINCT ?item WHERE {{
              VALUES ?lemma {{ {values} }}
              ?lex dct:language wd:Q1860 ; wikibase:lemma ?lemma ;
                   ontolex:sense/wdt:P5137 ?item .
            }}""")
        qids.update(entity_id(row["item"]) for row in rows)
    return sorted(qids, key=lambda q: int(q[1:]))


def fetch_lexemes(
    client: WikimediaClient, qids: list[str], languages: Iterable[Language]
) -> dict[tuple[str, str], dict[str, Lexeme]]:
    """Return {(concept qid, language qid): {lexeme id: Lexeme}}."""
    lang_values = " ".join(f'(wd:{lang.wikidata_id} "{lang.lemma_tag}")' for lang in languages)
    result: dict[tuple[str, str], dict[str, Lexeme]] = defaultdict(dict)
    by_id: dict[str, Lexeme] = {}

    # Step 1: concept -> lexemes. The optimizer hint keeps the join starting from the (few)
    # concept items instead of from all lexemes of a language, which times out.
    for i, batch in enumerate(chunks(qids, CONCEPT_BATCH), 1):
        items = " ".join(f"wd:{qid}" for qid in batch)
        rows = client.sparql(f"""
            SELECT ?item ?lang ?lex ?lemma WHERE {{
              hint:Query hint:optimizer "None" .
              VALUES ?item {{ {items} }}
              ?sense wdt:P5137 ?item .
              ?lex ontolex:sense ?sense ; dct:language ?lang ; wikibase:lemma ?lemma .
              VALUES (?lang ?tag) {{ {lang_values} }}
              FILTER(LANG(?lemma) = ?tag)
            }}""")
        for row in rows:
            lemma = row["lemma"].strip()
            if is_affix_or_abbreviation(lemma):
                continue
            lexeme_id = entity_id(row["lex"])
            lexeme = by_id.setdefault(lexeme_id, Lexeme(lexeme_id, lemma))
            result[(entity_id(row["item"]), entity_id(row["lang"]))][lexeme_id] = lexeme
        print(f"  concepts batch {i}: {len(rows)} lexeme links")

    # Step 2: lexeme -> IPA and audio of the lemma form.
    lexeme_ids = sorted(by_id, key=lambda lid: int(lid[1:]))
    for batch in chunks(lexeme_ids, LEXEME_BATCH):
        values = " ".join(f"wd:{lid}" for lid in batch)
        rows = client.sparql(f"""
            SELECT ?lex ?ipa ?audio WHERE {{
              VALUES ?lex {{ {values} }}
              ?lex wikibase:lemma ?lemma ; ontolex:lexicalForm ?form .
              ?form ontolex:representation ?rep .
              FILTER(STR(?rep) = STR(?lemma))
              OPTIONAL {{ ?form wdt:P898 ?ipa }}
              OPTIONAL {{ ?form wdt:P443 ?audio }}
              FILTER(BOUND(?ipa) || BOUND(?audio))
            }}""")
        for row in rows:
            lexeme = by_id[entity_id(row["lex"])]
            if (ipa := row.get("ipa")) and ipa not in lexeme.ipas:
                lexeme.ipas.append(ipa)
            if (audio := row.get("audio")) and FILEPATH_MARKER in audio:
                name = unquote(audio.split(FILEPATH_MARKER, 1)[1])
                if name not in lexeme.audio_files:
                    lexeme.audio_files.append(name)
    print(f"  pronunciation data fetched for {len(lexeme_ids)} lexemes")
    return result


def is_affix_or_abbreviation(lemma: str) -> bool:
    return lemma.startswith("-") or lemma.endswith("-") or (lemma.isascii() and lemma.isupper())


def fetch_labels(client: WikimediaClient, qids: list[str]) -> dict[str, dict[str, str]]:
    """Return {qid: {label_en, label_uk, description_en, description_uk}}; keys may be missing."""
    labels: dict[str, dict[str, str]] = {}
    for batch in chunks(qids, 100):
        items = " ".join(f"wd:{qid}" for qid in batch)
        rows = client.sparql(f"""
            SELECT ?item ?label_en ?label_uk ?description_en ?description_uk WHERE {{
              VALUES ?item {{ {items} }}
              OPTIONAL {{ ?item rdfs:label ?label_en FILTER(LANG(?label_en) = "en") }}
              OPTIONAL {{ ?item rdfs:label ?label_uk FILTER(LANG(?label_uk) = "uk") }}
              OPTIONAL {{ ?item schema:description ?description_en
                          FILTER(LANG(?description_en) = "en") }}
              OPTIONAL {{ ?item schema:description ?description_uk
                          FILTER(LANG(?description_uk) = "uk") }}
            }}""")
        for row in rows:
            labels.setdefault(entity_id(row.pop("item")), row)
    return labels


def fetch_commons(client: WikimediaClient, names: list[str]) -> dict[str, CommonsFile]:
    files: dict[str, CommonsFile] = {}
    for batch in chunks(names, COMMONS_BATCH):
        data = client.get_json(
            COMMONS_API,
            {
                "action": "query",
                "format": "json",
                "formatversion": "2",
                "prop": "imageinfo",
                "iiprop": "url|extmetadata",
                "iiextmetadatafilter": "LicenseShortName|Artist",
                "titles": "|".join(f"File:{name}" for name in batch),
            },
        )
        query = data.get("query", {})
        normalized = {n["from"]: n["to"] for n in query.get("normalized", [])}
        pages = {page["title"]: page for page in query.get("pages", [])}
        for name in batch:
            title = f"File:{name}"
            page = pages.get(normalized.get(title, title))
            if not page or "imageinfo" not in page:
                continue
            info = page["imageinfo"][0]
            meta = info.get("extmetadata", {})
            license_name = meta.get("LicenseShortName", {}).get("value")
            if not license_name:
                continue  # never import audio without a known license
            artist = strip_html(meta.get("Artist", {}).get("value", "")) or None
            files[name] = CommonsFile(info["url"], license_name[:100], artist and artist[:200])
    return files


def strip_html(value: str) -> str:
    return re.sub(r"\s+", " ", re.sub(r"<[^>]+>", "", value)).strip()


def pick_primary(lexemes: Iterable[Lexeme]) -> Lexeme:
    # Prefer the lexeme with audio, then with IPA, then the oldest (usually the common word).
    return min(lexemes, key=lambda lx: (not lx.audio_files, not lx.ipas, lx.number))


def upsert_varieties(session: Session) -> dict[str, Variety]:
    regions = {r.code: r for r in session.scalars(select(Region).where(Region.level == "country"))}
    varieties: dict[str, Variety] = {}
    for lang in LANGUAGES:
        variety = session.scalar(select(Variety).where(Variety.wikidata_id == lang.wikidata_id))
        if variety is None:
            variety = Variety(wikidata_id=lang.wikidata_id)
            session.add(variety)
        variety.name_en = lang.name_en
        variety.name_uk = lang.name_uk
        variety.kind = "language"
        variety.iso639_3 = lang.iso639_3
        missing = [code for code in lang.countries if code not in regions]
        if missing:
            print(f"  warning: no region for {lang.name_en}: {missing}")
        variety.regions = [regions[code] for code in lang.countries if code in regions]
        varieties[lang.wikidata_id] = variety
    session.flush()
    return varieties


def main() -> None:
    client = WikimediaClient()
    lemmas = [
        line.strip()
        for line in SWADESH_FILE.read_text(encoding="utf-8").splitlines()
        if line.strip() and not line.startswith("#")
    ]

    print(f"Looking up concepts for {len(lemmas)} English lemmas ...")
    candidate_qids = find_concepts(client, lemmas)
    print(f"  {len(candidate_qids)} candidate concepts")

    print("Fetching lexemes ...")
    lexemes = fetch_lexemes(client, candidate_qids, LANGUAGES)
    coverage: dict[str, int] = defaultdict(int)
    for qid, _lang in lexemes:
        coverage[qid] += 1
    qids = [qid for qid in candidate_qids if coverage[qid] >= MIN_LANGUAGES]
    print(f"  {len(qids)} concepts have words in >= {MIN_LANGUAGES} languages")

    print("Fetching concept labels ...")
    labels = fetch_labels(client, qids)

    audio_names = sorted(
        {
            name
            for (qid, _lang), by_id in lexemes.items()
            if qid in qids
            for lexeme in by_id.values()
            for name in lexeme.audio_files
        }
    )
    print(f"Fetching license info for {len(audio_names)} audio files from Commons ...")
    commons = fetch_commons(client, audio_names)

    with SessionLocal() as session:
        wikidata = upsert_source(
            session,
            "Wikidata Lexemes",
            "https://www.wikidata.org/wiki/Wikidata:Lexicographical_data",
            "CC0 1.0",
        )
        commons_source = upsert_source(
            session, "Wikimedia Commons", "https://commons.wikimedia.org/", "Per file (see audio)"
        )
        varieties = upsert_varieties(session)

        concepts: dict[str, Concept] = {}
        for qid in qids:
            concept = session.scalar(select(Concept).where(Concept.wikidata_id == qid))
            if concept is None:
                concept = Concept(wikidata_id=qid, category="swadesh")
                session.add(concept)
            entry = labels.get(qid, {})
            concept.gloss_en = entry.get("label_en", qid)[:200]
            concept.gloss_uk = entry.get("label_uk")
            concept.description_en = (entry.get("description_en") or "")[:500] or None
            concept.description_uk = (entry.get("description_uk") or "")[:500] or None
            concepts[qid] = concept
        session.flush()

        session.execute(delete(Form).where(Form.source_id == wikidata.id))

        form_count = audio_count = 0
        for (qid, lang_qid), by_id in lexemes.items():
            if qid not in concepts:
                continue
            primary = pick_primary(by_id.values())
            seen_spellings: set[str] = set()
            for lexeme in sorted(by_id.values(), key=lambda lx: lx is not primary):
                if lexeme.lemma in seen_spellings:
                    continue
                seen_spellings.add(lexeme.lemma)
                form = Form(
                    concept=concepts[qid],
                    variety=varieties[lang_qid],
                    spelling=lexeme.lemma[:200],
                    ipa=lexeme.ipas[0][:200] if lexeme.ipas else None,
                    is_primary=lexeme is primary,
                    external_id=lexeme.lexeme_id,
                    source=wikidata,
                )
                for name in lexeme.audio_files:
                    if file := commons.get(name):
                        form.audio.append(
                            Audio(
                                url=file.url,
                                speaker=file.artist,
                                is_synthetic=False,
                                license=file.license,
                                source=commons_source,
                            )
                        )
                        audio_count += 1
                session.add(form)
                form_count += 1

        session.commit()

    print(
        f"Imported {len(concepts)} concepts, {form_count} forms, {audio_count} audio files "
        f"in {len(varieties)} languages."
    )


if __name__ == "__main__":
    main()
