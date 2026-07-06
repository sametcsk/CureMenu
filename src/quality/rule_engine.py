from typing import List, Dict, Any

class RuleEngine:
    """Tıbbi (Klinik) kısıtlamaları (Hard-Rule) kontrol eden motor."""
    
    def check_rules(self, profile: Dict[str, Any], meal: str, ingredients: List[str]) -> Dict[str, Any]:
        found_risks = []
        risk_score = 0.0 # 0 (Low), 1 (High)
        
        # Basit hard-coded kural motoru örneği (Daha sonra detaylandırılacak)
        allergies = profile.get("alerjiler", [])
        for allergy in allergies:
            if allergy.lower() in meal.lower() or any(allergy.lower() in ing.lower() for ing in ingredients):
                found_risks.append(f"Alerji riski (Kesin İhlal): {allergy}")
                risk_score = 1.0
                
        diseases = profile.get("hastaliklar", [])
        if "Gut" in diseases and ("Et" in meal or "Sakatat" in meal):
            found_risks.append("Gut hastalığında yüksek pürin (Kırmızı Et/Sakatat) riski.")
            risk_score = 0.8
            
        return {
            "found_risks": found_risks,
            "medical_risk_score": risk_score
        }

