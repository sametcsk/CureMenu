"""Central component version registry for reproducible clinical decisions."""

from copy import deepcopy

from src.config import settings


COMPONENT_VERSIONS = {
    "clinical_decision_graph": "v1",
    "supervisor_prompt": "supervisor_agent:v1",
    "triage_prompt": "triage_agent:v1",
    "dietitian_prompt": "dietitian_agent:v1",
    "auditor_prompt": "auditor_agent:v1",
    "rule_engine": "v1",
    "policy_engine": "v1",
    "medication_safety": "hybrid_rules_rag:v1",
    "medication_food_rules": "medication_food_rules:v1",
    "medical_knowledge_normalizer": "bioportal_local_fallback:v1",
    "high_risk_medications": "high_risk_medications:v1",
    "confidence_calculator": "v1",
    "citation_validator": "mock:v1",
    "model": settings.text_model_name,
    "text_model": settings.text_model_name,
    "vision_model": settings.GEMINI_VISION_MODEL,
    "fast_model": settings.GEMINI_FAST_MODEL,
    "eval_model": settings.GEMINI_EVAL_MODEL,
    "embedding_model": "sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2",
    "vector_db": "chroma:clinical_library",
    "guideline": "project_internal:v1",
    "evaluation_dataset": "golden_v1+adversarial_v1",
}


def get_component_versions() -> dict[str, str]:
    """Return a copy so callers cannot mutate the process-wide registry."""
    return deepcopy(COMPONENT_VERSIONS)
