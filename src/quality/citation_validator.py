class CitationValidator:
    def validate_citation(
        self,
        similarity_score: float,
        evidence_span: str = "",
        lexical_score: float | None = None,
    ) -> float:
        """Return a conservative 0-1 retrieval quality signal.

        Chroma distance alone is not a calibrated confidence score. When the
        retrieval filter supplies lexical overlap, combine both signals while
        giving lexical relevance the larger weight. Older callers retain the
        previous distance-only behavior.
        """
        if similarity_score < 0:
            distance_quality = 0.0
        else:
            distance_quality = max(0.0, min(1.0, 1.0 / (1.0 + similarity_score)))

        if lexical_score is None:
            return distance_quality

        lexical_quality = max(0.0, min(1.0, float(lexical_score)))
        return (0.7 * lexical_quality) + (0.3 * distance_quality)
