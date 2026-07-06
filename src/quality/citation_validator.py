class CitationValidator:
    def __init__(self):
        pass

    def validate_citation(self, similarity_score: float, evidence_span: str = "") -> float:
        """
        RAG atıflarının (similarity_score) üzerinden eşleşme kalitesini döner.
        0 (Eşleşmiyor) ile 1 (Mükemmel eşleşme) arası.
        """
        # Distance'ı (0.0 en iyi) 0-1 aralığında bir kalite skoruna çevir.
        # Basit bir formül: 1 / (1 + distance) veya lineer dönüşüm.
        if similarity_score < 0:
            return 0.0
        return max(0.0, min(1.0, 1.0 / (1.0 + similarity_score)))
