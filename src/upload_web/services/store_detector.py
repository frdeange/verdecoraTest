from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass, field
from difflib import SequenceMatcher

AUTO_SELECT_THRESHOLD = 0.85
SUGGEST_THRESHOLD = 0.5
_POSTAL_CODE_PATTERN = re.compile(r"\b\d{5}\b")
_PUNCTUATION_PATTERN = re.compile(r"[^\w\s]")
_WHITESPACE_PATTERN = re.compile(r"\s+")


@dataclass(frozen=True, slots=True)
class Store:
    id: str
    name: str
    address: str
    city: str
    postal_code: str
    aliases: list[str] = field(default_factory=list)


@dataclass(frozen=True, slots=True)
class StoreMatch:
    store: Store | None
    confidence: float
    method: str


VERDECORA_STORES: list[Store] = [
    Store(
        id="madrid-chamberi-urban",
        name="Verdecora Chamberí Urban",
        address="Calle de Jerónimo de la Quintana 6",
        city="Madrid",
        postal_code="28010",
        aliases=["Chamberí Urban", "Jerónimo de la Quintana", "Trafalgar"],
    ),
    Store(
        id="madrid-rios-rosas-urban",
        name="Verdecora Ríos Rosas Urban",
        address="Calle de Orense 27",
        city="Madrid",
        postal_code="28020",
        aliases=["Ríos Rosas Urban", "Orense", "Cuatro Caminos"],
    ),
    Store(
        id="madrid-lopez-de-hoyos-urban",
        name="Verdecora López de Hoyos Urban",
        address="Calle de Alcalá 110",
        city="Madrid",
        postal_code="28009",
        aliases=["López de Hoyos Urban", "Alcalá 110", "Goya Urban"],
    ),
    Store(
        id="madrid-aravaca",
        name="Verdecora Aravaca",
        address="Calle de Carlos San José",
        city="Madrid",
        postal_code="28023",
        aliases=["Aravaca", "Valdemarín", "Carlos San José"],
    ),
    Store(
        id="leganes-parquesur",
        name="Verdecora Parquesur",
        address="Carretera de Villaverde",
        city="Leganés",
        postal_code="28916",
        aliases=["Parquesur", "El Carrascal"],
    ),
    Store(
        id="alcobendas-los-penotes",
        name="Verdecora Los Peñotes",
        address="Plaza de La Botánica 1",
        city="Alcobendas",
        postal_code="28108",
        aliases=["Los Peñotes", "Plaza de la Botánica", "La Botánica"],
    ),
    Store(
        id="majadahonda",
        name="Verdecora Majadahonda",
        address="Carretera Majadahonda a Boadilla 106",
        city="Majadahonda",
        postal_code="28222",
        aliases=["Majadahonda a Boadilla", "Boadilla"],
    ),
    Store(
        id="torrelodones",
        name="Verdecora Torrelodones",
        address="Calle de Colonia Varela",
        city="Torrelodones",
        postal_code="28250",
        aliases=["Colonia Varela", "Los Prados"],
    ),
    Store(
        id="alcala-de-henares",
        name="Verdecora Alcalá de Henares",
        address="Calle de Cogolludo",
        city="Alcalá de Henares",
        postal_code="28805",
        aliases=["Alcalá", "La Dehesa", "Parque Comercial La Dehesa"],
    ),
    Store(
        id="valencia-paterna",
        name="Verdecora Paterna",
        address="Autovía del Túria",
        city="Paterna",
        postal_code="46980",
        aliases=["Autovía del Túria", "La Coma", "Benimàmet"],
    ),
    Store(
        id="valencia-urban",
        name="Verdecora Valencia Urban",
        address="Calle de Isabel la Católica 9",
        city="Valencia",
        postal_code="46004",
        aliases=["Valencia Urban", "Isabel la Católica", "Eixample"],
    ),
    Store(
        id="valencia-av-puerto",
        name="Verdecora Valencia Av. Puerto",
        address="Avenida del Puerto",
        city="Valencia",
        postal_code="",
        aliases=["Av. Puerto", "Avenida del Puerto", "El Grau", "Cabanyal"],
    ),
    Store(
        id="denia",
        name="Verdecora Dénia",
        address="Dénia",
        city="Dénia",
        postal_code="",
        aliases=["Denia"],
    ),
    Store(
        id="zaragoza",
        name="Verdecora Zaragoza",
        address="Calle de Manuel Jalón",
        city="Zaragoza",
        postal_code="50011",
        aliases=["Manuel Jalón", "Venta del Olivar"],
    ),
    Store(
        id="malaga",
        name="Verdecora Málaga",
        address="Avenida Enrique Granados 3",
        city="Málaga",
        postal_code="29003",
        aliases=["Enrique Granados", "Guadalmar", "Churriana"],
    ),
    Store(
        id="vigo",
        name="Verdecora Vigo",
        address="Vía Norte",
        city="Vigo",
        postal_code="36204",
        aliases=["Via Norte", "Área Central", "Area Central"],
    ),
    Store(
        id="barcelona-sant-quirze",
        name="Verdecora Sant Quirze",
        address="Sant Quirze del Vallès",
        city="Sant Quirze del Vallès",
        postal_code="",
        aliases=["Sant Quirze"],
    ),
    Store(
        id="barcelona-diagonal-534",
        name="Verdecora Diagonal 534",
        address="Avinguda Diagonal 534",
        city="Barcelona",
        postal_code="08036",
        aliases=["Diagonal 534", "Avinguda Diagonal", "Barcelona Diagonal"],
    ),
    Store(
        id="alicante",
        name="Verdecora Alicante",
        address="Alicante",
        city="Alicante",
        postal_code="",
        aliases=["Alacant"],
    ),
]


def normalize_text(value: str) -> str:
    normalized = unicodedata.normalize("NFD", value.lower())
    without_accents = "".join(char for char in normalized if unicodedata.category(char) != "Mn")
    without_punctuation = _PUNCTUATION_PATTERN.sub(" ", without_accents)
    return _WHITESPACE_PATTERN.sub(" ", without_punctuation).strip()


def detect_store(extracted_address: str, stores: list[Store]) -> StoreMatch:
    normalized_address = normalize_text(extracted_address)
    if not normalized_address:
        return StoreMatch(store=None, confidence=0.0, method="no_match")

    postal_codes = set(_POSTAL_CODE_PATTERN.findall(extracted_address))
    postal_matches = [store for store in stores if store.postal_code and store.postal_code in postal_codes]
    if postal_matches:
        best_postal_match = max(postal_matches, key=lambda store: _street_score(normalized_address, store))
        best_context = max(_city_score(normalized_address, best_postal_match), _street_score(normalized_address, best_postal_match))
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


__all__ = [
    "AUTO_SELECT_THRESHOLD",
    "SUGGEST_THRESHOLD",
    "Store",
    "StoreMatch",
    "VERDECORA_STORES",
    "detect_store",
    "normalize_text",
]
