from __future__ import annotations

import pytest

from src.shared.stores.loader import load_stores
from src.upload_web.services.store_detector import (
    AUTO_SELECT_THRESHOLD,
    SUGGEST_THRESHOLD,
    detect_store,
    detect_store_from_catalog,
)

pytestmark = pytest.mark.unit

STORES = load_stores()


def test_detect_store_prefers_exact_postal_code_match() -> None:
    match = detect_store(
        "Entrega en Carretera de Majadahonda a Boadilla, 106, 28222 Majadahonda, Madrid",
        STORES,
    )

    assert match.store is not None
    assert match.store.id == "VDC-MAD-MAJADAHONDA"
    assert match.confidence >= AUTO_SELECT_THRESHOLD
    assert match.method == "postal_code"


def test_detect_store_returns_suggestion_for_city_only_match() -> None:
    match = detect_store("Entrega prevista en Paterna para recepción de tienda", STORES)

    assert match.store is not None
    assert match.store.id == "VDC-VLC-PATERNA"
    assert SUGGEST_THRESHOLD <= match.confidence < AUTO_SELECT_THRESHOLD
    assert match.method == "city_street_fuzzy"


def test_detect_store_returns_no_suggestion_for_unknown_address() -> None:
    match = detect_store("Polígono Industrial La Negrilla, Sevilla", STORES)

    assert match.store is None
    assert match.confidence < SUGGEST_THRESHOLD
    assert match.method == "no_match"


def test_detect_store_handles_accent_variations() -> None:
    match = detect_store("Avenida Enrique Granados 3, malaga", STORES)

    assert match.store is not None
    assert match.store.id == "VDC-MLG-MALAGA"
    assert match.confidence >= AUTO_SELECT_THRESHOLD
    assert match.method == "city_street_fuzzy"


def test_detect_store_handles_partial_address() -> None:
    match = detect_store("Plaza de la Botanica 1 Alcobendas", STORES)

    assert match.store is not None
    assert match.store.id == "VDC-MAD-LOS-PENOTES"
    assert match.confidence >= AUTO_SELECT_THRESHOLD
    assert match.method == "city_street_fuzzy"


def test_detect_store_from_catalog_uses_shared_loader() -> None:
    match = detect_store_from_catalog("Centro Comercial Parquesur, 28916 Leganés")

    assert match.store is not None
    assert match.store.id == "VDC-MAD-PARQUESUR"
    assert match.method == "postal_code"
