# Dialectio

Web app: enter a word → see on a map how it is written, pronounced (IPA) and sounds in different languages and dialects.
Full plan and decisions: [docs/plan.md](docs/plan.md). Communicate with the user in Ukrainian.

## Layout
- `backend/` — FastAPI (Python 3.11+, managed with uv), SQLAlchemy + Alembic, PostgreSQL/PostGIS
- `frontend/` — Next.js (TypeScript) + MapLibre GL, i18n (uk, en)
- `data/scripts/` — import scripts for open data (Wiktionary, Wikidata, geoBoundaries)
- `docs/` — plan and design notes

## Conventions
- Data is organized around `Concept` (meaning), not raw word strings.
- Every imported record must keep its `Source` (name, url, license).
- Synthetic (TTS) audio must be flagged `is_synthetic`.
- Use only free/open data sources and libraries; no Google Maps.
- UI strings live in `frontend/messages/{uk,en}.json` (next-intl); routes are prefixed with the locale (`/uk`, `/en`), default `uk`. Never hardcode UI text in components.
- Do not `git push` without discussing with the user first.

## Commands
- Start DB: `docker compose up -d db`
- Backend (from `backend/`): `uv sync`, `uv run uvicorn app.main:app --reload`, `uv run pytest`, `uv run ruff check .`
- Migrations (from `backend/`): `uv run alembic revision --autogenerate -m "..."`, `uv run alembic upgrade head`
- Frontend (from `frontend/`): `npm install`, `npm run dev`, `npm run lint`, `npm run build`
- Next.js 16 has breaking changes vs older versions: check `frontend/node_modules/next/dist/docs/` before writing frontend code.
