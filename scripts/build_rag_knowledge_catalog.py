"""Build a policy-aware catalog for CureMenu's local RAG research library.

The catalog records what each document may support. It deliberately keeps
clinical background, product research, technical references, and quarantined
files separate from the scoped official evidence registry.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any


PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from scripts.audit_rag_library import audit_pdf  # noqa: E402


DEFAULT_POLICY_PATH = PROJECT_ROOT / "data" / "rag_source_policy.json"
DEFAULT_OFFICIAL_REGISTRY_PATH = PROJECT_ROOT / "data" / "clinical_evidence_registry.json"
DEFAULT_OUTPUT_PATH = PROJECT_ROOT / "data" / "rag_knowledge_catalog.json"


PRODUCT_RESEARCH_USE: dict[str, tuple[str, str]] = {
    "20260623-168580-9qoc3l.pdf": (
        "behavior_change",
        "Sağlık sohbet botlarında davranış değişikliği, değerlendirme ve kullanıcı desteği tasarımı.",
    ),
    "ai_chatbots_health_behavior_change.pdf": (
        "behavior_change",
        "Sohbet botlarında kişiselleştirme, davranış değişikliği teknikleri ve değerlendirme çerçevesi.",
    ),
    "ai_chronic_disease_self_management.pdf": (
        "self_management",
        "Kronik hastalıklarda öz yönetim, süreklilik, insan gözetimi ve uygulama sınırlılıkları.",
    ),
    "applsci-15-09283-v2.pdf": (
        "personalized_nutrition_architecture",
        "Makine öğrenmesi, NLP ve kural tabanlı filtreleri birleştiren modüler beslenme mimarisi.",
    ),
    "ehr_rag_bridging_long_horizon_records.pdf": (
        "longitudinal_rag",
        "Uzun dönem sağlık kayıtlarında zaman ve olay farkındalıklı retrieval tasarımı.",
    ),
    "enhancing_guardrails_safe_healthcare_ai.pdf": (
        "health_ai_guardrails",
        "Sağlık yapay zekâsında halüsinasyon, yanlış bilgi ve alan odaklı guardrail gereksinimleri.",
    ),
    "journal.pdig.0000758.pdf": (
        "explainable_personalized_nutrition",
        "RAG, açıklanabilirlik ve tanımlı beslenme ölçütleriyle kişiselleştirilmiş öneri yaklaşımı.",
    ),
    "nutrients-18-00938-v2.pdf": (
        "precision_nutrition_review",
        "Üretken yapay zekânın hassas beslenmedeki kullanım alanları, doğrulama ve gizlilik açıkları.",
    ),
    "nutriorion_multi_agent_personalized_nutrition.pdf": (
        "multi_agent_nutrition",
        "Çoklu hastalık ve ilaç bağlamında uzman ajanlar, önceliklendirme ve güvenlik kısıtları.",
    ),
    "rag_type_2_diabetes_mellitus_care.pdf": (
        "personalized_rag",
        "Kişisel kayıtlar, kurum bağlamı ve rehberleri birleştiren çok kaynaklı RAG araştırması.",
    ),
    "s44325-025-00101-6.pdf": (
        "behavior_change",
        "Yapay zekâ destekli sağlık davranışı değişikliğinin fırsatları ve kanıt sınırları.",
    ),
}


TECHNICAL_REFERENCE_USE: dict[str, tuple[str, str]] = {
    "eu-ai-act-high-risk-compliance-pharma-medical-devices.pdf": (
        "regulatory_orientation",
        "Risk sınıflandırması, izlenebilirlik ve insan gözetimi için ikincil mevzuat araştırması.",
    ),
    "hl7-fhir-guide-to-esource-epro-interoperability.pdf": (
        "fhir_interoperability",
        "Gelecekteki veri değişimi ve birlikte çalışabilirlik yol haritası için teknik referans.",
    ),
    "icd11factsheet_en.pdf": (
        "icd11_reference",
        "Sağlık durumlarının standart adlandırılması ve kodlama yaklaşımı için genel referans.",
    ),
    "presentation-fhir-and-eu-common-standard-epi-g-rodriguez_en.pdf": (
        "fhir_epi_reference",
        "Elektronik ürün bilgisi ve FHIR tabanlı veri değişimi için resmî sunum referansı.",
    ),
}


QUARANTINE_USE: dict[str, tuple[str, str, str]] = {
    "14.pdf": (
        "ocr_required",
        "İlaç-besin, ilaç-alkol ve bitkisel ürün etkileşimleri hakkında taranmış eğitim yazısı.",
        "Metin katmanı yok; kaynak kimliği ve OCR çıktısı doğrulanmadan indekslenmemeli.",
    ),
    "kepan_2025.pdf": (
        "merged_document",
        "Çok sayıda beslenme ve sağlık belgesini bir araya getiren yerel derleme.",
        "Tek bir eser gibi güvenilir biçimde atıf yapılamıyor; alt belgeler ayrıştırılmalı.",
    ),
}


TITLE_OVERRIDES = {
    "14.pdf": "İlaç-Besin, İlaç-Alkol ve İlaç-Bitkisel Kökenli Ürün Etkileşimleri",
    "20260623-168580-9qoc3l.pdf": "AI Chatbots and Health Behaviour Change Review",
    "ai_chatbots_health_behavior_change.pdf": "AI Chatbots for Health Behavior Change",
    "rag_type_2_diabetes_mellitus_care.pdf": "Personal Multi-Source RAG for Type 2 Diabetes Care",
}


def _load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _classify_source(filename: str) -> tuple[str, str, str, str]:
    if filename in PRODUCT_RESEARCH_USE:
        theme, product_use = PRODUCT_RESEARCH_USE[filename]
        return "product_research", theme, product_use, "research_only"
    if filename in TECHNICAL_REFERENCE_USE:
        theme, product_use = TECHNICAL_REFERENCE_USE[filename]
        return "technical_reference", theme, product_use, "reference_only"
    if filename in QUARANTINE_USE:
        reason, product_use, _ = QUARANTINE_USE[filename]
        return "quarantine", reason, product_use, "not_indexed"
    return (
        "clinical_background",
        "nutrition_background",
        "Literatür araştırması ve arka plan açıklaması; hasta düzeyinde kesin klinik iddia için kullanılamaz.",
        "indexed_background_only",
    )


def build_catalog(source_dir: Path) -> dict[str, Any]:
    policy = _load_json(DEFAULT_POLICY_PATH)
    official_registry = _load_json(DEFAULT_OFFICIAL_REGISTRY_PATH)
    excluded_names = set((policy.get("excluded_sources") or {}).keys())

    records = []
    for path in sorted(source_dir.glob("*.pdf"), key=lambda item: item.name.casefold()):
        audit = audit_pdf(path)
        lane, theme, product_use, runtime_status = _classify_source(path.name)
        limitation = ""
        if path.name in QUARANTINE_USE:
            limitation = QUARANTINE_USE[path.name][2]
        elif lane == "product_research":
            limitation = "Ürün ve Ar-Ge gerekçesi sağlar; hasta düzeyinde beslenme kararını tek başına taşımaz."
        elif lane == "technical_reference":
            limitation = "Teknik yol haritası içindir; klinik öneri veya hukuki uygunluk kanıtı değildir."
        else:
            limitation = "Genel literatür katmanıdır; resmî scoped kanıt veya uzman onayı yerine geçmez."

        records.append({
            "filename": path.name,
            "sha256": audit["sha256"],
            "title": TITLE_OVERRIDES.get(path.name, audit.get("title") or path.stem),
            "author": audit.get("author") or None,
            "year": audit.get("likely_year"),
            "pages": audit.get("pages", 0),
            "document_type": audit.get("document_type"),
            "topics": audit.get("topics") or [],
            "authorities_mentioned": audit.get("authorities") or [],
            "usage_lane": lane,
            "research_theme": theme,
            "runtime_status": runtime_status,
            "clinical_claim_eligible": False,
            "product_use": product_use,
            "limitation": limitation,
            "policy_excluded_from_general_rag": path.name in excluded_names,
            "warnings": audit.get("warnings") or [],
        })

    return {
        "schema_version": "rag_knowledge_catalog:v1",
        "source_policy_version": policy.get("version"),
        "library_file_count": len(records),
        "usage_policy": {
            "clinical_background": "Arka plan araştırması; hasta düzeyinde kesin klinik iddia üretemez.",
            "product_research": "Ürün, mimari, güvenlik ve Ar-Ge kararlarını gerekçelendirir; runtime klinik kanıt değildir.",
            "technical_reference": "Mevzuat ve birlikte çalışabilirlik yol haritasını destekler; klinik veya hukuki onay değildir.",
            "quarantine": "OCR, kaynak kimliği veya belge ayrıştırması tamamlanana kadar indekslenmez.",
        },
        "official_evidence": {
            "registry": "data/clinical_evidence_registry.json",
            "collection": official_registry.get("collection"),
            "source_count": len(official_registry.get("sources") or {}),
            "clinical_review_required": official_registry.get("clinical_review_required"),
        },
        "sources": records,
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("source_dir", type=Path)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT_PATH)
    args = parser.parse_args()

    catalog = build_catalog(args.source_dir)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(catalog, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({
        "output": str(args.output),
        "source_count": catalog["library_file_count"],
        "lanes": {
            lane: sum(source["usage_lane"] == lane for source in catalog["sources"])
            for lane in catalog["usage_policy"]
        },
    }, ensure_ascii=False))


if __name__ == "__main__":
    main()
