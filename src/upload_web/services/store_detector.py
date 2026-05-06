from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass
from difflib import SequenceMatcher

from src.models.store import Store
from src.shared.stores.loader import load_stores

AUTO_SELECT_THRESHOLD = 0.85
SUGGEST_THRESHOLD = 0.5
_POSTAL_CODE_PATTERN = re.compile(r"\b\d{5}\b")
_PUNCTUATION_PATTERN = re.compile(r"[^\w\s]")
_WHITESPACE_PATTERN = re.compile(r"\s+")


@dataclass(frozen=True, slots=True)
class StoreMatch:
    store: Store | None
    confidence: float
    method: str


def normalize_text(value: str) -> str:
    normalized = unicodedata.normalize("NFD", value.lower())
    without_accents = "".join(char for char in normalized if unicodedata.category(char) != "Mn")
    without_punctuation = _PUNCTUATION_PATTERN.sub(" ", without_accents)
    return _WHITESPACE_PATTERN.sub(" ", without_punctuation).strip()


def detect_store(extracted_address: str, stores: list[Store]) -> StoreMatch:
    normalized_address = normalize_text(extracted_address)
    if not normalized_address or not stores:
        return StoreMatch(store=None, confidence=0.0, method="no_match")

    postal_codes = set(_POSTAL_CODE_PATTERN.findall(extracted_address))
    postal_matches = [store for store in stores if store.postal_code and store.postal_code in postal_codes]
    if postal_matches:
        best_postal_match = max(postal_matches, key=lambda store: _street_score(normalized_address, store))
        best_context = max(
            _city_score(normalized_address, best_postal_match), _street_score(normalized_address, best_postal_match)
        )
        confidence = round(min(0.95 + (0.05 * best_context), 1.0), 2)
        return StoreMatch(store=best_postal_match, confidence=confidence, method="postal_code")

    ranked_matches = sorted(
        ((_fuzzy_score(normalized_address, store), store) for store in stores),
        key=lambda item: item[0],
        reverse=True,
    )
    best_score, best_store = ranked_matches[0]
    rounded_score = round(best_score, 2)
    if rounded_score < SUGGEST_THRESHOLD:
        return StoreMatch(store=None, confidence=rounded_score, method="no_match")
    return StoreMatch(store=best_store, confidence=rounded_score, method="city_street_fuzzy")


def _fuzzy_score(normalized_address: str, store: Store) -> float:
    city_score = _city_score(normalized_address, store)
    street_score = _street_score(normalized_address, store)
    return min((0.55 * city_score) + (0.45 * street_score), 0.99)


def _city_score(normalized_address: str, store: Store) -> float:
    return _text_score(normalized_address, normalize_text(store.city))


def _street_score(normalized_address: str, store: Store) -> float:
    normalized_city = normalize_text(store.city)
    candidates = [normalize_text(store.address)]
    candidates.extend(normalize_text(alias) for alias in store.aliases)
    filtered_candidates = [candidate for candidate in candidates if candidate and candidate != normalized_city]
    if not filtered_candidates:
        return 0.0
    return max(_text_score(normalized_address, candidate) for candidate in filtered_candidates)


def _text_score(source: str, candidate: str) -> float:
    if not candidate:
        return 0.0

    source_tokens = set(source.split())
    candidate_tokens = set(candidate.split())
    token_overlap = 0.0
    token_subset = 0.0
    if candidate_tokens:
        token_overlap = len(source_tokens & candidate_tokens) / len(candidate_tokens)
        token_subset = 1.0 if candidate_tokens.issubset(source_tokens) else 0.0

    return max(
        SequenceMatcher(None, source, candidate).ratio(),
        token_overlap,
        token_subset,
        1.0 if candidate in source else 0.0,
    )


def detect_store_from_catalog(extracted_address: str) -> StoreMatch:
    return detect_store(extracted_address, load_stores())


__all__ = [
    "AUTO_SELECT_THRESHOLD",
    "SUGGEST_THRESHOLD",
    "StoreMatch",
    "detect_store",
    "detect_store_from_catalog",
    "normalize_text",
]
