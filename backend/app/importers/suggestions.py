"""Load draft words for review in the editor (status "pending", not public until approved).

Run from backend/:  uv run python -m app.importers.suggestions [iso639_3]   (default: ukr)
Reads app/importers/data/suggestions_<iso639_3>.json: {"<Wikidata item>": "<word>"}.
Concepts that already have an approved or pending word in that language are skipped.
"""

import json
import sys

from sqlalchemy import select

from app.api.editor import EDITOR_SOURCE_LICENSE, EDITOR_SOURCE_URL, SUGGESTION_SOURCE_NAME
from app.db.session import SessionLocal
from app.importers.common import upsert_source
from app.importers.wikidata_lexemes import DATA_DIR
from app.models import PENDING, Concept, Form, Variety


def main(iso639_3: str = "ukr") -> None:
    suggestions: dict[str, str] = json.loads(
        (DATA_DIR / f"suggestions_{iso639_3}.json").read_text(encoding="utf-8")
    )
    suggestions.pop("_comment", None)

    with SessionLocal() as session:
        variety = session.scalar(select(Variety).where(Variety.iso639_3 == iso639_3))
        if variety is None:
            raise SystemExit(f"Unknown language {iso639_3}")
        source = upsert_source(
            session, SUGGESTION_SOURCE_NAME, EDITOR_SOURCE_URL, EDITOR_SOURCE_LICENSE
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
                    is_primary=False,
                    status=PENDING,
                    source=source,
                )
            )
            added += 1
        session.commit()

    print(f"Added {added} draft words for review, skipped {skipped} concepts that have one.")


if __name__ == "__main__":
    main(*sys.argv[1:])
