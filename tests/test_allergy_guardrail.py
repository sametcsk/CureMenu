import pytest
from typing import Any
from src.quality.rule_engine import RuleEngine
from src.medical_knowledge.safety_checker import check_medication_food_safety

def test_shellfish_allergy_detects_shrimp():
    profile: dict[str, Any] = {"alerjiler": ["kabuklu deniz ürünleri"], "hastaliklar": []}
    meal = "karidesli makarna"
    ingredients = ["karides", "makarna"]
    
    engine = RuleEngine()
    result = engine.check_rules(profile, meal, ingredients)
    
    risks = result.get("found_risks", [])
    assert any("kabuklu" in r.lower() or "allergi" in r.lower() or "alerji" in r.lower() for r in risks), f"Should detect shellfish allergy, got {risks}"
    assert "allergy-shellfish:v1" in result.get("matched_rules", [])

def test_shellfish_allergy_detects_mussel():
    profile: dict[str, Any] = {"alerjiler": ["shellfish"], "hastaliklar": []}
    meal = "midye dolma"
    ingredients = ["midye", "pirinç", "baharat"]
    
    engine = RuleEngine()
    result = engine.check_rules(profile, meal, ingredients)
    
    risks = result.get("found_risks", [])
    assert any("alerji riski" in r.lower() for r in risks), f"Should detect mussel as shellfish allergy, got {risks}"
    assert "allergy-shellfish:v1" in result.get("matched_rules", [])

def test_fish_allergy_detects_salmon():
    profile: dict[str, Any] = {"alerjiler": ["balık"], "hastaliklar": []}
    meal = "fırında somon"
    ingredients = ["somon", "zeytinyağı"]
    
    engine = RuleEngine()
    result = engine.check_rules(profile, meal, ingredients)
    
    risks = result.get("found_risks", [])
    assert any("alerji riski" in r.lower() for r in risks), f"Should detect salmon as fish allergy, got {risks}"
    assert "allergy-fish:v1" in result.get("matched_rules", [])

def test_medication_and_allergy_independent():
    # Profilde hem warfarin ilacı hem de kabuklu deniz ürünleri alerjisi var
    profile: dict[str, Any] = {"alerjiler": ["kabuklu deniz ürünleri"], "hastaliklar": []}
    medications = ["warfarin"]
    meal = "ıspanak yatağında karides"
    ingredients = ["ıspanak", "karides"]
    
    # Kural motoru (alerji/hastalık) kontrolü
    engine = RuleEngine()
    rule_result = engine.check_rules(profile, meal, ingredients)
    
    # İlaç-besin etkileşimi kontrolü
    med_result = check_medication_food_safety(medications, meal)
    
    # 1. Alerji tespit edilmeli
    risks = rule_result.get("found_risks", [])
    assert any("alerji riski" in r.lower() for r in risks), "Allergy should be detected"
    assert "allergy-shellfish:v1" in rule_result.get("matched_rules", [])
    
    # 2. İlaç etkileşimi tespit edilmeli
    matched_med_rules = med_result.get("matched_rules", [])
    assert len(matched_med_rules) > 0, "Medication rule should be matched"
    
    # Not: İkisi bağımsız tespit ediliyor mu diye kontrol ettik. Sistem chat router'da ikisini birleştiriyor.
