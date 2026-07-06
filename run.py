"""
CureMenu — Tek giriş noktası
FastAPI sunucusunu başlatır (web arayüzü + API).
"""
import os
import uvicorn

if __name__ == "__main__":
    debug = os.getenv("DEBUG", "true").lower() == "true"
    uvicorn.run(
        "api:app",
        host="127.0.0.1" if debug else "0.0.0.0",
        port=int(os.getenv("PORT", "8000")),
        reload=debug,
        reload_excludes=["*.db", "*.sqlite3", "*.db-wal", "*.db-shm", ".venv", "venv", "__pycache__"]
    )
