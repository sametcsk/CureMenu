import yaml
from pathlib import Path
from typing import Dict

CONFIG_PATH = Path(__file__).parent / "config.yaml"

class ConfidenceCalculator:
    def __init__(self):
        with open(CONFIG_PATH, "r", encoding="utf-8") as f:
            config = yaml.safe_load(f)
            self.weights = config.get("confidence_weights", {})
            self.thresholds = config.get("thresholds", {})
            
    def calculate_final_score(
        self,
        model_confidence: float,
        evidence_strength: float,
        medical_risk: float,
        citation_quality: float
    ) -> Dict[str, float]:
        """
        Deterministik olarak bileşik (composite) güven skoru üretir.
        medical_risk 0 (Düşük) ile 1 (Yüksek) arasındadır.
        Diğerleri 0 (Kötü) ile 1 (İyi) arasındadır.
        """
        # Risk 1 (Yüksek) ise güveni düşürmeli, o yüzden (1 - medical_risk) alıyoruz.
        safe_risk = 1.0 - medical_risk
        
        score = (
            (model_confidence * self.weights.get("model_confidence", 0.2)) +
            (evidence_strength * self.weights.get("evidence_strength", 0.35)) +
            (safe_risk * self.weights.get("medical_risk", 0.3)) +
            (citation_quality * self.weights.get("citation_quality", 0.15))
        )
        
        # Sınırlandırma (0.0 - 1.0 arası)
        score = max(0.0, min(1.0, score))
        return {
            "final_score": round(score, 4),
            "model_confidence": model_confidence,
            "evidence_strength": evidence_strength,
            "medical_risk": medical_risk,
            "citation_quality": citation_quality
        }
        
    def determine_action(self, final_score: float) -> str:
        """Sistemin son kararı ne olmalı?"""
        if final_score < self.thresholds.get("reject_below", 0.40):
            return "REJECT"
        elif final_score < self.thresholds.get("human_review_below", 0.70):
            return "REVIEW_REQUIRED"
        return "APPROVE"
