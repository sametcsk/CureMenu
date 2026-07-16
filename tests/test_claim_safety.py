from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
SCAN_ROOTS = (
    PROJECT_ROOT / "frontend",
    PROJECT_ROOT / "docs",
    PROJECT_ROOT / "scripts",
)
PROHIBITED_CLAIMS = (
    "klinik olarak doğrulandı",
    "sıfır risk",
    "sıfır halüsinasyon",
    "doktor kadar güvenli",
    "doktor yerine geçer",
    "tedavi önerir",
    "kesin güvenli",
    "her hastalık için uygundur",
    "tüm ilaç-besin etkileşimlerini kapsıyor",
    "klinik standart",
    "%92 güvenli seçim",
    "medical safety",
    "clinical safety",
    "ready for production",
)


def _claim_text_files():
    yield PROJECT_ROOT / "README.md"
    for root in SCAN_ROOTS:
        for path in root.rglob("*"):
            if path.suffix.casefold() in {".md", ".html", ".js", ".py", ".txt"}:
                yield path


def test_public_and_evaluation_texts_do_not_make_unsupported_clinical_claims():
    violations = []
    for path in _claim_text_files():
        text = path.read_text(encoding="utf-8").casefold()
        for phrase in PROHIBITED_CLAIMS:
            if phrase.casefold() in text:
                violations.append(f"{path.relative_to(PROJECT_ROOT)}: {phrase}")

    assert violations == []


def test_evaluate_labels_results_as_engineering_scenario_metrics():
    source = (PROJECT_ROOT / "scripts" / "evaluate.py").read_text(encoding="utf-8")

    assert "Guardrail Scenario Pass Rate" in source
    assert "do not establish clinical performance" in source
    assert "EXPERT REVIEW AND RELEASE CHECKS ARE STILL REQUIRED" in source
