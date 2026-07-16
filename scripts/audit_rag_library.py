"""Audit a local PDF library without modifying the vector database."""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import re
import unicodedata
from collections import Counter
from datetime import datetime
from pathlib import Path

import fitz


TOPIC_KEYWORDS = {
    "general_nutrition": ("beslenme rehberi", "healthy diet", "dietary guideline", "makro besin"),
    "diabetes": ("diyabet", "diabetes", "glycemic", "glisemik"),
    "hypertension_cardiovascular": ("hipertansiyon", "hypertension", "cardiovascular", "kalp damar"),
    "celiac_gluten": ("colyak", "celiac", "gluten"),
    "kidney": ("bobrek", "renal", "kidney", "nefro"),
    "gastrointestinal": ("irritable bowel", "ibs", "gastro", "bagirsak", "intestinal"),
    "thyroid": ("thyroid", "tiroid", "hashimoto", "levothyroxine"),
    "women_health": ("menopause", "menopoz", "pcos", "gebelik", "pregnancy"),
    "drug_nutrient": ("drug nutrient", "food drug", "ilac besin", "farmakokinetik"),
    "clinical_ai_safety": ("guardrail", "healthcare ai", "clinical ai", "hallucination", "yapay zeka"),
    "rag_retrieval": ("retrieval augmented", "retrieval-augmented", "rag", "vector database"),
    "interoperability": ("fhir", "hl7", "icd-11", "interoperability"),
    "behavior_change": ("behavior change", "behaviour change", "self-management", "oz yonetim"),
    "regulation_privacy": ("eu ai act", "kvkk", "gdpr", "privacy", "data protection"),
}

AUTHORITY_KEYWORDS = {
    "WHO": ("world health organization", "dunya saglik orgutu"),
    "T.C. Saglik Bakanligi": ("t.c. saglik bakanligi", "turkiye saglik bakanligi"),
    "TEMD": ("turkiye endokrinoloji ve metabolizma dernegi", "temd"),
    "ESPEN": ("european society for clinical nutrition", "espen"),
    "ADA": ("american diabetes association", "standards of care in diabetes"),
    "AHA/ACC": ("american heart association", "american college of cardiology"),
    "KDIGO": ("kidney disease improving global outcomes", "kdigo"),
    "EFSA": ("european food safety authority", "efsa"),
    "FDA": ("u.s. food and drug administration", "food and drug administration"),
    "EAACI": ("european academy of allergy and clinical immunology", "eaaci"),
    "ACG": ("american college of gastroenterology",),
}


def _normalize(value: str) -> str:
    return re.sub(r"\s+", " ", (value or "").strip())


def _search_normalize(value: str) -> str:
    folded = unicodedata.normalize("NFKD", (value or "").casefold())
    without_marks = "".join(char for char in folded if not unicodedata.combining(char))
    return re.sub(r"\s+", " ", without_marks)


def _contains_keyword(text: str, keyword: str) -> bool:
    normalized_keyword = _search_normalize(keyword)
    if len(normalized_keyword) <= 4 and normalized_keyword.isalnum():
        return bool(re.search(rf"(?<![a-z0-9]){re.escape(normalized_keyword)}(?![a-z0-9])", text))
    return normalized_keyword in text


def _first_title(text: str, fallback: str) -> str:
    for line in text.splitlines()[:40]:
        candidate = _normalize(line)
        if 12 <= len(candidate) <= 240 and not candidate.isdigit():
            return candidate
    return fallback


def _infer_year(metadata: dict, first_pages_text: str, filename: str) -> int | None:
    current_year = datetime.now().year
    filename_years = re.findall(r"(?:19|20)\d{2}", filename)
    if filename_years:
        return int(filename_years[-1])
    metadata_values = " ".join(
        str(metadata.get(key) or "")
        for key in ("creationDate", "modDate", "subject", "title")
    )
    candidates = re.findall(r"\b(?:19|20)\d{2}\b", metadata_values + "\n" + first_pages_text)
    valid = [int(year) for year in candidates if 1990 <= int(year) <= current_year]
    if not valid:
        return None
    return Counter(valid).most_common(1)[0][0]


def _classify_document(text: str, filename: str) -> str:
    value = _search_normalize(text)
    filename_value = _search_normalize(filename)
    if filename_value.startswith("fda ") or any(
        term in value
        for term in ("full prescribing information", "highlights of prescribing information")
    ):
        return "regulatory_drug_label"
    if "guideline" in filename_value or "rehberi" in filename_value:
        return "clinical_guideline"
    if any(term in value for term in ("clinical practice guideline", "uygulama rehberi", "tani ve tedavi rehberi")):
        return "clinical_guideline"
    if any(term in value for term in ("systematic review", "meta-analysis", "meta analysis")):
        return "systematic_review"
    if any(term in value for term in ("randomized controlled", "randomised controlled")):
        return "clinical_trial"
    if any(term in value for term in ("review article", "narrative review", "derleme")):
        return "review"
    if any(term in value for term in ("thesis", "tez")):
        return "thesis"
    if any(term in value for term in ("factsheet", "fact sheet", "sunum")):
        return "factsheet_or_presentation"
    return "article_or_other"


