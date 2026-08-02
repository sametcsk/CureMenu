# Tech stack
- Python >=3.11,<3.14; README targets 3.11/3.12.
- FastAPI/Starlette/Uvicorn API; Pydantic v2 settings/models.
- LangGraph + LangChain Google Gemini; Tavily optional external search.
- ChromaDB 1.5.9 with HuggingFace embeddings for local RAG/memory.
- SQLite + SQLAlchemy 2.0.51 + Alembic.
- NeMo Guardrails 0.23.0 plus deterministic safety/policy layers.
- Vanilla JavaScript/HTML/CSS frontend in `frontend/`; browser E2E via Playwright 1.61.0.
- Pytest test runner. No configured formatter, linter, or static type checker in `pyproject.toml`.
- Dependencies are requirements-file based; no lockfile/constraints policy is currently authoritative.