from __future__ import annotations

import pytest

from src.upload_web.services.store_detector import VERDECORA_STORES, detect_store

pytestmark = pytest.mark.unit


def test_detect_store_prefers_exact_postal_code_match() -> None:
    match = detect_store(
        "Entrega en Carretera Majadahonda a Boadilla 106, 28222 Majadahonda, Madrid",
        VERDECORA_STORES,
    )

    assert match.store is not None
    assert match.store.id == "majadahonda"
    assert match.confidence >= 0.85
    assert match.method == "postal_code"


def test_detect_store_returns_medium_confidence_for_city_only_match() -> None:
    match = detect_store("Entrega prevista en Paterna para recepción de tienda", VERDECORA_STORES)

    assert match.store is not None
    assert match.store.id == "valencia-paterna"
    assert 0.5 <= match.confidence < 0.85
    assert match.method == "city_street_fuzzy"


def test_detect_store_returns_no_suggestion_for_unknown_address() -> None:
    match = detect_store("Polígono Industrial La Negrilla, Sevilla", VERDECORA_STORES)

    assert match.store is None
    assert match.confidence < 0.5
    assert match.method == "no_match"


def test_detect_store_handles_accent_variations() -> None:
    match = detect_store("Avenida Enrique Granados 3, malaga", VERDECORA_STORES)

    assert match.store is not None
    assert match.store.id == "malaga"
    assert match.confidence >= 0.85
    assert match.method == "city_street_fuzzy"


def test_detect_store_handles_partial_address() -> None:
    match = detect_store("Plaza de la Botanica 1 Alcobendas", VERDECORA_STORES)

    assert match.store is not None
    assert match.store.id == "alcobendas-los-penotes"
    assert match.confidence >= 0.85
    assert match.method == "city_street_fuzzy"
