import os
from functools import lru_cache
from typing import Any

import requests


BIOPORTAL_SEARCH_URL = "https://data.bioontology.org/search"
BIOPORTAL_INCLUDE = "prefLabel,synonym,definition,notation,cui,semanticType"


class BioPortalClient:
    def __init__(self, *, api_key: str | None = None, timeout_seconds: float = 3.0) -> None:
        self._api_key = api_key if api_key is not None else os.getenv("BIOPORTAL_API_KEY")
        self._timeout_seconds = timeout_seconds
        self._cache: dict[str, list[dict[str, Any]]] = {}

    @property
    def enabled(self) -> bool:
        return bool(self._api_key)

    def search(self, term: str) -> list[dict[str, Any]]:
        query = (term or "").strip()
        if not query or not self.enabled:
            return []

        cache_key = query.casefold()
        if cache_key in self._cache:
            return self._cache[cache_key]

        try:
            response = requests.get(
                BIOPORTAL_SEARCH_URL,
                headers={"Authorization": f"apikey token={self._api_key}"},
                params={
                    "q": query,
                    "include": BIOPORTAL_INCLUDE,
                    "require_exact_match": "false",
                },
                timeout=self._timeout_seconds,
            )
            response.raise_for_status()
            data = response.json()
            collection = data.get("collection", [])
            results = collection if isinstance(collection, list) else []
        except (requests.RequestException, ValueError, TypeError):
            return []

        self._cache[cache_key] = results
        return results


@lru_cache(maxsize=1)
def default_bioportal_client() -> BioPortalClient:
    return BioPortalClient()
