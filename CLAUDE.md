# Dialectio

Web app: enter a word → see on a map how it is written, pronounced (IPA) and sounds in different languages and dialects.
Full plan and decisions: [docs/plan.md](docs/plan.md). Communicate with the user in Ukrainian.

## Layout
- `backend/` — FastAPI (Python 3.11+, managed with uv), SQLAlchemy + Alembic, PostgreSQL/PostGIS
- `frontend/` — Next.js (TypeScript) + MapLibre GL, i18n (uk, en)
- `backend/app/importers/` — import scripts for open data (run as `uv run python -m app.importers.<name>`); downloads go to git-ignored `data/raw/`
- `docs/` — plan and design notes

## Conventions
- Data is organized around `Concept` (meaning), not raw word strings.
- Every imported record must keep its `Source` (name, url, license).
- Synthetic (TTS) audio must be flagged `is_synthetic`.
- Forms have `status`: only `approved` ones are public (search, word pages, map). `pending` drafts (source "Dialectio suggestions (draft)", loaded by `app.importers.suggestions`) wait for review in the editor. Every public query must filter on `status = 'approved'`.
- Concept slugs (`/[locale]/word/[slug]`) are permanent once assigned (`app/slugs.py`); never recompute them, URLs are indexed by search engines.
- Use only free/open data sources and libraries; no Google Maps.
- UI strings live in `frontend/messages/{uk,en}.json` (next-intl); routes are prefixed with the locale (`/uk`, `/en`), default `uk`. Never hardcode UI text in components.
- Do not `git push` without discussing with the user first.

## Commands
- Start DB: `docker compose up -d db`
- Backend (from `backend/`): `uv sync`, `uv run uvicorn app.main:app --reload`, `uv run pytest`, `uv run ruff check .`
- Import countries (from `backend/`): `uv run python -m app.importers.natural_earth`; restart the API afterwards (country vector tiles are cached in memory)
- Word editor: `/uk/editor`, token = `EDITOR_TOKEN` in `.env`; editor words use source "Dialectio editors" and survive Wikidata re-imports
- Import words (from `backend/`, after countries): `uv run python -m app.importers.wikidata_lexemes` (~10 min, re-runnable); word lists and exclusions live in `backend/app/importers/data/`
- Migrations (from `backend/`): `uv run alembic revision --autogenerate -m "..."`, `uv run alembic upgrade head`
- Frontend (from `frontend/`): `npm install`, `npm run dev`, `npm run lint`, `npm run build`
- `uvicorn --reload` on Windows sometimes misses file changes: if the API serves old code, restart it
- Next.js 16 has breaking changes vs older versions: check `frontend/node_modules/next/dist/docs/` before writing frontend code.
