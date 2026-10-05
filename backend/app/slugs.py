"""URL slugs for concept pages.

Slugs are permanent: once assigned they are never recomputed, so page URLs survive changes
to the concept's label. Only concepts without a slug get one.
"""

from sqlalchemy import text
from sqlalchemy.orm import Session

# Slug = English gloss in lowercase ASCII with dashes ("water"). If that slug is already taken,
# or several new concepts share it (homonyms like "bark"), the Wikidata id is appended
# ("bark-q38681").
ASSIGN_MISSING_SLUGS = text("""
    WITH base AS (
        SELECT id, wikidata_id,
               trim(both '-' from regexp_replace(lower(gloss_en), '[^a-z0-9]+', '-', 'g')) AS slug
        FROM concept
        WHERE slug IS NULL
    ), counted AS (
        SELECT *, count(*) OVER (PARTITION BY slug) AS n FROM base
    )
    UPDATE concept c
    SET slug = CASE
        WHEN counted.slug = '' THEN lower(coalesce(counted.wikidata_id, 'concept-' || c.id))
        WHEN counted.n > 1 OR EXISTS (SELECT 1 FROM concept o WHERE o.slug = counted.slug)
            THEN counted.slug || '-' || lower(coalesce(counted.wikidata_id, c.id::text))
        ELSE counted.slug
    END
    FROM counted
    WHERE c.id = counted.id
""")


def assign_missing_slugs(session: Session) -> int:
    return session.execute(ASSIGN_MISSING_SLUGS).rowcount
