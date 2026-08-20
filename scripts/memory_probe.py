"""Local process-RSS probe for the Railway memory root-cause analysis.

Diagnostic only — does NOT change production behavior. Measures resident memory at
each load stage (baseline vs lazy-loaded globals vs image pipeline) so a real leak
can be told apart from Python high-water RSS / allocator behavior.

Run: python -m scripts.memory_probe
"""
from __future__ import annotations

import base64
import gc
import io
import os

import psutil

_PROC = psutil.Process(os.getpid())


def rss_mb() -> float:
    return round(_PROC.memory_info().rss / (1024 * 1024), 1)


def stage(label: str, before: float) -> float:
    now = rss_mb()
    print(f"  {label:42} rss={now:8} MB  (delta {round(now - before, 1):+} MB)")
    return now


def main() -> int:
    print(f"process count (this probe): 1   pid={os.getpid()}")
    base = rss_mb()
    print(f"  {'interpreter + psutil':42} rss={base:8} MB  (baseline)")

    try:
        import api  # noqa: F401  (loads settings + all routers)
        base = stage("after import api (app+routers)", base)
    except Exception as exc:
        print(f"  import api failed: {exc}")

    try:
        from src.graph import app as _graph  # noqa: F401
        base = stage("after import src.graph (LangGraph)", base)
    except Exception as exc:
        print(f"  import graph failed: {exc}")

    try:
        import src.memory as memory  # noqa: F401
        base = stage("after import src.memory", base)
        try:
            memory.klinik_bilgi_getir("beslenme guvenligi", k_adet=1)
            base = stage("after 1 clinical RAG query (chroma+embeddings)", base)
        except Exception as exc:
            print(f"  RAG query skipped: {exc}")
    except Exception as exc:
        print(f"  import memory failed: {exc}")

    # Image pipeline: how many copies of one image coexist?
    try:
        from PIL import Image
        before_img = rss_mb()
        img = Image.new("RGB", (2000, 1500), (120, 90, 60))
        buf = io.BytesIO()
        img.save(buf, format="JPEG", quality=85)
        raw = buf.getvalue()                       # encoded bytes
        b64 = base64.b64encode(raw).decode()       # base64 string
        decoded = base64.b64decode(b64)            # decoded bytes (copy of raw)
        reopened = Image.open(io.BytesIO(decoded)); reopened.load()  # PIL bitmap
        preview = reopened.copy(); preview.thumbnail((512, 512))     # preview bitmap
        prev_buf = io.BytesIO(); preview.save(prev_buf, format="JPEG", quality=80)
        preview_b64 = base64.b64encode(prev_buf.getvalue()).decode()
        print("  --- image pipeline live copies ---")
        print(f"    raw_bytes={len(raw)}  base64={len(b64)}  decoded={len(decoded)}  "
              f"pil_bitmap~{2000*1500*3}  preview_b64={len(preview_b64)}")
        stage("peak during image pipeline", before_img)
        del img, buf, raw, b64, decoded, reopened, preview, prev_buf, preview_b64
        gc.collect()
        stage("after releasing image refs + gc", before_img)
    except Exception as exc:
        print(f"  image pipeline skipped: {exc}")

    print(f"\n  FINAL rss={rss_mb()} MB")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
