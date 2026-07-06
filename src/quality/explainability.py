from typing import Dict, Any

class ExplainabilityLogger:
    """Tıbbi Kararların 'Neden?' verildiğini izleyen log mekanizması."""
    
    def log_decision(
        self,
        decision_id: str,
        user_id: str,
        final_score: float,
        rules_applied: list,
        policies_applied: list,
        citations: list,
        medical_guideline: str = "TBD"
    ) -> Dict[str, Any]:
        
        log_entry = {
            "decision_id": decision_id,
            "user_id": user_id,
            "confidence_score": final_score,
            "explainability": {
                "applied_rules": rules_applied,
                "applied_policies": policies_applied,
                "medical_guideline_version": medical_guideline,
                "citations_used": citations
            }
        }
        
        # The log_entry is captured as a Governance Event and saved to decision_events.
        return log_entry
