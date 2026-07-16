import unicodedata
from typing import Dict, Any


def _normalize(value: str) -> str:
    folded = unicodedata.normalize("NFKD", str(value or "").casefold())
    return "".join(char for char in folded if not unicodedata.combining(char))

class PolicyEngine:
    """Ürün ve Şirket Politikalarını kontrol eden motor."""
    
    def check_policy(self, profile: Dict[str, Any], action: str) -> Dict[str, Any]:
        applied_policies = []
        is_allowed = True
        requires_review = False
        
        age = int(profile.get("yas", 30) or 30)
        if age < 18:
            applied_policies.append("18 yaş altı bireyler için kişiselleştirilmiş öneri sağlık profesyoneli tarafından değerlendirilmelidir.")
            requires_review = True

        context = _normalize(" ".join([
            str(profile.get("cinsiyet", "")),
            str(profile.get("hedef", "")),
            " ".join(profile.get("hastaliklar") or []),
        ]))
        if any(term in context for term in ("hamile", "gebelik", "emzir")):
            applied_policies.append("Gebelik veya emzirme dönemindeki öneri sağlık profesyoneli tarafından değerlendirilmelidir.")
            requires_review = True
        if any(term in context for term in ("bobrek", "renal", "diyaliz", "dialysis")):
            applied_policies.append("Böbrek hastalığında öneri; evre, ilaçlar ve güncel tahlillerle birlikte uzman tarafından değerlendirilmelidir.")
            requires_review = True
            
        return {
            "applied_policies": applied_policies,
            "is_allowed": is_allowed,
            "requires_review": requires_review
        }
