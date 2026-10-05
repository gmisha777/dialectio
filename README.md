# Dialectio

Interactive map of how words are written, pronounced and sound across languages and dialects.
Type a word — see on the map how it is said in each country or region, with spelling, IPA and audio.

> Status: early development (Stage 0 — project setup).

## Stack

| Layer    | Technology                                   |
|----------|----------------------------------------------|
| Backend  | Python 3.11+, FastAPI, SQLAlchemy, Alembic   |
| Database | PostgreSQL 16 + PostGIS                      |
| Frontend | Next.js (React, TypeScript), MapLibre GL     |
| Maps     | OpenStreetMap tiles, geoBoundaries / GADM    |

## Repository layout

```
backend/   FastAPI application (API, models, DB access)
frontend/  Next.js web application
data/      Import scripts for open data sources (Wiktionary, Wikidata, boundaries)
docs/      Project plan and design notes
```

## Local development

Requirements: Docker Desktop, Python 3.11+, [uv](https://docs.astral.sh/uv/), Node.js 22+.

```bash
cp .env.example .env
docker compose up -d db
```

Backend (http://localhost:8000/docs):

```bash
cd backend
uv sync
uv run alembic upgrade head
uv run uvicorn app.main:app --reload
```

Frontend (http://localhost:3000):

```bash
cd frontend
npm install
npm run dev
```

## Roadmap

See [docs/plan.md](docs/plan.md).

## Data and licenses

Lexical data comes from open sources (Wiktionary, Wikidata Lexemes, public-domain dictionaries)
and community contributions. Each record keeps its source and license.
