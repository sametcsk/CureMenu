
from langgraph.graph import StateGraph, START, END
from src.agent_state import AgentState
from src.nodes import (
    supervisor_node, beslenme_uzmani, denetleyici_node, 
    mutfak_sefi_node, onceliklendirme_node, adime_raporlayici_node
)
from src.logger import get_logger

logger = get_logger(__name__)

MAX_DENEME = 3  # Guardrail'in sonsuz döngüye girmemesi için koyduğumuz fren

workflow = StateGraph(AgentState)

workflow.add_node("supervisor", supervisor_node)
workflow.add_node("triyaj", onceliklendirme_node)
workflow.add_node("doktor", beslenme_uzmani)
workflow.add_node("denetmen", denetleyici_node)
workflow.add_node("sef", mutfak_sefi_node)
workflow.add_node("raporlayici", adime_raporlayici_node)

workflow.add_edge(START, "supervisor")

def supervisor_kontrol(state: AgentState) -> str:
    """Supervisor Agent'in kararına göre bir sonraki adımı belirler."""
    return state.get("next_node", "FINISH")

workflow.add_conditional_edges(
    "supervisor",
    supervisor_kontrol,
    {
        "DIETITIAN": "triyaj",
        "CHEF": "denetmen",
        "FINISH": "denetmen",
    }
)

# Triyaj ajanından çıkan sonuç her zaman Diyetisyene (Seçenek Sunma) gider.
workflow.add_edge("triyaj", "doktor")
workflow.add_edge("doktor", "denetmen")

def kural_kontrolu(state: AgentState) -> str:
    """
    Guardrail karar noktamız.
    Eğer yemek güvenliyse → Mutfak şefine gönderiyoruz.
    Eğer güvenli değilse VE deneme limiti aşılmadıysa → Yeni yemek için Beslenme uzmanına geri gönderiyoruz.
    Eğer güvenli değilse VE limit aşıldıysa → Maliyet/Zaman döngüsünü kırmak için direkt bitiriyoruz.
    """
    if state["guvenli_mi"]:
        if state.get("hedef_islem") in {"SOHBET", "SECENEK_SUN", "SECENEK_SUN_BITTI"}:
            return "bitir"
        return "onaylandi"
    
    deneme = state.get("deneme_sayisi", 0)
    if deneme >= MAX_DENEME:
        logger.warning("GUARDRAIL FREN: %s deneme aşıldı, döngü kırılıyor.", MAX_DENEME)
        return "limit_asildi"
    
    return "reddedildi"


# Backward-compatible Turkish identifier used by older tests/docs.
kural_kontrolü = kural_kontrolu

workflow.add_conditional_edges(
    "denetmen",
    kural_kontrolu,
    {
        "onaylandi": "sef",
        "bitir": END,
        "reddedildi": "doktor", # Eğer onaylanmazsa doktordan yeni tarif istiyoruz
        "limit_asildi": END,
    }
)

workflow.add_edge("sef", "raporlayici")
workflow.add_edge("raporlayici", END)

app = workflow.compile()
