"""Import concepts and word forms from Wikidata Lexemes, with audio metadata from Wikimedia Commons.

Concepts are the Wikidata items that English Swadesh-list lexemes point to (P5137 "item for
this sense"). For each concept we take the lexemes in LANGUAGES that point to the same item,
with IPA (P898) and pronunciation audio (P443) from the lemma form.

Re-runnable: concepts and varieties are upserted, forms from this source are replaced.

Run from backend/:  uv run python -m app.importers.wikidata_lexemes
"""

import os
import re
import time
from collections import defaultdict
from collections.abc import Iterable, Iterator
from dataclasses import dataclass, field
from pathlib import Path
from typing import TypeVar
from urllib.parse import unquote

import httpx2
from sqlalchemy import delete, select, text
from sqlalchemy.orm import Session, selectinload

from app.api.lexicon import MACHINE_SOURCE_NAME
from app.db.session import SessionLocal
from app.importers.common import upsert_source
from app.importers.languages import LANGUAGES, Language
from app.models import Audio, Concept, Form, Region, Variety
from app.slugs import assign_missing_slugs

SPARQL_URL = "https://query.wikidata.org/sparql"
COMMONS_API = "https://commons.wikimedia.org/w/api.php"
USER_AGENT = "Dialectio/0.1 (https://github.com/gmisha777/dialectio)"
DATA_DIR = Path(__file__).parent / "data"
# English word lists that seed concepts, as (concept category, file). Earlier lists win when
# the same concept is reached from several lists.
WORD_LISTS = (
    ("swadesh", DATA_DIR / "swadesh_en.txt"),
    ("everyday", DATA_DIR / "everyday_en.txt"),
)
EXCLUDED_FILE = DATA_DIR / "excluded_concepts.txt"

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
    # Concepts for which this lexeme's sense carries a language style (P6191: slang,
    # informal, jargon, ...); such words are never chosen as the main word.
    styled_for: set[str] = field(default_factory=set)

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


def read_list(path: Path) -> list[str]:
    """Non-empty lines of a data file, without "#" comments."""
    lines = (
        line.split("#", 1)[0].strip() for line in path.read_text(encoding="utf-8").splitlines()
    )
    return [line for line in lines if line]


def find_concepts(client: WikimediaClient, lemmas: list[str]) -> dict[str, str]:
    """Return {concept qid: English lemma that led to it}, ordered by qid."""
    found: dict[str, str] = {}
    order = {lemma: i for i, lemma in enumerate(lemmas)}
    for batch in chunks(lemmas, 100):
        values = " ".join(f"{literal(lemma)}@en" for lemma in batch)
        rows = client.sparql(f"""
            SELECT DISTINCT ?item ?lemma WHERE {{
              VALUES ?lemma {{ {values} }}
              ?lex dct:language wd:Q1860 ; wikibase:lemma ?lemma ;
                   ontolex:sense/wdt:P5137 ?item .
            }}""")
        for row in rows:
            qid, lemma = entity_id(row["item"]), row["lemma"]
            if qid not in found or order[lemma] < order[found[qid]]:
                found[qid] = lemma
    return dict(sorted(found.items(), key=lambda item: int(item[0][1:])))


def english_gloss(label: str | None, lemma: str) -> str:
    """The concept's English label, or the word that led to it when the label is unusable.

    Taxa are labelled with Latin names ("Camelus", "Quercus"); a capitalised label for a
    lowercase lemma is treated as one and replaced by the plain word ("camel", "oak").
    Proper nouns like "January" match their lemma and are kept.
    """
    if not label or (label.lower() != lemma.lower() and label[0].isupper() and lemma[0].islower()):
        return lemma[:200]
    return label[:200]


