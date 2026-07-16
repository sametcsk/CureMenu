"""
CureMenu — FastAPI Backend API
Refactored to use routers for modularity.
"""
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse, JSONResponse
from slowapi.errors import RateLimitExceeded
from slowapi.middleware import SlowAPIMiddleware
from starlette.middleware.trustedhost import TrustedHostMiddleware
from starlette.exceptions import HTTPException as StarletteHTTPException
from dotenv import load_dotenv
from functools import lru_cache

load_dotenv()

from src.config import settings
from src.messages import (
    COK_FAZLA_ISTEK, kullanici_hatasi, POSITIONING_TAGLINE,
    TIBBI_FERAGAT, TIBBI_FERAGAT_KISA, ONBOARDING_ORNEK_SORULAR
)
from src.ilac_etkilesim import YAYGIN_ILACLAR
from src.routers import auth, profile, chat, tools, governance, grocery
from src.logger import get_logger, log_failure
from src.rate_limit import limiter
from src.readiness import collect_readiness

logger = get_logger(__name__)
settings.validate_startup_security()

app = FastAPI(title="CureMenu API", version="1.0.0", debug=settings.DEBUG)

app.state.limiter = limiter
app.add_middleware(SlowAPIMiddleware)

app.add_middleware(TrustedHostMiddleware, allowed_hosts=settings.allowed_hosts_list)


@app.middleware("http")
async def security_headers(request: Request, call_next):
    response = await call_next(request)
    response.headers.setdefault("X-Content-Type-Options", "nosniff")
    response.headers.setdefault("Referrer-Policy", "strict-origin-when-cross-origin")
    response.headers.setdefault("X-Frame-Options", "DENY")
    response.headers.setdefault("Permissions-Policy", "camera=(self), microphone=(), geolocation=()")

    path = request.url.path
    if path.startswith("/api/") or path in {"/", "/dashboard", "/giris", "/kayit", "/guven", "/health", "/live", "/ready"}:
        response.headers.setdefault("Cache-Control", "no-store")

    forwarded_proto = request.headers.get("x-forwarded-proto", "").split(",", 1)[0].strip().lower()
    is_https = request.url.scheme == "https" or (settings.TRUST_PROXY_HEADERS and forwarded_proto == "https")
    if settings.is_production and is_https:
        response.headers.setdefault("Strict-Transport-Security", "max-age=31536000; includeSubDomains")
    return response

@app.exception_handler(RateLimitExceeded)
async def rate_limit_turkce(request: Request, exc: RateLimitExceeded):
    return JSONResponse(status_code=429, content={"detail": COK_FAZLA_ISTEK})

@app.exception_handler(StarletteHTTPException)
async def http_exception_handler(request: Request, exc: StarletteHTTPException):
    return JSONResponse(status_code=exc.status_code, content={"detail": exc.detail})

@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    log_failure(logger, "unhandled_request", exc, component="api")
    hata_mesaji = kullanici_hatasi(exc)
    return JSONResponse(status_code=500, content={"success": False, "detail": hata_mesaji})

_cors_origins = settings.cors_origins_list
_allow_credentials = "*" not in _cors_origins

app.add_middleware(
    CORSMiddleware,
    allow_origins=_cors_origins,
    allow_credentials=_allow_credentials,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.mount("/static", StaticFiles(directory="frontend"), name="static")

@app.get("/")
async def serve_home():
    return FileResponse("frontend/index.html")

@app.get("/giris")
async def serve_giris():
    return FileResponse("frontend/giris.html")

@app.get("/kayit")
async def serve_kayit():
    return FileResponse("frontend/kayit.html")

@app.get("/dashboard")
async def serve_dashboard():
    return FileResponse("frontend/dashboard.html")

@app.get("/guven")
async def serve_guven():
    return FileResponse("frontend/guven.html")

@app.get("/health")
async def health_check():
    return {"status": "ok", "service": "CureMenu API"}

@app.get("/live")
async def live_check():
    return {"status": "ok", "service": "CureMenu API"}

@app.get("/ready")
async def ready_check():
    readiness = collect_readiness()
    status_code = 200 if readiness["ready"] else 503
    return JSONResponse(
        status_code=status_code,
        content={
            "status": "ready" if readiness["ready"] else "not_ready",
            **readiness,
        },
    )

@lru_cache(maxsize=1)
def _get_public_metinler_cached():
    return {
        "tagline": POSITIONING_TAGLINE,
        "tibbi_feragat": TIBBI_FERAGAT,
        "tibbi_feragat_kisa": TIBBI_FERAGAT_KISA,
        "ornek_sorular": ONBOARDING_ORNEK_SORULAR,
        "yaygin_ilaclar": YAYGIN_ILACLAR,
    }

@app.get("/api/public/metinler")
async def public_metinler():
    return _get_public_metinler_cached()

# Routers
app.include_router(auth.router)
app.include_router(profile.router)
app.include_router(chat.router)
app.include_router(tools.router)
app.include_router(governance.router)
app.include_router(grocery.router)
