from typing import List, Dict, Any

class PolicyEngine:
    """Ürün ve Şirket Politikalarını kontrol eden motor."""
    
    def check_policy(self, profile: Dict[str, Any], action: str) -> Dict[str, Any]:
        applied_policies = []
        is_allowed = True
        requires_review = False
        
        age = profile.get("yas", 30)
        if age < 18:
            applied_policies.append("Çocuk kullanıcılara doğrudan ilaç/katı diyet önerilemez.")
            requires_review = True
            
        if profile.get("cinsiyet") == "kadın" and "Hamilelik" in profile.get("hedef", ""):
            applied_policies.append("Gebelik durumunda doktor onaylı diyet uyarısı gösterilmeli.")
            requires_review = True
            
        return {
            "applied_policies": applied_policies,
            "is_allowed": is_allowed,
            "requires_review": requires_review
        }