def usable_label(label: str | None) -> str | None:
    # Numbers are labelled "1", "2", ... and some items have no label at all.
    return label if label and not label.isdigit() else None


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
            SELECT ?item ?lang ?lex ?lemma ?style WHERE {{
              hint:Query hint:optimizer "None" .
              VALUES ?item {{ {items} }}
              ?sense wdt:P5137 ?item .
              ?lex ontolex:sense ?sense ; dct:language ?lang ; wikibase:lemma ?lemma .
              VALUES (?lang ?tag) {{ {lang_values} }}
              FILTER(LANG(?lemma) = ?tag)
              OPTIONAL {{ ?sense wdt:P6191 ?style }}
            }}""")
        for row in rows:
            lemma = row["lemma"].strip()
            if is_affix_or_abbreviation(lemma):
                continue
            lexeme_id = entity_id(row["lex"])
            lexeme = by_id.setdefault(lexeme_id, Lexeme(lexeme_id, lemma))
            qid = entity_id(row["item"])
            result[(qid, entity_id(row["lang"]))][lexeme_id] = lexeme
            if "style" in row:
                lexeme.styled_for.add(qid)
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


ITEM_LABELS_SOURCE = "Wikidata item labels"
# Languages that capitalise common nouns, so a capitalised label is not a sign of a name.
CAPITALISED_NOUNS = {"deu", "ltz"}


def label_as_word(label: str | None, english_label: str, iso639_3: str) -> bool:
    """Whether a concept label can stand in for a word: one token, no digits or brackets,
    and not a Latin taxon name copied from English ("Rhopalocera")."""
    if not label or len(label) > 40 or " " in label.strip():
        return False
    if any(ch.isdigit() or ch in "()[],;/" for ch in label):
        return False
    looks_latin_name = label[0].isupper() and label.lower() == english_label and label.isascii()
    return not (looks_latin_name and iso639_3 not in CAPITALISED_NOUNS | {"eng"})


def label_word(label: str, english_label: str, iso639_3: str) -> str:
    """Labels are often capitalised like titles ("Жаңбыр"); words are not, except in
    languages that capitalise nouns and for proper nouns (the English label is capitalised)."""
    if (
        iso639_3 not in CAPITALISED_NOUNS
        and label[:1].isupper()
        and label[1:] == label[1:].lower()
        and not english_label[:1].isupper()
    ):
        return label[0].lower() + label[1:]
    return label


def same_stem(a: str, b: str) -> bool:
    """Rough match of inflected forms ("риба" / "риби"): long common prefix."""
    common = len(os.path.commonprefix([a, b]))
    return common >= 3 and common >= min(len(a), len(b)) - 2


def pick_primary(
    lexemes: Iterable[Lexeme], item_label: str | None = None, item_qid: str | None = None
) -> Lexeme | None:
    """Choose the main word for a concept in one language; None means "use the label".

    The concept's Wikidata label in that language is normally the neutral, standard word, so
    a lexeme matching it wins ("голова", not the slang "тыква" that happens to have audio);
    then one that is a word of the label ("пес" for "пес свійський"), then one with the same
    stem. Senses marked with a language style (slang, informal, ...) never win over unmarked
    ones. Remaining ties fall back to audio, then IPA, then the oldest lexeme.

    When no lexeme resembles a one-word label, the label itself is the better main word
    (e.g. Russian "деньги" when only slang lexemes point to "money"): returns None.
    """
    label = (item_label or "").lower()
    label_words = label.split()

    def tier(lx: Lexeme) -> int:
        lemma = lx.lemma.lower()
        if lemma == label:
            return 0
        if lemma in label_words:
            return 1
        if any(same_stem(lemma, word) for word in label_words):
            return 2
        return 3

    def rank(lx: Lexeme) -> tuple[int, bool, bool, bool, int]:
        styled = item_qid is not None and item_qid in lx.styled_for
        return (tier(lx), styled, not lx.audio_files, not lx.ipas, lx.number)

    best = min(lexemes, key=rank)
    if len(label_words) == 1 and tier(best) == 3:
        return None
    return best


def fetch_item_labels(
    client: WikimediaClient, qids: list[str], languages: Iterable[Language]
) -> dict[tuple[str, str], str]:
    """Return {(concept qid, language qid): the concept's Wikidata label in that language}."""
    lang_values = " ".join(f'(wd:{lang.wikidata_id} "{lang.lemma_tag}")' for lang in languages)
    labels: dict[tuple[str, str], str] = {}
    for batch in chunks(qids, 50):
        items = " ".join(f"wd:{qid}" for qid in batch)
        rows = client.sparql(f"""
            SELECT ?item ?lang ?label WHERE {{
              VALUES ?item {{ {items} }}
              VALUES (?lang ?tag) {{ {lang_values} }}
              ?item rdfs:label ?label .
              FILTER(LANG(?label) = ?tag)
            }}""")
        for row in rows:
            labels[(entity_id(row["item"]), entity_id(row["lang"]))] = row["label"]
    return labels


ENSURE_PRIMARY = text("""
    UPDATE form SET is_primary = true
    WHERE id IN (
        SELECT min(id) FROM form
        WHERE status = 'approved'
        GROUP BY concept_id, variety_id
        HAVING NOT bool_or(is_primary)
    )
""")


def ensure_one_primary(session: Session) -> int:
    """Give every (concept, language) without a primary form its oldest approved form."""
    return session.execute(ENSURE_PRIMARY).rowcount


def remove_stale_concepts(session: Session, current: set[str]) -> tuple[int, list[Concept]]:
    """Delete Wikidata concepts that are no longer imported (excluded or too little coverage).

    Runs after this source's forms were replaced, so remaining forms come from other sources;
    concepts that still have such forms are kept.
    """
    removed = 0
    kept: list[Concept] = []
    stale = session.scalars(
        select(Concept).where(Concept.wikidata_id.is_not(None), Concept.wikidata_id.not_in(current))
    )
    for concept in stale:
        if concept.forms:
            kept.append(concept)
        else:
            session.delete(concept)
            removed += 1
    session.flush()
    return removed, kept


def upsert_varieties(session: Session) -> dict[str, Variety]:
    # Languages can be mapped to countries or to first-level regions (e.g. Crimean Tatar).
    regions = {r.code: r for r in session.scalars(select(Region))}
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
        variety.code = lang.iso639_3
        missing = [code for code in lang.countries if code not in regions]
        if missing:
            print(f"  warning: no region for {lang.name_en}: {missing}")
        variety.regions = [regions[code] for code in lang.countries if code in regions]
        varieties[lang.wikidata_id] = variety
    session.flush()
    return varieties


def main() -> None:
    client = WikimediaClient()
    excluded = set(read_list(EXCLUDED_FILE))
    lemma_by_qid: dict[str, str] = {}
    category_by_qid: dict[str, str] = {}
    for category, path in WORD_LISTS:
        lemmas = read_list(path)
        print(f"Looking up concepts for {len(lemmas)} English lemmas ({category}) ...")
        for qid, lemma in find_concepts(client, lemmas).items():
            if qid not in lemma_by_qid:
                lemma_by_qid[qid] = lemma
                category_by_qid[qid] = category
    candidate_qids = [qid for qid in lemma_by_qid if qid not in excluded]
    print(f"  {len(candidate_qids)} candidate concepts ({len(excluded)} excluded by list)")

    print("Fetching lexemes ...")
    lexemes = fetch_lexemes(client, candidate_qids, LANGUAGES)
    coverage: dict[str, int] = defaultdict(int)
    for qid, _lang in lexemes:
        coverage[qid] += 1
    qids = [qid for qid in candidate_qids if coverage[qid] >= MIN_LANGUAGES]
    print(f"  {len(qids)} concepts have words in >= {MIN_LANGUAGES} languages")

    print("Fetching concept labels ...")
    labels = fetch_labels(client, qids)
    item_labels = fetch_item_labels(client, qids, LANGUAGES)

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
                concept = Concept(wikidata_id=qid, category=category_by_qid[qid])
                session.add(concept)
            entry = labels.get(qid, {})
            concept.gloss_en = english_gloss(usable_label(entry.get("label_en")), lemma_by_qid[qid])
            concept.gloss_uk = usable_label(entry.get("label_uk"))
            concept.description_en = (entry.get("description_en") or "")[:500] or None
            concept.description_uk = (entry.get("description_uk") or "")[:500] or None
            concepts[qid] = concept
        session.flush()

        item_labels_source = upsert_source(
            session,
            ITEM_LABELS_SOURCE,
            "https://www.wikidata.org/wiki/Help:Label",
            "CC0 1.0",
        )
        session.execute(
            delete(Form).where(Form.source_id.in_([wikidata.id, item_labels_source.id]))
        )
        session.flush()

        # Words from other sources (e.g. our editors) are kept: don't duplicate their spelling
        # and don't add a second primary form next to theirs.
        # Unverified machine words are only placeholders: real data replaces them.
        other_forms: dict[tuple[int, int], list[Form]] = defaultdict(list)
        machine_forms: dict[tuple[int, int], list[Form]] = defaultdict(list)
        for form in session.scalars(select(Form).options(selectinload(Form.source))):
            target = machine_forms if form.source.name == MACHINE_SOURCE_NAME else other_forms
            target[(form.concept_id, form.variety_id)].append(form)

        def drop_machine_words(concept_id: int, variety_id: int) -> None:
            for form in machine_forms.pop((concept_id, variety_id), []):
                session.delete(form)

        form_count = audio_count = 0
        for (qid, lang_qid), by_id in lexemes.items():
            if qid not in concepts:
                continue
            existing = other_forms[(concepts[qid].id, varieties[lang_qid].id)]
            drop_machine_words(concepts[qid].id, varieties[lang_qid].id)
            has_primary = any(f.is_primary for f in existing)
            label = item_labels.get((qid, lang_qid))
            primary = pick_primary(by_id.values(), label, qid)
            seen_spellings = {f.spelling for f in existing}
            if primary is None and label and label not in seen_spellings:
                # The concept's label is the standard word; lexemes become synonyms.
                seen_spellings.add(label)
                session.add(
                    Form(
                        concept=concepts[qid],
                        variety=varieties[lang_qid],
                        spelling=label[:200],
                        is_primary=not has_primary,
                        external_id=qid,
                        source=item_labels_source,
                    )
                )
                form_count += 1
            for lexeme in sorted(by_id.values(), key=lambda lx: lx is not primary):
                if lexeme.lemma in seen_spellings:
                    continue
                seen_spellings.add(lexeme.lemma)
                form = Form(
                    concept=concepts[qid],
                    variety=varieties[lang_qid],
                    spelling=lexeme.lemma[:200],
                    ipa=lexeme.ipas[0][:200] if lexeme.ipas else None,
                    is_primary=lexeme is primary and not has_primary,
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

        # Languages without any lexeme for a concept get the concept's label in that language,
        # when it looks like a single word (less reliable than lexemes, but CC0 and broad).
        label_count = 0
        for qid, concept in concepts.items():
            english_label = labels.get(qid, {}).get("label_en") or concept.gloss_en
            english = english_label.lower()
            for lang in LANGUAGES:
                if (qid, lang.wikidata_id) in lexemes:
                    continue
                label = item_labels.get((qid, lang.wikidata_id))
                variety = varieties[lang.wikidata_id]
                # Editor words and pending drafts take precedence over labels.
                if other_forms[(concept.id, variety.id)]:
                    continue
                if not label_as_word(label, english, lang.iso639_3):
                    continue
                label = label_word(label, english_label, lang.iso639_3)
                drop_machine_words(concept.id, variety.id)
                session.add(
                    Form(
                        concept=concept,
                        variety=variety,
                        spelling=label,
                        is_primary=True,
                        external_id=qid,
                        source=item_labels_source,
                    )
                )
                label_count += 1
        print(f"  {label_count} words taken from concept labels")
        form_count += label_count

        session.flush()
        assign_missing_slugs(session)
        removed, kept = remove_stale_concepts(session, set(qids))
        if removed:
            print(f"  removed {removed} concepts no longer imported")
        for concept in kept:
            print(
                f"  warning: {concept.wikidata_id} ({concept.gloss_en}) is no longer imported "
                "but has words from other sources; kept"
            )
        promoted = ensure_one_primary(session)
        session.commit()

    if promoted:
        print(f"  promoted {promoted} forms to primary")
    print(
        f"Imported {len(concepts)} concepts, {form_count} forms, {audio_count} audio files "
        f"in {len(varieties)} languages."
    )


if __name__ == "__main__":
    main()
