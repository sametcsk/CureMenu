# RAG Source Gap Report

## Current state

- Desktop library audited: 43 PDFs, 2,260 pages.
- Active clinical collection: `klinik_kutuphane_v2` with 1,976 chunks from 26 sources.
- Exact duplicate chunks: 0.
- Stale persisted sources: 0.
- Seventeen local PDFs are intentionally not active clinical evidence. They are OCR-only, merged/uncitable, or concern AI architecture, interoperability, regulation, or product research rather than patient-level nutrition decisions.
- `14.pdf` has no usable text layer and requires OCR plus source identification before it can be considered.
- `kepan_2025.pdf` is a merged multi-document file. It must not be cited as one clinical source.
- Those seventeen files are no longer treated as an unused remainder. Eleven are cataloged as product/AI research, four as technical references, and two as quarantine items in `data/rag_knowledge_catalog.json`.

Detailed per-file reports are under `outputs/rag_audit/`.
The automatically inferred topic, year, and document-type labels are triage hints only. They do not replace bibliographic verification or clinical approval.

## Knowledge utilization model

The library has four deliberately separated uses:

1. **Official scoped evidence:** eight hash-pinned FDA, KDIGO, and EAACI documents support source traceability for current deterministic rules. Expert clinical review remains pending.
2. **Clinical background:** twenty-six local PDFs remain indexed for literature research, but the health-claim retrieval filter does not accept them as patient-level evidence.
3. **Product and technical research:** fifteen documents inform product design, behavior-change framing, multi-agent/RAG architecture, safety guardrails, interoperability, and regulatory planning. They are not part of runtime clinical evidence.
4. **Quarantine:** `14.pdf` requires OCR and bibliographic verification; `kepan_2025.pdf` requires document-level separation before either can be cited reliably.

The readable map of how these sources influenced CureMenu is maintained in `docs/RAG_KNOWLEDGE_ASSET_MAP.md`. The complete machine-readable inventory, including SHA-256, topic, document type, use lane, and limitation, is in `data/rag_knowledge_catalog.json`.

## Scoped official evidence collection

Eight official documents are stored under `data/rag_candidates/official/`. Their file hashes are verified and 29 page-reviewed sections are active in the separate `clinical_official_evidence_v1` collection:

- Six FDA prescribing labels supporting the current warfarin, atorvastatin, metformin, levothyroxine, ciprofloxacin, and linezolid rules.
- KDIGO 2024 CKD guideline for current kidney-disease context.
- EAACI 2024 IgE-mediated food-allergy guideline for allergen avoidance and referral context.

`data/clinical_evidence_registry.json` is the single source of truth for source URLs, SHA-256 values, page allowlists, and deterministic-rule provenance. Source verification is automated; clinical expert approval is explicitly pending.

Run the local verification and page-candidate scan with:

```powershell
.\.venv\Scripts\python.exe scripts\sync_clinical_evidence.py --check-only --discover-pages
```

Use `--download` to compare official remote PDFs with the accepted hashes. A changed upstream file is never accepted automatically. After human review updates the registry, use `--rebuild` to rebuild the scoped Chroma collection.

## Still missing or not yet activated

Priority 0:

- Turkish SmPC/KUB documents for medicines used by Turkish users. FDA labels are strong primary evidence but do not replace locally approved product information.
- A Turkish pharmacist/physician review of locally marketed product KUB/KT documents. A stable, open, official TİTCK download endpoint could not be verified; third-party mirrors were not admitted as official evidence.
- OCR and source identification for `14.pdf`; otherwise delete it from the clinical library workflow.

Priority 1:

- ACG 2023 celiac guideline or another current licensed/open primary guideline.
- ACR 2020 gout guideline for the existing gout restrictions.
- WHO sodium guidance/direct PDF, once the endpoint returns a valid PDF rather than an HTML shell and reuse terms are verified.
- Current pregnancy, lactation, pediatric, and eating-disorder guidance before these populations are supported.

Priority 2:

- Turkish guideline updates for hypertension, CKD, food allergy, and celiac disease.
- Benchmark cases reviewed and signed off by named experts, covering contradictions between disease, allergy, medication, laboratory, budget, and family profiles.

## Safety boundary

RAG is supporting evidence, not a clinical decision engine. Deterministic rules run first. Retrieval without sufficient lexical and clinical-anchor overlap returns no evidence. Missing or conflicting evidence must produce caution or professional review, never a fully safe claim.

Children, pregnancy/lactation, kidney disease/dialysis, and eating-disorder histories are currently outside autonomous personalization scope. The product may provide general decision support, but it must surface professional-review warnings for these profiles.