def audit_pdf(path: Path) -> dict:
    file_hash = hashlib.sha256(path.read_bytes()).hexdigest()
    warnings: list[str] = []
    try:
        document = fitz.open(path)
    except Exception as exc:
        return {
            "filename": path.name,
            "sha256": file_hash,
            "size_bytes": path.stat().st_size,
            "readable": False,
            "error": type(exc).__name__,
            "warnings": ["PDF acilamadi."],
        }

    page_texts: list[str] = []
    empty_pages = 0
    for page in document:
        text = page.get_text("text") or ""
        page_texts.append(text)
        if len(_normalize(text)) < 40:
            empty_pages += 1

    full_text = "\n".join(page_texts)
    searchable_text = _search_normalize(full_text)
    metadata = document.metadata or {}
    page_count = document.page_count
    document.close()

    text_chars = len(full_text)
    chars_per_page = round(text_chars / max(page_count, 1), 1)
    if text_chars < 200:
        warnings.append("Metin cikarimi yok denecek kadar az; OCR gerekebilir.")
    elif chars_per_page < 250:
        warnings.append("Sayfa basina metin dusuk; taranmis veya gorsel agirlikli olabilir.")
    if empty_pages:
        warnings.append(f"{empty_pages} sayfada anlamli metin cikarilamadi.")

    topics = [
        topic
        for topic, keywords in TOPIC_KEYWORDS.items()
        if any(_contains_keyword(searchable_text, keyword) for keyword in keywords)
    ]
    authorities = [
        authority
        for authority, keywords in AUTHORITY_KEYWORDS.items()
        if any(_contains_keyword(searchable_text, keyword) for keyword in keywords)
    ]
    dois = sorted(set(re.findall(r"10\.\d{4,9}/[-._;()/:A-Z0-9]+", full_text, re.IGNORECASE)))[:10]
    title = _normalize(metadata.get("title", "")) or _first_title(page_texts[0] if page_texts else "", path.stem)

    return {
        "filename": path.name,
        "sha256": file_hash,
        "size_bytes": path.stat().st_size,
        "readable": True,
        "pages": page_count,
        "text_chars": text_chars,
        "chars_per_page": chars_per_page,
        "empty_pages": empty_pages,
        "title": title,
        "author": _normalize(metadata.get("author", "")),
        "subject": _normalize(metadata.get("subject", "")),
        "likely_year": _infer_year(metadata, "\n".join(page_texts[:2]), path.name),
        "document_type": _classify_document(full_text[:250_000], path.name),
        "topics": topics,
        "authorities": authorities,
        "dois": dois,
        "warnings": warnings,
    }


def write_report(records: list[dict], output_dir: Path) -> None:
    output_dir.mkdir(parents=True, exist_ok=True)
    (output_dir / "rag_pdf_audit.json").write_text(
        json.dumps(records, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    fields = [
        "filename", "readable", "pages", "text_chars", "chars_per_page", "empty_pages",
        "likely_year", "document_type", "title", "author", "topics", "authorities", "dois", "warnings",
    ]
    with (output_dir / "rag_pdf_audit.csv").open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields, extrasaction="ignore")
        writer.writeheader()
        for record in records:
            row = dict(record)
            for key in ("topics", "authorities", "dois", "warnings"):
                row[key] = " | ".join(row.get(key) or [])
            writer.writerow(row)

    topic_counts = Counter(topic for record in records for topic in record.get("topics", []))
    lines = [
        "# CureMenu RAG PDF Denetimi",
        "",
        f"- PDF sayisi: {len(records)}",
        f"- Okunamayan PDF: {sum(not item.get('readable') for item in records)}",
        f"- Uyarili PDF: {sum(bool(item.get('warnings')) for item in records)}",
        f"- Toplam sayfa: {sum(item.get('pages', 0) for item in records)}",
        "- Not: Konu, yil ve belge turu etiketleri otomatik on incelemedir; klinik veya bibliyografik onay degildir.",
        "",
        "## Konu Dagilimi",
        "",
        *[f"- {topic}: {count}" for topic, count in topic_counts.most_common()],
        "",
        "## Dosya Envanteri",
        "",
        "| Dosya | Sayfa | Tur | Yil | Konular | Uyari |",
        "|---|---:|---|---:|---|---|",
    ]
    for record in records:
        warnings = "; ".join(record.get("warnings") or [])
        lines.append(
            f"| {record['filename']} | {record.get('pages', '-')} | {record.get('document_type', '-')} | "
            f"{record.get('likely_year') or '-'} | {', '.join(record.get('topics') or []) or '-'} | {warnings or '-'} |"
        )
    (output_dir / "rag_pdf_audit.md").write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("folder", type=Path)
    parser.add_argument("--output-dir", type=Path, default=Path("outputs/rag_audit"))
    args = parser.parse_args()

    pdfs = sorted(args.folder.glob("*.pdf"), key=lambda item: item.name.casefold())
    records = [audit_pdf(path) for path in pdfs]
    write_report(records, args.output_dir)
    print(json.dumps({"pdf_count": len(records), "output_dir": str(args.output_dir)}, ensure_ascii=False))


if __name__ == "__main__":
    main()
