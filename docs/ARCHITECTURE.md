# HealMenu Architecture & Layers

This document outlines the core responsibilities of the different logical layers within the HealMenu system. When adding new features, please consult this document to ensure logic is placed in the correct module.

## 1. Governance (`src/governance/`)
**Responsibility:** Auditability, event tracking, and compliance.
**Details:** This layer does NOT make medical or logic decisions. It records them. It provides the event-sourcing primitives (`events.py`) and standardizes decision records (`decision.py`) so that the system's actions are traceable, auditable, and can be queried for KPIs.

## 2. Quality (`src/quality/`)
**Responsibility:** Metacognition, validation, and confidence scoring.
**Details:** This layer evaluates *how well* the system is performing a given task. It calculates confidence scores (`confidence.py`), validates RAG citations (`citation_validator.py`), and logs explainability metrics (`explainability.py`). It monitors the quality of AI outputs but does not enforce medical rules.

## 3. Medical Knowledge (`src/medical_knowledge/`)
**Responsibility:** Medical domain logic and strict health validation.
**Details:** This layer holds the source of truth for clinical interactions. It checks drug-food interactions (`safety_checker.py`) and interfaces with external clinical terminology or ontology databases (like ICD-11). If a medical rule is violated, this layer raises the flag.

## 4. Rules (`src/rules/`)
**Responsibility:** Business and application-level policy enforcement.
**Details:** This layer manages generic policies, routing constraints, and deterministic logic that isn't strictly "medical". For example, deciding if a user request requires a "Review" or should be "Blocked" based on application state or predefined risk matrices (`engine.py`, `policy.py`).

## 5. Grocery (`src/grocery/`)
**Responsibility:** E-commerce, inventory, and supply chain logic.
**Details:** Converts abstract dietary plans into actionable shopping items. Handles price estimation, alternative ingredient sourcing, and integration with grocery store APIs. It uses the `medical_knowledge` layer to ensure recommended substitutions don't violate patient restrictions.

## 6. Privacy (`src/privacy/`)
**Responsibility:** Data redaction and PII protection.
**Details:** Ensures that no Personally Identifiable Information (PII) leaks into the logs, LLM prompts, or external databases. It redacts names, phone numbers, and sensitive health markers (`redaction.py`) before data crosses trust boundaries.
