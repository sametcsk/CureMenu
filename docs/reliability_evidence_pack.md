# CureMenu Reliability Evidence Pack

Checked on 15 July 2026. This pack records engineering tests and source provenance only; it does not establish clinical performance or regulatory status.

## What is implemented and verifiable

- 128 automated tests pass; Python compilation is clean.
- All 13 current frontend JavaScript files pass `node --check`.
- The main clinical library contains 1,976 deduplicated chunks from 26 active sources.
- A separate official evidence collection contains 100 chunks from 29 explicitly allowlisted pages in 8 FDA, KDIGO, and EAACI documents.
- Every active deterministic medication-food rule has a stable rule ID, source URL, local SHA-256, exact page/section, evidence summary, rule version, and provenance version.
- Deterministic medication-food rules run before RAG/LLM explanation.
- Unsupported or high-variability profiles do not receive an unqualified safe signal: children, pregnancy/lactation, kidney disease/dialysis, eating-disorder history, and unknown medication terms require professional review.
- RAG rejects evidence without meaningful lexical and clinical-anchor overlap; official sources receive only a limited ranking bonus after relevance is established.
- The embedding model is local-only by default so an unavailable internet connection does not silently disable clinical retrieval.

## Current deterministic rule coverage

| Medication | Food/context | Product behavior | Primary evidence |
|---|---|---|---|
| Warfarin | Major changes in vitamin K / leafy greens | Caution; emphasize consistency | FDA label, page 16 |
| Atorvastatin | Large quantities of grapefruit juice | Caution; quantity matters | FDA 2024 label, pages 5, 19, 28 |
| Metformin | Alcohol, especially excessive use | Caution | FDA label, page 6 |
| Levothyroxine | Calcium, iron, dairy timing | Caution; timing matters | FDA 2024 label, pages 3, 10, 19 |
| Ciprofloxacin | Dairy/calcium alone and dose timing | Caution; normal mixed meal nuance retained | FDA label, pages 8, 22 |
| Linezolid/MAOI | High-tyramine foods | Avoid/review | FDA 2024 label, pages 22, 29 |

## Automated evidence maintenance

Source URL, hash, page scope, and rule provenance are maintained in one registry: `data/clinical_evidence_registry.json`.

```powershell
# Local PDF/hash/page/rule verification
.\.venv\Scripts\python.exe scripts\sync_clinical_evidence.py --check-only

# Also scan likely evidence pages for human review
.\.venv\Scripts\python.exe scripts\sync_clinical_evidence.py --check-only --discover-pages

# Compare remote official files with accepted hashes
.\.venv\Scripts\python.exe scripts\sync_clinical_evidence.py --download

# Rebuild the scoped official Chroma collection after verification
.\.venv\Scripts\python.exe scripts\sync_clinical_evidence.py --rebuild
```

The sync is fail-closed: HTML responses, unreadable PDFs, missing pages, and changed hashes stop the process. It does not approve new evidence or change clinical rule severity automatically.

## Claims that are safe for a presentation

- "Çalışan teknik çekirdekte kaynak izlenebilirliği ve deterministik güvenlik kontrolleri bulunuyor."
- "İlaç-besin kuralları resmî ürün etiketlerinin belirli sayfalarına bağlanıyor ve sürümleniyor."
- "Belirsiz veya kapsam dışı durumda sistem kesin konuşmak yerine uzman değerlendirmesi istiyor."
- "Yapay zeka öneri üretiminde kullanılıyor; yüksek riskli eşleşmeler yalnızca yapay zekanın yorumuna bırakılmıyor."

## Claim boundaries

- Do not describe the prototype as clinically reviewed, error-free, universally applicable, or equivalent to a health professional.
- Do not claim complete medication-food interaction or disease coverage.
- Do not imply a regulator, medical-device process, or named expert has endorsed the product.
- Registry membership proves scoped provenance and file integrity only; it is not a clinician sign-off on every PDF or generated answer.

## Remaining evidence work

1. A pharmacist and clinical dietitian must review each deterministic rule, wording, severity, and Turkish product context; reviewer identity/date must then be recorded.
2. Build a de-identified expert-labelled benchmark set with expected allow/caution/block/review outcomes and inter-rater agreement.
3. Obtain current Turkish KUB/KT documents through an authoritative and maintainable channel.
4. Add current primary guidance for celiac disease, gout, pregnancy/lactation, pediatrics, and eating disorders before expanding autonomous scope.
5. Run prospective usability and safety pilots; automated tests alone cannot establish clinical performance.
