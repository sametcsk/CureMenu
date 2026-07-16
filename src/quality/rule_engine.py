import re
from typing import List, Dict, Any


def _contains_allergen_risk(text: str, allergy: str) -> bool:
    """Ignore explicit absence/allergy-context mentions, not real ingredient use."""
    value = (text or "").casefold()
    needle = (allergy or "").strip().casefold()
    if not needle:
        return False

    safe_suffix = re.compile(
        r"^\s*(?:i[cç]ermez|i[cç]ermeyen|bulunmaz|yok(?:tur)?|"
        r"kullanılmadan|kullanilmadan|yerine|alerji)",
        re.IGNORECASE,
    )
    mention_pattern = re.compile(
        rf"(?<![a-zçğıöşü0-9]){re.escape(needle)}(?:l[ıiuü])?(?![a-zçğıöşü0-9])",
        re.IGNORECASE,
    )
    for match in mention_pattern.finditer(value):
        after = value[match.end():match.end() + 50]
        if not safe_suffix.search(after):
            return True
    return False

class RuleEngine:
    """Tıbbi (Klinik) kısıtlamaları (Hard-Rule) kontrol eden motor."""
    
    def check_rules(self, profile: Dict[str, Any], meal: str, ingredients: List[str]) -> Dict[str, Any]:
        found_risks = []
        risk_score = 0.0 # 0 (Low), 1 (High)
        
        # Basit hard-coded kural motoru örneği (Daha sonra detaylandırılacak)
        allergies = profile.get("alerjiler", [])
        for allergy in allergies:
            if _contains_allergen_risk(meal, allergy) or any(
                _contains_allergen_risk(ingredient, allergy) for ingredient in ingredients
            ):
                found_risks.append(f"Alerji riski (Kesin İhlal): {allergy}")
                risk_score = 1.0
                
        diseases = {str(disease).casefold() for disease in profile.get("hastaliklar", [])}
        meal_text = (meal or "").casefold()
        has_gout = any("gut" in disease or "gout" in disease for disease in diseases)
        has_high_purine_meat = any(
            term in meal_text
            for term in ("sakatat", "ciğer", "ciger", "böbrek", "bobrek", "işkembe", "iskembe")
        )
        if has_gout and has_high_purine_meat:
            found_risks.append("Gut hastalığında yüksek pürinli sakatat riski.")
            risk_score = 0.8
            
        return {
            "found_risks": found_risks,
            "medical_risk_score": risk_score
        }
