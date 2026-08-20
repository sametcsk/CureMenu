import hashlib
import json
import sqlite3

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException

from src.auth import get_current_user
from src.database import artifact_getir, artifact_kaydet, etkilesim_logla, get_db, klinik_karar_kaydet
from src.logger import get_logger, log_failure
from src.governance.decision import build_decision_record
from src.grocery.capability import build_smart_grocery
from src.grocery.profile import grocery_profile_facts
from src.llm_telemetry import set_llm_context
from src.profile_context import resolve_profile_snapshot
from src.grocery.schemas import SmartGroceryRequest, SmartGroceryResponse


router = APIRouter()
logger = get_logger(__name__)


def _plan_ref(weekly_plan: str) -> str:
    """Stable fingerprint of the weekly plan a shopping list was built from, so a
    saved list is not shown against a different plan."""
    return hashlib.sha256((weekly_plan or "").encode("utf-8")).hexdigest()[:16]


@router.post("/api/smart-grocery", response_model=SmartGroceryResponse)
async def smart_grocery(
    req: SmartGroceryRequest,
    bg_tasks: BackgroundTasks,
    telefon: str = Depends(get_current_user),
    db: sqlite3.Connection = Depends(get_db),
):
    set_llm_context(feature="shopping_list", account_id=telefon)
    if not req.weekly_plan and not req.shopping_items:
        raise HTTPException(status_code=400, detail="weekly_plan veya shopping_items gerekli")

    snapshot = resolve_profile_snapshot(telefon, req.kimin_icin, db=db)
    profile_facts = grocery_profile_facts(snapshot)

    shopping_items = [item.model_dump(exclude_none=True) for item in req.shopping_items or []]
    basket, state = build_smart_grocery(
        weekly_plan=req.weekly_plan,
        shopping_items=shopping_items,
        profile_facts=profile_facts,
        resolved_profile_snapshot=snapshot.state_payload(),
        location_context=req.location_context,
    )
    final_answer = basket["recommendation_summary"]
    decision_record = build_decision_record(
        state,
        telefon=telefon,
        kimin_icin=snapshot.target_key,
        final_answer=final_answer,
    )
    bg_tasks.add_task(klinik_karar_kaydet, decision_record)
    bg_tasks.add_task(
        etkilesim_logla,
        telefon,
        snapshot.target_name,
        "Smart Grocery",
        "Sepet değerlendirmesi",
        final_answer,
        json.dumps(snapshot.history_metadata(), ensure_ascii=False),
    )

    result = {
        "success": True,
        "decision_id": decision_record["decision_id"],
        **basket,
    }
    # Persist as backend source-of-truth (account + resolved target). The frontend
    # keeps only a display cache; this survives F5 / route change / re-open.
    try:
        artifact_kaydet(
            telefon, snapshot.target_key, "shopping_list",
            json.dumps({**basket, "decision_id": decision_record["decision_id"],
                        "target_scope": snapshot.target_scope}, ensure_ascii=False),
            ref_id=_plan_ref(req.weekly_plan or ""),
            conn=db,
        )
    except Exception as exc:
        log_failure(logger, "shopping_list_persist", exc, component="grocery")
    return result


@router.get("/api/smart-grocery/saved")
async def smart_grocery_saved(
    kimin_icin: str = "kendim",
    plan_ref: str = "",
    telefon: str = Depends(get_current_user),
    db: sqlite3.Connection = Depends(get_db),
):
    """Restore the persisted shopping list for the resolved target (source-of-truth).

    When the caller passes the current plan's `plan_ref`, a saved list built from a
    different plan is reported as stale instead of shown, mirroring the client's
    existing freshness check."""
    snapshot = resolve_profile_snapshot(telefon, kimin_icin, db=db)
    saved = artifact_getir(telefon, snapshot.target_key, "shopping_list", conn=db)
    if not saved:
        return {"success": True, "saved": None}
    if plan_ref and saved.get("ref_id") and saved["ref_id"] != plan_ref:
        return {"success": True, "saved": None, "stale": True}
    try:
        payload = json.loads(saved["data_json"])
    except (TypeError, ValueError):
        payload = None
    return {"success": True, "saved": payload, "updated_at": saved["updated_at"], "plan_ref": saved.get("ref_id")}
