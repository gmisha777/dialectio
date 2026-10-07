"""Load generated words for concepts that have no word in a language.

    uv run python -m app.importers.suggestions [iso639_3]            (default: ukr)
        data/suggestions_<iso>.json -> drafts (status "pending") reviewed in the editor
    uv run python -m app.importers.suggestions --machine <iso> [...]
        data/machine/<iso>.json -> public right away, marked unverified ("≈" on the site)

Files map Wikidata items to words: {"<Wikidata item>": "<word>"}. Concepts that already
have any word in that language are skipped, so real data always wins.
"""

import json
import sys

from sqlalchemy import select

from app.api.editor import EDITOR_SOURCE_LICENSE, EDITOR_SOURCE_URL, SUGGESTION_SOURCE_NAME
from app.api.lexicon import MACHINE_SOURCE_NAME
from app.db.session import SessionLocal
from app.importers.common import upsert_source
from app.importers.wikidata_lexemes import DATA_DIR
from app.models import APPROVED, PENDING, Concept, Form, Variety


def main(*args: str) -> None:
    if args and args[0] == "--machine":
        for iso639_3 in args[1:]:
            load(iso639_3, machine=True)
    else:
        load(args[0] if args else "ukr", machine=False)


def load(iso639_3: str, machine: bool) -> None:
    path = (
        DATA_DIR / "machine" / f"{iso639_3}.json"
        if machine
        else DATA_DIR / f"suggestions_{iso639_3}.json"
    )
    suggestions: dict[str, str] = json.loads(path.read_text(encoding="utf-8"))
    suggestions.pop("_comment", None)

    with SessionLocal() as session:
        variety = session.scalar(select(Variety).where(Variety.iso639_3 == iso639_3))
        if variety is None:
            raise SystemExit(f"Unknown language {iso639_3}")
        source = upsert_source(
            session,
            MACHINE_SOURCE_NAME if machine else SUGGESTION_SOURCE_NAME,
            EDITOR_SOURCE_URL,
            EDITOR_SOURCE_LICENSE,
        )
        concepts = {
            c.wikidata_id: c
            for c in session.scalars(
                select(Concept).where(Concept.wikidata_id.in_(list(suggestions)))
            )
        }
        has_word = set(
            session.scalars(select(Form.concept_id).where(Form.variety_id == variety.id))
        )

        added = skipped = 0
        for qid, word in suggestions.items():
            concept = concepts.get(qid)
            if concept is None:
                print(f"  unknown concept {qid} ({word}), skipped")
                continue
            if concept.id in has_word:
                skipped += 1
                continue
            session.add(
                Form(
                    concept=concept,
                    variety=variety,
                    spelling=word.strip(),
                    is_primary=machine,
                    status=APPROVED if machine else PENDING,
                    source=source,
                )
            )
            added += 1
        session.commit()

    kind = "unverified machine words" if machine else "draft words for review"
    print(f"{iso639_3}: added {added} {kind}, skipped {skipped} concepts that have a word.")


if __name__ == "__main__":
    main(*sys.argv[1:])
