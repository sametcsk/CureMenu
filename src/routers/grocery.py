import sqlite3

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException

from src.auth import get_current_user
from src.database import get_db, klinik_karar_kaydet, profil_getir_db
from src.governance.decision import build_decision_record
from src.grocery.capability import build_smart_grocery
from src.grocery.profile import grocery_profile_facts
from src.grocery.schemas import SmartGroceryRequest, SmartGroceryResponse
from src.messages import PROFIL_BULUNAMADI, PROFIL_GEREKLI


router = APIRouter()


@router.post("/api/smart-grocery", response_model=SmartGroceryResponse)
async def smart_grocery(
    req: SmartGroceryRequest,
    bg_tasks: BackgroundTasks,
    telefon: str = Depends(get_current_user),
    db: sqlite3.Connection = Depends(get_db),
):
    if not req.weekly_plan and not req.shopping_items:
        raise HTTPException(status_code=400, detail="weekly_plan veya shopping_items gerekli")

    profil = profil_getir_db(telefon, conn=db)
    if profil is None:
        raise HTTPException(status_code=404, detail=PROFIL_BULUNAMADI)
    try:
        profile_facts = grocery_profile_facts(profil, req.kimin_icin)
    except ValueError:
        raise HTTPException(status_code=400, detail=PROFIL_GEREKLI) from None

    shopping_items = [item.model_dump(exclude_none=True) for item in req.shopping_items or []]
    basket, state = build_smart_grocery(
        weekly_plan=req.weekly_plan,
        shopping_items=shopping_items,
        profile_facts=profile_facts,
        location_context=req.location_context,
    )
    final_answer = basket["recommendation_summary"]
    decision_record = build_decision_record(
        state,
        telefon=telefon,
        kimin_icin=req.kimin_icin,
        final_answer=final_answer,
    )
    bg_tasks.add_task(klinik_karar_kaydet, decision_record)

    return {
        "success": True,
        "decision_id": decision_record["decision_id"],
        **basket,
    }
