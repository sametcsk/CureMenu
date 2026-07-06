from typing import TypedDict, List, Optional, Dict, Any

from src.governance.events import make_event, new_decision_id, utc_now_iso
from src.governance.version_registry import get_component_versions

class AgentState(TypedDict):

    profil_ozeti: str
    istek: str 
    hafiza: List[str]
    uzman_onerisi: Optional[str]
    guvenli_mi: bool
    uyari_mesaji: str
    tarif_metni: Optional[str]
    sohbet_gecmisi: List[Dict[str, Any]]
    hedef_islem: str
    deneme_sayisi: int
    ilaclar: List[str]
    klinik_oncelik: str
    adime_raporu: str
    next_node: str
    decision_id: str
    created_at: str
    component_versions: Dict[str, str]
    governance_events: List[Dict[str, Any]]
    risk_score: Optional[float]
    confidence: Dict[str, Any]
    citations: List[Dict[str, Any]]

initial_state = AgentState(
    profil_ozeti="",
    istek="",
    hafiza=[],
    uzman_onerisi=None,
    guvenli_mi=True,
    uyari_mesaji="",
    tarif_metni=None,
    hedef_islem="SOHBET",
    deneme_sayisi=0,
    sohbet_gecmisi=[],
    ilaclar=[],
    klinik_oncelik="",
    adime_raporu="",
    next_node="supervisor",
    decision_id="",
    created_at="",
    component_versions={},
    governance_events=[],
    risk_score=None,
    confidence={},
    citations=[],
)

def create_initial_state(
    profil_ozeti: str,
    istek: str,
    hafiza: List[str],
    sohbet_gecmisi: List[Dict[str, Any]] = None,
    ilaclar: List[str] | None = None,
) -> AgentState:
    """Grafik ilk çalıştırıldığında başlangıç durumunu oluşturur."""
    if sohbet_gecmisi is None:
        sohbet_gecmisi = []
    decision_id = new_decision_id()
    created_at = utc_now_iso()
    return AgentState(
        profil_ozeti=profil_ozeti,
        istek=istek,
        hafiza=hafiza,
        uzman_onerisi=None,
        guvenli_mi=True,
        uyari_mesaji="",
        tarif_metni=None,
        sohbet_gecmisi=sohbet_gecmisi,
        hedef_islem="SOHBET",
        deneme_sayisi=0,
        ilaclar=ilaclar or [],
        klinik_oncelik="",
        adime_raporu="",
        next_node="supervisor",
        decision_id=decision_id,
        created_at=created_at,
        component_versions=get_component_versions(),
        governance_events=[
            make_event(
                "ConversationStarted",
                "api.chat",
                metadata={"request_length": len(istek or "")},
            ),
            make_event(
                "PatientProfileLoaded",
                "profile_context",
                metadata={
                    "profile_chars": len(profil_ozeti or ""),
                    "memory_items": len(hafiza or []),
                    "medications_count": len(ilaclar or []),
                },
            ),
        ],
        risk_score=None,
        confidence={},
        citations=[],
    )

    
