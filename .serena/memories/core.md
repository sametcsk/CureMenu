# CureMenu core
- Safety-sensitive nutrition decision-support prototype; never frame outputs as diagnosis, treatment, or clinically validated advice.
- Backend entrypoint: `api.py`; local launcher: `run.py`.
- FastAPI routers: auth, profile, chat, tools, grocery, governance under `src/routers/`.
- LangGraph orchestration: `src/graph.py`; state and agent behavior: `src/agent_state.py`, `src/nodes.py`.
- Layer boundaries documented in `docs/ARCHITECTURE.md`: governance records decisions; quality evaluates output; medical_knowledge handles limited known-rule checks; rules enforce application policy; grocery builds shopping outputs; privacy redacts data.
- Relational persistence is SQLite with Alembic migrations; semantic memory/RAG is Chroma.
- Clinical evidence registry and RAG source policy live under `data/`; evidence integrity is not clinical validation.
- Read `mem:tech_stack` for runtime/dependencies, `mem:conventions` for invariants, and `mem:task_completion` before declaring work complete.